"""Serper.dev API integration for news search."""
import json
import re

import requests
from app import app
from app.models import get_api_key
from app.utils.scraping import cached_json_post


SERPER_NEWS_ENDPOINT = 'https://google.serper.dev/news'
GEMINI_MODEL_CANDIDATES = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-2.0-flash']


def _post_gemini_generate_content(api_key, payload):
    for model in GEMINI_MODEL_CANDIDATES:
        endpoint = (
            'https://generativelanguage.googleapis.com/v1beta/models/'
            f'{model}:generateContent?key={api_key}'
        )
        try:
            response_data = cached_json_post(endpoint, json_payload=payload, timeout=25)
            return {'data': response_data, 'model': model}
        except requests.HTTPError as e:
            status_code = getattr(getattr(e, 'response', None), 'status_code', None)
            if status_code == 404:
                continue
            app.logger.warning('serper: gemini request failed (status=%s)', status_code)
            return None
        except Exception as e:
            app.logger.warning('serper: gemini request failed (%s)', type(e).__name__)
            return None

    app.logger.warning('serper: no compatible Gemini model available')
    return None


def _extract_json_object(raw_text):
    if raw_text is None:
        return None

    text = raw_text.strip()
    fence_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, flags=re.DOTALL)
    if fence_match:
        return fence_match.group(1)

    object_match = re.search(r'(\{.*\})', text, flags=re.DOTALL)
    if object_match:
        return object_match.group(1)

    return None


def search_news(query, num=10):
    """Fetch recent news articles for `query` from serper.dev.

    Returns a list of dicts with keys: title, link, snippet, source, date,
    imageUrl (when available). Returns [] if no API key is configured or the
    request fails.
    """
    api_key = get_api_key('serper')
    if not api_key:
        app.logger.debug('serper: no API key configured')
        return []

    try:
        data = cached_json_post(
            SERPER_NEWS_ENDPOINT,
            headers={'X-API-KEY': api_key, 'Content-Type': 'application/json'},
            json_payload={'q': query, 'num': num},
            timeout=10,
        )
    except Exception as e:
        app.logger.warning('serper.search_news failed for %r: %s', query, e)
        return []

    return data.get('news', []) or []


def analyze_news_sentiment_with_gemini(asset_name, news, preview_only=False):
    """Analyze sentiment for a list of news items using Gemini.

    Returns a dict:
    {
      'overall': 'positive|neutral|negative',
      'summary': 'short text',
      'items': [{'index': int, 'sentiment': str, 'confidence': float, 'reason': str}, ...]
    }
    or None when Gemini API key is unavailable or request fails.
    """
    if not news:
        return None

    compact_news = []
    for idx, item in enumerate(news[:6]):
        compact_news.append({
            'index': idx,
            'title': str(item.get('title', ''))[:220],
            'snippet': str(item.get('snippet', ''))[:360],
            'source': item.get('source', ''),
            'date': item.get('date', ''),
        })

    prompt = (
        'You are a financial news sentiment analyst. '
        'Given the asset name and a list of recent news headlines/snippets, classify sentiment. '
        'Return ONLY valid JSON with this schema: '
        '{"overall":"positive|neutral|negative",'
        '"summary":"max 240 chars",'
        '"items":[{"index":0,"sentiment":"positive|neutral|negative",'
        '"confidence":0.0,"reason":"max 120 chars"}]}. '
        'If confidence is low, prefer neutral. Do not include markdown. '
        f'Asset: {asset_name}. News: {json.dumps(compact_news, ensure_ascii=True)}'
    )

    if preview_only:
        return {'prompt': prompt, 'preview': True}

    api_key = get_api_key('gemini')
    if not api_key:
        app.logger.debug('serper: no gemini API key configured')
        return None

    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'temperature': 0, 'responseMimeType': 'application/json'},
    }

    try:
        gemini_result = _post_gemini_generate_content(api_key, payload)
        if not gemini_result:
            return None
        response_data = gemini_result['data']
        model_used = gemini_result.get('model')

        candidates = response_data.get('candidates', [])
        if not candidates:
            return None

        parts = candidates[0].get('content', {}).get('parts', [])
        if not parts:
            return None

        raw_text = parts[0].get('text', '')
        json_text = _extract_json_object(raw_text)
        if json_text is None:
            return None

        parsed = json.loads(json_text)

        overall = str(parsed.get('overall', 'neutral')).strip().lower()
        if overall not in {'positive', 'neutral', 'negative'}:
            overall = 'neutral'

        summary = str(parsed.get('summary', '')).strip()

        parsed_items = parsed.get('items', []) or []
        items = []
        for item in parsed_items:
            try:
                idx = int(item.get('index'))
            except Exception:
                continue

            sentiment = str(item.get('sentiment', 'neutral')).strip().lower()
            if sentiment not in {'positive', 'neutral', 'negative'}:
                sentiment = 'neutral'

            try:
                confidence = float(item.get('confidence', 0.0))
            except Exception:
                confidence = 0.0
            confidence = max(0.0, min(1.0, confidence))

            reason = str(item.get('reason', '')).strip()
            items.append({
                'index': idx,
                'sentiment': sentiment,
                'confidence': confidence,
                'reason': reason,
            })

        return {
            'overall': overall,
            'summary': summary,
            'items': items,
            'prompt': prompt,
            'raw_response': raw_text,
            'model': model_used,
        }
    except Exception as e:
        app.logger.warning(
            'serper.analyze_news_sentiment_with_gemini failed for %r (%s)',
            asset_name,
            type(e).__name__,
        )
        return None


def analyze_asset_performance_with_gemini(asset_info, preview_only=False):
    """Generate a qualitative performance analysis for a consolidated asset."""
    consolidated = {
        'name': asset_info.get('name'),
        'source': asset_info.get('source'),
        'ticker': asset_info.get('ticker'),
        'long_name': asset_info.get('long_name'),
        'currency': asset_info.get('currency'),
        'position': asset_info.get('position'),
        'position_total': asset_info.get('position_total'),
        'last_close_price': asset_info.get('last_close_price'),
        'cost': asset_info.get('cost'),
        'liquid_cost': asset_info.get('liquid_cost'),
        'avg_price': asset_info.get('avg_price'),
        'capital_gain': asset_info.get('capital_gain'),
        'realized_gain': asset_info.get('realized_gain'),
        'not_realized_gain': asset_info.get('not_realized_gain'),
        'rentability': asset_info.get('rentability'),
        'anualized_rentability': asset_info.get('anualized_rentability'),
        'price_gain': asset_info.get('price_gain'),
        'age_years': asset_info.get('age_years'),
        'wages_sum': asset_info.get('wages_sum'),
        'rent_wages_sum': asset_info.get('rent_wages_sum'),
        'taxes_sum': asset_info.get('taxes_sum'),
    }

    fundamentals = asset_info.get('info', {}) or {}
    compact_fundamentals = {
        'symbol': fundamentals.get('symbol'),
        'quoteType': fundamentals.get('quoteType'),
        'longName': fundamentals.get('longName'),
        'shortName': fundamentals.get('shortName'),
        'sector': fundamentals.get('sector'),
        'industry': fundamentals.get('industry'),
        'marketCap': fundamentals.get('marketCap'),
        'enterpriseValue': fundamentals.get('enterpriseValue'),
        'trailingPE': fundamentals.get('trailingPE'),
        'forwardPE': fundamentals.get('forwardPE'),
        'priceToBook': fundamentals.get('priceToBook'),
        'beta': fundamentals.get('beta'),
        'fiftyTwoWeekHigh': fundamentals.get('fiftyTwoWeekHigh'),
        'fiftyTwoWeekLow': fundamentals.get('fiftyTwoWeekLow'),
        'fiftyDayAverage': fundamentals.get('fiftyDayAverage'),
        'twoHundredDayAverage': fundamentals.get('twoHundredDayAverage'),
        '52WeekChange': fundamentals.get('52WeekChange'),
        'dividendYield': fundamentals.get('dividendYield'),
        'dividendRate': fundamentals.get('dividendRate'),
        'payoutRatio': fundamentals.get('payoutRatio'),
        'trailingEps': fundamentals.get('trailingEps'),
        'forwardEps': fundamentals.get('forwardEps'),
        'revenueGrowth': fundamentals.get('revenueGrowth'),
        'earningsGrowth': fundamentals.get('earningsGrowth'),
        'profitMargins': fundamentals.get('profitMargins'),
        'operatingMargins': fundamentals.get('operatingMargins'),
        'currentRatio': fundamentals.get('currentRatio'),
        'quickRatio': fundamentals.get('quickRatio'),
        'debtToEquity': fundamentals.get('debtToEquity'),
        'pegRatio': fundamentals.get('pegRatio'),
        'returnOnEquity': fundamentals.get('returnOnEquity'),
        'returnOnAssets': fundamentals.get('returnOnAssets'),
        'targetMeanPrice': fundamentals.get('targetMeanPrice'),
        'targetLowPrice': fundamentals.get('targetLowPrice'),
        'targetHighPrice': fundamentals.get('targetHighPrice'),
        'recommendationKey': fundamentals.get('recommendationKey'),
        'numberOfAnalystOpinions': fundamentals.get('numberOfAnalystOpinions'),
    }

    # Build a compact execution history from transaction dataframes to give
    # Gemini context about behavior (cadence, average ticket, recency).
    dataframes = asset_info.get('dataframes', {}) or {}
    buys_df = dataframes.get('buys')
    sells_df = dataframes.get('sells')
    wages_df = dataframes.get('wages')
    taxes_df = dataframes.get('taxes')

    transaction_context = {
        'buy_trades': 0,
        'sell_trades': 0,
        'wages_events': 0,
        'tax_events': 0,
        'last_buy_date': None,
        'last_sell_date': None,
        'first_trade_date': None,
        'last_trade_date': None,
        'turnover_ratio': 0.0,
        'avg_buy_ticket': 0.0,
        'avg_sell_ticket': 0.0,
    }

    recent_activity = []
    activity_events = []

    if buys_df is not None and len(buys_df) > 0:
        transaction_context['buy_trades'] = int(len(buys_df))
        transaction_context['last_buy_date'] = str(buys_df.iloc[-1].get('Date', ''))
        transaction_context['avg_buy_ticket'] = round(
            _safe_float(buys_df.get('Total', []).mean() if 'Total' in buys_df else 0.0),
            2,
        )
        for _, row in buys_df.tail(24).iterrows():
            activity_events.append({
                '_type': 'buy',
                'Date': row.get('Date', ''),
                'Quantity': row.get('Quantity', 0),
                'Price': row.get('Price', 0),
                'Total': row.get('Total', 0),
            })

    if sells_df is not None and len(sells_df) > 0:
        transaction_context['sell_trades'] = int(len(sells_df))
        transaction_context['last_sell_date'] = str(sells_df.iloc[-1].get('Date', ''))
        transaction_context['avg_sell_ticket'] = round(
            _safe_float(sells_df.get('Total', []).abs().mean() if 'Total' in sells_df else 0.0),
            2,
        )
        for _, row in sells_df.tail(24).iterrows():
            activity_events.append({
                '_type': 'sell',
                'Date': row.get('Date', ''),
                'Quantity': row.get('Quantity', 0),
                'Price': row.get('Price', 0),
                'Total': row.get('Total', 0),
            })

    if wages_df is not None:
        transaction_context['wages_events'] = int(len(wages_df))
    if taxes_df is not None:
        transaction_context['tax_events'] = int(len(taxes_df))

    if activity_events:
        all_activity = sorted(activity_events, key=lambda item: str(item.get('Date', '')))

        if len(all_activity) > 0:
            transaction_context['first_trade_date'] = str(all_activity[0].get('Date', ''))
            transaction_context['last_trade_date'] = str(all_activity[-1].get('Date', ''))

        sells_qty = abs(_safe_float(asset_info.get('sell_quantity')))
        buys_qty = _safe_float(asset_info.get('buy_quantity'))
        transaction_context['turnover_ratio'] = round((sells_qty / buys_qty) if buys_qty > 0 else 0.0, 4)

        for row in all_activity[-8:]:
            recent_activity.append({
                'type': str(row.get('_type', '')),
                'date': str(row.get('Date', '')),
                'quantity': round(_safe_float(row.get('Quantity')), 8),
                'price': round(_safe_float(row.get('Price')), 4),
                'total': round(_safe_float(row.get('Total')), 2),
            })

    derived_metrics = {
        'pnl_over_cost_pct': round(
            100 * (_safe_float(asset_info.get('capital_gain')) / _safe_float(asset_info.get('cost')))
            if _safe_float(asset_info.get('cost')) > 0 else 0.0,
            2,
        ),
        'income_over_cost_pct': round(
            100 * ((_safe_float(asset_info.get('wages_sum')) + _safe_float(asset_info.get('rent_wages_sum')))
                   / _safe_float(asset_info.get('cost')))
            if _safe_float(asset_info.get('cost')) > 0 else 0.0,
            2,
        ),
        'tax_over_income_pct': round(
            100 * (_safe_float(asset_info.get('taxes_sum')) /
                   (_safe_float(asset_info.get('wages_sum')) + _safe_float(asset_info.get('rent_wages_sum'))))
            if (_safe_float(asset_info.get('wages_sum')) + _safe_float(asset_info.get('rent_wages_sum'))) > 0
            else 0.0,
            2,
        ),
        'position_vs_cost_pct': round(
            100 * (_safe_float(asset_info.get('position_total')) / _safe_float(asset_info.get('cost')))
            if _safe_float(asset_info.get('cost')) > 0 else 0.0,
            2,
        ),
    }

    prompt = (
        'You are a buy-side portfolio analyst. Analyze a single asset based only on '
        'the consolidated portfolio metrics and fundamentals provided. '
        'Return ONLY valid JSON with this schema: '
        '{"overall":"great|good|mixed|weak",'
        '"score":0,'
        '"performance_summary":"max 320 chars",'
        '"strengths":["..."],'
        '"risks":["..."],'
        '"next_steps":["..."],'
        '"time_horizon":"short|medium|long",'
        '"confidence":0.0}. '
        'Use concise language in pt-BR. Score must be an integer from 0 to 100. '
        'Consider profitability quality, risk concentration, execution behavior, and consistency over time. '
        'Do not include markdown. '
        f'Consolidated metrics: {json.dumps(consolidated, ensure_ascii=True)}. '
        f'Fundamentals: {json.dumps(compact_fundamentals, ensure_ascii=True)}. '
        f'Derived metrics: {json.dumps(derived_metrics, ensure_ascii=True)}. '
        f'Transaction context: {json.dumps(transaction_context, ensure_ascii=True)}. '
        f'Recent activity: {json.dumps(recent_activity, ensure_ascii=True)}.'
    )

    if preview_only:
        return {'prompt': prompt, 'preview': True}

    api_key = get_api_key('gemini')
    if not api_key:
        app.logger.debug('serper: no gemini API key configured for asset analysis')
        return None

    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'temperature': 0.2, 'responseMimeType': 'application/json'},
    }

    try:
        gemini_result = _post_gemini_generate_content(api_key, payload)
        if not gemini_result:
            return None

        response_data = gemini_result['data']
        model_used = gemini_result.get('model')
        candidates = response_data.get('candidates', [])
        if not candidates:
            return None

        parts = candidates[0].get('content', {}).get('parts', [])
        if not parts:
            return None

        raw_text = parts[0].get('text', '')
        json_text = _extract_json_object(raw_text)
        if json_text is None:
            return None

        parsed = json.loads(json_text)

        overall = str(parsed.get('overall', 'mixed')).strip().lower()
        if overall not in {'great', 'good', 'mixed', 'weak'}:
            overall = 'mixed'

        try:
            score = int(parsed.get('score', 0))
        except Exception:
            score = 0
        score = max(0, min(100, score))

        summary = str(parsed.get('performance_summary', '')).strip()

        def _as_str_list(value, max_items=5):
            if not isinstance(value, list):
                return []
            out = []
            for item in value[:max_items]:
                text = str(item).strip()
                if text:
                    out.append(text)
            return out

        strengths = _as_str_list(parsed.get('strengths'))
        risks = _as_str_list(parsed.get('risks'))
        next_steps = _as_str_list(parsed.get('next_steps'))

        time_horizon = str(parsed.get('time_horizon', 'medium')).strip().lower()
        if time_horizon not in {'short', 'medium', 'long'}:
            time_horizon = 'medium'

        try:
            confidence = float(parsed.get('confidence', 0.0))
        except Exception:
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        return {
            'overall': overall,
            'score': score,
            'performance_summary': summary,
            'strengths': strengths,
            'risks': risks,
            'next_steps': next_steps,
            'time_horizon': time_horizon,
            'confidence': confidence,
            'prompt': prompt,
            'raw_response': raw_text,
            'model': model_used,
        }
    except Exception as e:
        app.logger.warning(
            'serper.analyze_asset_performance_with_gemini failed for %r (%s)',
            asset_info.get('name'),
            type(e).__name__,
        )
        return None


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def analyze_consolidate_performance_with_gemini(consolidate_info, preview_only=False):
    """Generate a high-level portfolio performance analysis from consolidate data."""
    by_group_df = consolidate_info.get('consolidate_by_group')
    if by_group_df is None or len(by_group_df) == 0:
        return None

    try:
        total_row = by_group_df.iloc[0]
        for idx in range(len(by_group_df)):
            row = by_group_df.iloc[idx]
            if str(row.get('asset_class', '')).strip().lower() == 'total':
                total_row = row
                break

        total_metrics = {
            'position': round(_safe_float(total_row.get('position')), 2),
            'liquid_cost': round(_safe_float(total_row.get('liquid_cost')), 2),
            'capital_gain': round(_safe_float(total_row.get('capital_gain')), 2),
            'realized_gain': round(_safe_float(total_row.get('realized_gain')), 2),
            'not_realized_gain': round(_safe_float(total_row.get('not_realized_gain')), 2),
            'rentability': round(_safe_float(total_row.get('rentability')), 2),
            'wages': round(_safe_float(total_row.get('wages')), 2),
            'rents': round(_safe_float(total_row.get('rents')), 2),
            'taxes': round(_safe_float(total_row.get('taxes')), 2),
            'currency': str(total_row.get('currency', 'BRL')),
        }

        allocation = []
        for idx in range(len(by_group_df)):
            row = by_group_df.iloc[idx]
            asset_class = str(row.get('asset_class', '')).strip()
            if not asset_class or asset_class.lower() == 'total':
                continue
            allocation.append({
                'asset_class': asset_class,
                'position': round(_safe_float(row.get('position')), 2),
                'relative_position': round(_safe_float(row.get('relative_position')), 2),
                'rentability': round(_safe_float(row.get('rentability')), 2),
                'capital_gain': round(_safe_float(row.get('capital_gain')), 2),
            })

        allocation = sorted(allocation, key=lambda item: item['position'], reverse=True)[:12]

        top_classes = allocation[:3]
        concentration_top1 = top_classes[0]['relative_position'] if len(top_classes) >= 1 else 0.0
        concentration_top3 = sum(item['relative_position'] for item in top_classes)
        hhi_proxy = round(
            sum((item['relative_position'] / 100.0) ** 2 for item in allocation),
            4,
        )

        group_df = consolidate_info.get('group_df') or []
        top_positions = []
        source_mix = {}
        for group in group_df:
            df = group.get('df')
            if df is None or len(df) == 0:
                continue

            for _, row in df.iterrows():
                source = str(row.get('source', 'unknown'))
                source_mix[source] = source_mix.get(source, 0) + 1
                top_positions.append({
                    'name': str(row.get('name', '')),
                    'source': source,
                    'currency': str(row.get('currency', '')),
                    'asset_class': str(row.get('asset_class', '')),
                    'position_total': round(_safe_float(row.get('position_total')), 2),
                    'rentability': round(_safe_float(row.get('rentability')), 2),
                    'capital_gain': round(_safe_float(row.get('capital_gain')), 2),
                    'age_years': round(_safe_float(row.get('age_years')), 2),
                })

        top_positions = sorted(top_positions, key=lambda item: item['position_total'], reverse=True)[:15]

        class_rentability = [item.get('rentability', 0.0) for item in allocation]
        positive_classes = sum(1 for r in class_rentability if r > 0)
        negative_classes = sum(1 for r in class_rentability if r < 0)

        derived_metrics = {
            'class_count': len(allocation),
            'top1_class_concentration_pct': round(concentration_top1, 2),
            'top3_class_concentration_pct': round(concentration_top3, 2),
            'hhi_concentration_proxy': hhi_proxy,
            'positive_class_count': positive_classes,
            'negative_class_count': negative_classes,
            'source_mix_asset_count': source_mix,
            'usd_brl': _safe_float(consolidate_info.get('usd_brl')),
        }

        prompt = (
            'You are a portfolio strategist. Analyze the portfolio consolidated performance and diversification. '
            'Return ONLY valid JSON with this schema: '
            '{"overall":"great|good|mixed|weak",'
            '"score":0,'
            '"performance_summary":"max 320 chars",'
            '"allocation_summary":"max 220 chars",'
            '"strengths":["..."],'
            '"risks":["..."],'
            '"next_steps":["..."],'
            '"confidence":0.0}. '
            'Use concise language in pt-BR. Score must be integer 0..100. '
            'Explicitly evaluate concentration risk, diversification quality, return consistency, and source/currency mix. '
            'Do not include markdown. '
            f'Total metrics: {json.dumps(total_metrics, ensure_ascii=True)}. '
            f'Allocation by class: {json.dumps(allocation, ensure_ascii=True)}. '
            f'Derived metrics: {json.dumps(derived_metrics, ensure_ascii=True)}. '
            f'Top positions: {json.dumps(top_positions, ensure_ascii=True)}.'
        )

        if preview_only:
            return {'prompt': prompt, 'preview': True}

        api_key = get_api_key('gemini')
        if not api_key:
            app.logger.debug('serper: no gemini API key configured for consolidate analysis')
            return None

        payload = {
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'temperature': 0.2, 'responseMimeType': 'application/json'},
        }

        gemini_result = _post_gemini_generate_content(api_key, payload)
        if not gemini_result:
            return None

        response_data = gemini_result['data']
        model_used = gemini_result.get('model')
        candidates = response_data.get('candidates', [])
        if not candidates:
            return None

        parts = candidates[0].get('content', {}).get('parts', [])
        if not parts:
            return None

        raw_text = parts[0].get('text', '')
        json_text = _extract_json_object(raw_text)
        if json_text is None:
            return None

        parsed = json.loads(json_text)

        overall = str(parsed.get('overall', 'mixed')).strip().lower()
        if overall not in {'great', 'good', 'mixed', 'weak'}:
            overall = 'mixed'

        try:
            score = int(parsed.get('score', 0))
        except Exception:
            score = 0
        score = max(0, min(100, score))

        summary = str(parsed.get('performance_summary', '')).strip()
        allocation_summary = str(parsed.get('allocation_summary', '')).strip()

        def _as_str_list(value, max_items=6):
            if not isinstance(value, list):
                return []
            out = []
            for item in value[:max_items]:
                text = str(item).strip()
                if text:
                    out.append(text)
            return out

        strengths = _as_str_list(parsed.get('strengths'))
        risks = _as_str_list(parsed.get('risks'))
        next_steps = _as_str_list(parsed.get('next_steps'))

        try:
            confidence = float(parsed.get('confidence', 0.0))
        except Exception:
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        return {
            'overall': overall,
            'score': score,
            'performance_summary': summary,
            'allocation_summary': allocation_summary,
            'strengths': strengths,
            'risks': risks,
            'next_steps': next_steps,
            'confidence': confidence,
            'prompt': prompt,
            'raw_response': raw_text,
            'model': model_used,
        }
    except Exception as e:
        app.logger.warning(
            'serper.analyze_consolidate_performance_with_gemini failed (%s)',
            type(e).__name__,
        )
        return None

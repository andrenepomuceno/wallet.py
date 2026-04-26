"""Serper.dev API integration for news search."""
import json
import re

import requests
from app import app
from app.models import get_api_key


SERPER_NEWS_ENDPOINT = 'https://google.serper.dev/news'
GEMINI_MODEL_CANDIDATES = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-2.0-flash']


def _post_gemini_generate_content(api_key, payload):
    for model in GEMINI_MODEL_CANDIDATES:
        endpoint = (
            'https://generativelanguage.googleapis.com/v1beta/models/'
            f'{model}:generateContent?key={api_key}'
        )
        try:
            response = requests.post(endpoint, json=payload, timeout=25)
            if response.status_code == 404:
                continue
            response.raise_for_status()
            return {'data': response.json(), 'model': model}
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
        response = requests.post(
            SERPER_NEWS_ENDPOINT,
            headers={'X-API-KEY': api_key, 'Content-Type': 'application/json'},
            json={'q': query, 'num': num},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        app.logger.warning('serper.search_news failed for %r: %s', query, e)
        return []

    return data.get('news', []) or []


def analyze_news_sentiment_with_gemini(asset_name, news):
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

    api_key = get_api_key('gemini')
    if not api_key:
        app.logger.debug('serper: no gemini API key configured')
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

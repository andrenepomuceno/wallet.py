"""Asset detail view + price history view."""
import pandas as pd
from flask import abort, jsonify, render_template, request

from app import app
from app.processing import (
    plot_price_history,
    process_avenue_asset_request,
    process_b3_asset_request,
    process_generic_asset_request,
    process_history,
)
from app.utils.serper import (
    analyze_asset_performance_with_gemini,
    analyze_news_sentiment_with_gemini,
    search_news,
)


_ALLOWED_NEWS_SORTS = {'date_desc', 'date_asc', 'source_asc', 'title_asc'}


def _sort_news(news, news_sort):
    if not news:
        return news

    if news_sort == 'source_asc':
        return sorted(news, key=lambda item: str(item.get('source', '')).lower())

    if news_sort == 'title_asc':
        return sorted(news, key=lambda item: str(item.get('title', '')).lower())

    if news_sort == 'date_asc':
        return sorted(
            news,
            key=lambda item: pd.to_datetime(item.get('date'), errors='coerce'),
        )

    # default: newest first
    return sorted(
        news,
        key=lambda item: pd.to_datetime(item.get('date'), errors='coerce'),
        reverse=True,
    )


def _load_asset_info_or_404(source, asset):
    asset_info = {'valid': False}

    if source == 'b3':
        asset_info = process_b3_asset_request(asset)
    elif source == 'avenue':
        asset_info = process_avenue_asset_request(asset)
    elif source == 'generic':
        asset_info = process_generic_asset_request(asset)
    else:
        abort(404)

    if not asset_info['valid']:
        abort(404)

    return asset_info


def _build_news_payload(asset_info, fetch_news=False, analyze_sentiment=False, news_sort='date_desc'):
    news = []
    news_sentiment = None
    prompt_preview = None
    asset = asset_info['name']

    if fetch_news:
        news_query = asset_info.get('long_name') or asset_info.get('ticker') or asset
        news = search_news(f'{news_query} stock', num=8)
        news = _sort_news(news, news_sort)

        preview_sentiment = False
        if analyze_sentiment and isinstance(analyze_sentiment, dict):
            preview_sentiment = bool(analyze_sentiment.get('preview_only'))
            analyze_sentiment = True

        if analyze_sentiment and preview_sentiment:
            preview = analyze_news_sentiment_with_gemini(asset, news, preview_only=True)
            if preview:
                prompt_preview = preview.get('prompt')
        elif analyze_sentiment:
            news_sentiment = analyze_news_sentiment_with_gemini(asset, news)

        # Map sentiment output back to each news item for rendering.
        if news_sentiment and news_sentiment.get('items'):
            sentiment_by_index = {
                item.get('index'): item
                for item in news_sentiment['items']
                if isinstance(item, dict)
            }
            for idx, item in enumerate(news):
                meta = sentiment_by_index.get(idx)
                if meta:
                    item['sentiment'] = meta.get('sentiment', 'neutral')
                    item['sentiment_confidence'] = meta.get('confidence', 0.0)
                    item['sentiment_reason'] = meta.get('reason', '')

    return {
        'news': news,
        'news_sentiment': news_sentiment,
        'news_requested': fetch_news,
        'sentiment_requested': analyze_sentiment,
        'news_sort': news_sort,
        'prompt_preview': prompt_preview,
    }


def _view_asset_helper(asset_info, fetch_news=False, analyze_sentiment=False, news_sort='date_desc'):
    dataframes = asset_info['dataframes']
    extended_info = asset_info['info']

    buys = dataframes['buys']
    sells = dataframes['sells']
    wages = dataframes['wages']
    taxes = dataframes['taxes']

    buys = buys[['Date', 'Movimentation', 'Quantity', 'Price', 'Total']]
    sells = sells[['Date', 'Movimentation', 'Quantity', 'Price', 'Total', 'Realized Gain']]
    wages = wages[['Date', 'Total', 'Movimentation']]
    taxes = taxes[['Date', 'Total', 'Movimentation']]

    graph_html = plot_price_history(asset_info)

    movimentation = pd.DataFrame()
    if 'movimentation' in dataframes:
        movimentation = dataframes['movimentation']

    negotiation = pd.DataFrame()
    if 'negotiation' in dataframes:
        negotiation = dataframes['negotiation']

    rent = pd.DataFrame()
    if 'rent_wages' in dataframes:
        rent = dataframes['rent_wages']
        rent = rent[['Date', 'Total', 'Movimentation']]

    news_payload = _build_news_payload(
        asset_info,
        fetch_news=fetch_news,
        analyze_sentiment=analyze_sentiment,
        news_sort=news_sort,
    )

    return render_template(
        'view_asset.html', html_title=f"{asset_info['name']}",
        info=asset_info,
        extended_info=extended_info,
        buys=buys,
        sells=sells,
        wages=wages,
        taxes=taxes,
        movimentation=movimentation,
        graph_html=graph_html,
        rent=rent,
        negotiation=negotiation,
        news=news_payload['news'],
        news_sentiment=news_payload['news_sentiment'],
        news_requested=news_payload['news_requested'],
        sentiment_requested=news_payload['sentiment_requested'],
        news_sort=news_payload['news_sort'],
    )


@app.route('/view/<source>/<asset>', methods=['GET', 'POST'])
def view_asset(source=None, asset=None):
    asset_info = _load_asset_info_or_404(source, asset)

    fetch_news = request.args.get('news') == '1'
    analyze_sentiment = request.args.get('sentiment') == '1'
    news_sort = request.args.get('news_sort', 'date_desc')
    if news_sort not in _ALLOWED_NEWS_SORTS:
        news_sort = 'date_desc'

    return _view_asset_helper(
        asset_info,
        fetch_news=fetch_news,
        analyze_sentiment=analyze_sentiment,
        news_sort=news_sort,
    )


@app.route('/api/view/<source>/<asset>/news', methods=['GET'])
def api_asset_news(source=None, asset=None):
    asset_info = _load_asset_info_or_404(source, asset)

    fetch_news = request.args.get('news', '1') == '1'
    analyze_sentiment_requested = request.args.get('sentiment') == '1'
    preview_only = request.args.get('preview') == '1'
    analyze_sentiment = (
        {'preview_only': True}
        if (analyze_sentiment_requested and preview_only)
        else analyze_sentiment_requested
    )
    news_sort = request.args.get('news_sort', 'date_desc')
    if news_sort not in _ALLOWED_NEWS_SORTS:
        news_sort = 'date_desc'

    payload = _build_news_payload(
        asset_info,
        fetch_news=fetch_news,
        analyze_sentiment=analyze_sentiment,
        news_sort=news_sort,
    )

    if preview_only:
        payload['sentiment_requested'] = False
        payload['sentiment_preview'] = True

    return jsonify(payload)


@app.route('/api/view/<source>/<asset>/analysis', methods=['GET'])
def api_asset_analysis(source=None, asset=None):
    asset_info = _load_asset_info_or_404(source, asset)
    preview_only = request.args.get('preview') == '1'

    if preview_only:
        preview = analyze_asset_performance_with_gemini(asset_info, preview_only=True)
        return jsonify({
            'analysis': None,
            'analysis_requested': False,
            'analysis_preview': True,
            'prompt_preview': (preview or {}).get('prompt') if preview else None,
        })

    analysis = analyze_asset_performance_with_gemini(asset_info)
    # analysis is either a result dict (with 'overall'/'score') or an error dict
    if isinstance(analysis, dict) and 'error' in analysis and 'overall' not in analysis:
        return jsonify({
            'analysis': None,
            'analysis_requested': True,
            'analysis_error': analysis.get('error'),
        })
    return jsonify({'analysis': analysis, 'analysis_requested': True})


@app.route('/history/<source>/<asset>', methods=['GET', 'POST'])
def view_history(asset=None, source=None):
    ret = process_history(asset, source)
    consolidate = ret['consolidate']
    plots = ret['plots']
    return render_template('view_history.html', html_title=f'{asset} history', title=f'{asset}',
                           df=consolidate, plots=plots)

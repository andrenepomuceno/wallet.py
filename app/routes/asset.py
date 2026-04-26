"""Asset detail view + price history view."""
import pandas as pd
from flask import abort, render_template

from app import app
from app.processing import (
    plot_price_history,
    process_avenue_asset_request,
    process_b3_asset_request,
    process_generic_asset_request,
    process_history,
)
from app.utils.serper import search_news


def _view_asset_helper(asset_info):
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

    asset = asset_info['name']
    news_query = asset_info.get('long_name') or asset_info.get('ticker') or asset
    news = search_news(f'{news_query} stock', num=8)
    return render_template(
        'view_asset.html', html_title=f'{asset}',
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
        news=news,
    )


@app.route('/view/<source>/<asset>', methods=['GET', 'POST'])
def view_asset(source=None, asset=None):
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

    return _view_asset_helper(asset_info)


@app.route('/history/<source>/<asset>', methods=['GET', 'POST'])
def view_history(asset=None, source=None):
    ret = process_history(asset, source)
    consolidate = ret['consolidate']
    plots = ret['plots']
    return render_template('view_history.html', html_title=f'{asset} history', title=f'{asset}',
                           df=consolidate, plots=plots)

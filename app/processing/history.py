"""Historical analysis and chart rendering for asset detail."""
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.offline as pyo
import yfinance as yf

from app import app
from app.utils.scraping import usd_exchange_rate

from .assets import (
    consolidate_asset_info,
    process_b3_asset_request,
    process_avenue_asset_request,
    process_generic_asset_request,
)


def plot_price_history(asset_info):
    if 'info' not in asset_info:
        return None

    info = asset_info['info']
    if 'symbol' not in info:
        return None

    stock = yf.Ticker(asset_info['info']['symbol'])
    df = stock.history(start=asset_info['first_buy'], end=asset_info['last_sell'], auto_adjust=False)
    if df is None or df.empty:
        return None

    def add_moving_average(ma_size, df, color='green'):
        ma_name = "MA" + str(ma_size)
        df[ma_name] = df['Close'].rolling(ma_size).mean()
        return go.Scatter(
            x=df.index,
            y=df[ma_name],
            line={'color': color, 'width': 1},
            name=ma_name
        )

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        showlegend=False,
    ))
    fig.add_trace(add_moving_average(20, df, 'blue'))
    fig.add_trace(add_moving_average(100, df, 'cyan'))
    fig.update_layout()
    fig.update_yaxes(autorange=True, fixedrange=False)

    graph_html = pyo.plot(fig, output_type='div')

    return graph_html


def adjust_for_splits(df):
    """Back-adjust historical Close prices for stock splits."""
    adjustment_factor = 1.0

    for index in reversed(df.index):
        if adjustment_factor != 1.0:
            df.at[index, 'Close'] = df.at[index, 'Close'] / adjustment_factor

        split = df.at[index, 'Stock Splits']
        if split and split != 0:
            adjustment_factor *= split

    return df


def plot_history(asset_info, history_df):
    if history_df is None or history_df.empty:
        return [""]
    currency = asset_info.get('currency', 'BRL')
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        name='Rentability',
        x=history_df['date'],
        y=history_df['rentability'],
        line={'color': 'darkblue', 'width': 1},
        yaxis='y1',
    ))
    fig.add_trace(go.Scatter(
        name='Rentability/yr.',
        x=history_df['date'],
        y=history_df['anualized_rentability'],
        line={'color': 'blue', 'width': 1},
        yaxis='y1',
    ))
    fig.add_trace(go.Scatter(
        name='Rent. Slope',
        x=history_df['date'],
        y=history_df['slope'],
        line={'color': 'lightblue', 'width': 1},
        yaxis='y1',
        fill='tozeroy',
    ))

    fig.add_trace(go.Scatter(
        name='Position',
        x=history_df['date'],
        y=history_df['position_total'],
        line={'color': 'darkgreen', 'width': 1},
        yaxis='y2',
    ))
    fig.add_trace(go.Scatter(
        x=history_df['date'],
        y=history_df['liquid_cost'],
        line={'color': 'green', 'width': 1},
        name='Liquid Cost',
        yaxis='y2',
    ))
    fig.add_trace(go.Scatter(
        name='Wages',
        x=history_df['date'],
        y=history_df['wages_sum'],
        line={'color': 'lightgreen', 'width': 1},
        yaxis='y2',
    ))
    fig.add_trace(go.Scatter(
        name='Capital Gain',
        x=history_df['date'],
        y=history_df['capital_gain'],
        line={'color': 'lime', 'width': 1},
        yaxis='y2',
    ))
    fig.add_trace(go.Scatter(
        name='Quantity',
        x=history_df['date'],
        y=history_df['position'],
        line={'color': 'cyan', 'width': 1},
        yaxis='y2',
    ))

    fig.add_trace(go.Scatter(
        x=history_df['date'],
        y=history_df['last_close_price'],
        line={'color': 'red', 'width': 1},
        name='Close Price',
        yaxis='y2',
    ))
    fig.add_trace(go.Scatter(
        x=history_df['date'],
        y=history_df['avg_price'],
        line={'color': 'magenta', 'width': 1},
        name='Average Price',
        yaxis='y2',
    ))

    rangeselector = dict(
        buttons=list([
            dict(count=6,
                 label="6m",
                 step="month",
                 stepmode="backward"),
            dict(count=1,
                 label="YTD",
                 step="year",
                 stepmode="todate"),
            dict(count=1,
                 label="1y",
                 step="year",
                 stepmode="backward"),
            dict(count=2,
                 label="2y",
                 step="year",
                 stepmode="backward"),
            dict(step="all")
        ])
    )
    fig.update_layout(title='',
                      xaxis=dict(rangeslider=dict(visible=True), rangeselector=rangeselector),
                      yaxis=dict(title='Percent (%)', side='right'),
                      yaxis2=dict(title=f'{currency}', overlaying='y', side='left'),
                      yaxis3=dict(title='Quantity', overlaying='y', side='right'),
                      height=800)
    fig.update_yaxes(autorange=True, fixedrange=False)

    fig1 = pyo.plot(fig, output_type='div')

    return [fig1]


def process_history(asset=None, source=None):
    # Late import so tests patching `app.processing.get_online_info` take effect.
    from app import processing

    app.logger.info('process_history')

    ret = {}
    ret['valid'] = False

    asset_info = {}

    if source == 'b3':
        asset_info = process_b3_asset_request(asset)
    elif source == 'avenue':
        asset_info = process_avenue_asset_request(asset)
    elif source == 'generic':
        asset_info = process_generic_asset_request(asset)

    # Ensure required fields
    if 'first_buy' not in asset_info or not asset_info['first_buy']:
        ret['history'] = pd.DataFrame()
        ret['consolidate'] = pd.DataFrame()
        ret['plots'] = []
        ret['valid'] = True
        return ret

    if 'yfinance_ticker' not in asset_info:
        try:
            processing.get_online_info(asset_info.get('ticker', asset), asset_info)
        except Exception as e:
            app.logger.warning('Could not enrich ticker for history: %s', e)

    ticker = asset_info.get('yfinance_ticker', asset_info.get('ticker', asset))
    start_date = datetime.fromisoformat(asset_info['first_buy'])
    history = pd.DataFrame()

    try:
        stock = yf.Ticker(ticker)
        data = stock.history(start=start_date, auto_adjust=False)
    except Exception as e:
        app.logger.error('Error fetching history for %s: %s', ticker, e)
        data = pd.DataFrame()

    if not data.empty and 'Stock Splits' in data.columns:
        data = adjust_for_splits(data)

    if not data.empty and asset_info['name'] in ['BTC', 'ETH']:
        usdbrl = usd_exchange_rate()
        if usdbrl:
            data['Close'] *= usdbrl

    step = 5
    for index in range(len(data) - 1, 0, -step):
        row = data.iloc[index]

        last_date = row.name.to_pydatetime()
        last_date = datetime(last_date.year, last_date.month, last_date.day)

        last_close_price = round(row['Close'], 2)

        asset_info['date'] = last_date
        asset_info['last_close_price'] = last_close_price
        consolidate_asset_info(asset_info['dataframes'], asset_info, last_date, last_close_price)

        new_row = pd.DataFrame([asset_info])
        history = pd.concat([history, new_row], ignore_index=True)

    if len(history) >= 2:
        history['slope'] = -np.gradient(history.rentability).round(2)
        history['position_slope'] = -np.gradient(history.position_total).round(2)
    else:
        history['slope'] = 0
        history['position_slope'] = 0

    cols = ['date', 'last_close_price', 'avg_price', 'position', 'position_total', 'cost',
            'wages_sum', 'liquid_cost', 'capital_gain', 'rentability', 'slope',
            'anualized_rentability', 'age', 'position_slope']
    existing_cols = [c for c in cols if c in history.columns]
    consolidate = history[existing_cols]

    plots = plot_history(asset_info, history)

    ret['history'] = history
    ret['consolidate'] = consolidate
    ret['plots'] = plots

    ret['valid'] = True

    return ret

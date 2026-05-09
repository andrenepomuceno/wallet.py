"""Portfolio-level historical dashboard.

Builds a time-series of consolidated portfolio KPIs (total position, liquid
cost, capital gain, wages and rentability) by sampling every N business days
between a configurable start date and today. Reuses
:func:`consolidate_asset_info` per asset so the math stays identical to the
per-asset history view.
"""
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import plotly.offline as pyo
import yfinance as yf
from dateutil.relativedelta import relativedelta

from app import app
from app.utils.memocache import ttl_memoize
from app.utils.scraping import usd_exchange_rate

from .assets import (
    consolidate_asset_info,
    process_b3_asset_request,
    process_avenue_asset_request,
    process_generic_asset_request,
)
from .consolidate import load_products
from .history import adjust_for_splits


RANGE_KEYS = ('1m', '3m', '6m', 'ytd', '1y', '2y', '5y', 'all')

_SOURCE_PROCESSORS = {
    'b3': process_b3_asset_request,
    'avenue': process_avenue_asset_request,
    'generic': process_generic_asset_request,
}


def _resolve_date_range(range_key, earliest_buy=None):
    """Return ``(start_datetime, end_datetime)`` for a UI range key."""
    end = datetime.now()
    today = datetime(end.year, end.month, end.day)
    rk = (range_key or '1y').lower()

    if rk == '1m':
        start = today - relativedelta(months=1)
    elif rk == '3m':
        start = today - relativedelta(months=3)
    elif rk == '6m':
        start = today - relativedelta(months=6)
    elif rk == 'ytd':
        start = datetime(today.year, 1, 1)
    elif rk == '1y':
        start = today - relativedelta(years=1)
    elif rk == '2y':
        start = today - relativedelta(years=2)
    elif rk == '5y':
        start = today - relativedelta(years=5)
    elif rk == 'all':
        start = earliest_buy or (today - relativedelta(years=10))
    else:
        start = today - relativedelta(years=1)

    return start, today


def _load_all_assets():
    """Return list of asset_info dicts for every asset across sources."""
    assets = []
    for src, processor in _SOURCE_PROCESSORS.items():
        for ticker in load_products(src):
            if not ticker:
                continue
            try:
                info = processor(ticker)
            except Exception as e:  # noqa: BLE001
                app.logger.warning('dashboard: failed to load %s/%s: %s',
                                   src, ticker, e)
                continue
            if not info.get('valid'):
                continue
            # Preserve original currency/asset_class set by the per-source
            # processor — consolidate_asset_info() may overwrite these to
            # 'BRL'/'Sold' on past snapshots when the position is zeroed.
            info['_currency'] = info.get('currency', 'BRL')
            info['_asset_class'] = info.get('asset_class', '')
            assets.append(info)
    return assets


def _filter_assets(assets, scope, class_filter, source_filter, asset_filter):
    if scope == 'class' and class_filter:
        return [a for a in assets if a.get('_asset_class') == class_filter]
    if scope == 'asset' and asset_filter:
        return [a for a in assets
                if a.get('name') == asset_filter
                and (not source_filter or a.get('source') == source_filter)]
    return list(assets)


def _earliest_first_buy(assets):
    dates = []
    for a in assets:
        fb = a.get('first_buy')
        if fb:
            try:
                dates.append(datetime.fromisoformat(fb))
            except ValueError:
                continue
    return min(dates) if dates else None


def _fetch_close_history(ticker, start_date):
    """Return a pandas Series of close prices indexed by date, or ``None``."""
    try:
        data = yf.Ticker(ticker).history(
            start=start_date - timedelta(days=10), auto_adjust=False)
    except Exception as e:  # noqa: BLE001
        app.logger.warning('dashboard: yfinance history failed for %s: %s',
                           ticker, e)
        return None
    if data is None or data.empty or 'Close' not in data.columns:
        return None
    if 'Stock Splits' in data.columns:
        data = adjust_for_splits(data)
    series = data['Close'].copy()
    # Strip timezone so we can index by naive datetimes.
    try:
        series.index = series.index.tz_localize(None)
    except (TypeError, AttributeError):
        pass
    return series


def _lookup_price(series, when):
    """Return the most recent close price on/before ``when``. ``None`` if
    no data is available before that date."""
    if series is None or len(series) == 0:
        return None
    ts = pd.Timestamp(when)
    try:
        ts = ts.tz_localize(None)
    except TypeError:
        pass
    # Use as_of-style lookup: largest index <= ts.
    idx = series.index.searchsorted(ts, side='right') - 1
    if idx < 0:
        return None
    return float(series.iloc[idx])


def _build_sample_dates(start_date, end_date, step_days):
    """Business-day sample dates from ``start_date`` to ``end_date`` (inclusive).

    The end date is appended even if it doesn't fall on the step grid so the
    last point of every chart matches today's snapshot.
    """
    if start_date >= end_date:
        return [pd.Timestamp(end_date)]
    freq = f'{max(int(step_days), 1)}B'
    dates = pd.date_range(start=start_date, end=end_date, freq=freq).tolist()
    end_ts = pd.Timestamp(end_date)
    if not dates or dates[-1] < end_ts:
        dates.append(end_ts)
    return dates


def _aggregate_snapshot(assets, when, price_map, usdbrl_series, fallback_rate):
    """Sum per-asset KPIs at ``when`` and return a single aggregated dict."""
    agg = {
        'date': when,
        'position_total': 0.0,
        'liquid_cost': 0.0,
        'cost': 0.0,
        'wages_sum': 0.0,
        'capital_gain': 0.0,
        'realized_gain': 0.0,
        'not_realized_gain': 0.0,
    }
    for a in assets:
        close_series = price_map.get(id(a))
        close_price = _lookup_price(close_series, when)
        if close_price is None:
            close_price = 0.0

        # Build a shallow copy so consolidate_asset_info doesn't pollute the
        # cached asset record across iterations.
        tmp_info = {
            'ticker': a.get('ticker') or a.get('name'),
            'name': a.get('name'),
            'source': a.get('source'),
        }
        try:
            consolidate_asset_info(a['dataframes'], tmp_info,
                                   when.to_pydatetime() if hasattr(when, 'to_pydatetime') else when,
                                   close_price)
        except Exception as e:  # noqa: BLE001
            app.logger.warning('dashboard: consolidate_asset_info failed for '
                               '%s @ %s: %s', a.get('name'), when, e)
            continue

        rate = 1.0
        if a.get('_currency') == 'USD':
            rate = _lookup_price(usdbrl_series, when) or fallback_rate

        agg['position_total'] += tmp_info.get('position_total', 0.0) * rate
        agg['liquid_cost'] += tmp_info.get('liquid_cost', 0.0) * rate
        agg['cost'] += tmp_info.get('cost', 0.0) * rate
        agg['wages_sum'] += tmp_info.get('wages_sum', 0.0) * rate
        agg['capital_gain'] += tmp_info.get('capital_gain', 0.0) * rate
        agg['realized_gain'] += tmp_info.get('realized_gain', 0.0) * rate
        agg['not_realized_gain'] += tmp_info.get('not_realized_gain', 0.0) * rate

    liquid = agg['liquid_cost']
    agg['rentability'] = 100.0 * (agg['capital_gain'] / liquid) if liquid > 0 else 0.0
    return agg


def compute_period_kpis(history_df):
    """Derive period-level KPIs from a portfolio history DataFrame."""
    kpis = {
        'start_value': 0.0, 'end_value': 0.0,
        'start_cost': 0.0, 'end_cost': 0.0,
        'absolute_return': 0.0,
        'period_change': 0.0,
        'period_pct': 0.0,
        'simple_return_pct': 0.0,
        'wages_sum': 0.0,
        'annual_returns': {},
    }
    if history_df is None or history_df.empty:
        return kpis

    first = history_df.iloc[0]
    last = history_df.iloc[-1]

    kpis['start_value'] = float(first['position_total'])
    kpis['end_value'] = float(last['position_total'])
    kpis['start_cost'] = float(first['liquid_cost'])
    kpis['end_cost'] = float(last['liquid_cost'])
    kpis['wages_sum'] = float(last.get('wages_sum', 0.0))
    kpis['absolute_return'] = kpis['end_value'] - kpis['end_cost']
    kpis['period_change'] = kpis['end_value'] - kpis['start_value']
    if kpis['start_value'] > 0:
        kpis['period_pct'] = 100.0 * (kpis['period_change'] / kpis['start_value'])
    if kpis['end_cost'] > 0:
        kpis['simple_return_pct'] = 100.0 * (
            float(last.get('capital_gain', 0.0)) / kpis['end_cost'])

    # Annual returns: % change in (position_total - liquid_cost) is sensitive
    # to inflows/outflows; we use period_pct of position_total per year as a
    # proxy that is stable when the portfolio is mostly held.
    df = history_df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df['year'] = df['date'].dt.year
    annual = {}
    for year, group in df.groupby('year'):
        if len(group) < 2:
            continue
        start_v = float(group.iloc[0]['position_total'])
        end_v = float(group.iloc[-1]['position_total'])
        start_c = float(group.iloc[0]['liquid_cost'])
        end_c = float(group.iloc[-1]['liquid_cost'])
        # Net contribution during the year (cost variation), used to neutralize
        # inflows when computing the year's market-driven return.
        contributions = end_c - start_c
        denom = start_v + max(contributions, 0.0)
        if denom > 0:
            annual[int(year)] = round(100.0 * (end_v - start_v - contributions) / denom, 2)
    kpis['annual_returns'] = annual
    return kpis


def plot_portfolio_value(history_df, currency='BRL'):
    """Return a Plotly div with two lines (value, cost) and a filled area."""
    if history_df is None or history_df.empty:
        return ''
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        name='Liquid Cost',
        x=history_df['date'],
        y=history_df['liquid_cost'],
        line={'color': '#888', 'width': 1},
        mode='lines',
    ))
    fig.add_trace(go.Scatter(
        name='Portfolio Value',
        x=history_df['date'],
        y=history_df['position_total'],
        line={'color': '#1f77b4', 'width': 2},
        mode='lines',
        fill='tonexty',
        fillcolor='rgba(31,119,180,0.18)',
    ))
    rangeselector = dict(buttons=list([
        dict(count=1, label='1M', step='month', stepmode='backward'),
        dict(count=3, label='3M', step='month', stepmode='backward'),
        dict(count=6, label='6M', step='month', stepmode='backward'),
        dict(count=1, label='YTD', step='year', stepmode='todate'),
        dict(count=1, label='1Y', step='year', stepmode='backward'),
        dict(count=2, label='2Y', step='year', stepmode='backward'),
        dict(count=5, label='5Y', step='year', stepmode='backward'),
        dict(step='all', label='All'),
    ]))
    fig.update_layout(
        xaxis=dict(rangeslider=dict(visible=True), rangeselector=rangeselector),
        yaxis=dict(title=currency),
        height=520,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        margin=dict(l=40, r=20, t=40, b=20),
    )
    return pyo.plot(fig, output_type='div')


def plot_annual_returns(annual_returns):
    if not annual_returns:
        return ''
    years = sorted(annual_returns.keys())
    values = [annual_returns[y] for y in years]
    colors = ['#2ca02c' if v >= 0 else '#d62728' for v in values]
    fig = go.Figure(go.Bar(
        x=[str(y) for y in years],
        y=values,
        marker_color=colors,
        text=[f'{v:.2f}%' for v in values],
        textposition='auto',
    ))
    fig.update_layout(
        yaxis=dict(title='Return (%)'),
        xaxis=dict(title='Year'),
        height=320,
        margin=dict(l=40, r=20, t=20, b=40),
    )
    return pyo.plot(fig, output_type='div')


@ttl_memoize('dashboard')
def process_portfolio_history(scope='total', class_filter=None, source_filter=None,
                              asset_filter=None, range_key='1y', step_days=5):
    """Compute the portfolio time-series for the requested scope and range."""
    app.logger.info('process_portfolio_history scope=%s class=%s source=%s '
                    'asset=%s range=%s', scope, class_filter, source_filter,
                    asset_filter, range_key)

    ret = {'valid': False, 'history': pd.DataFrame(), 'kpis': {},
           'plots': {'value': '', 'annual': ''},
           'scope': scope, 'class_filter': class_filter,
           'source_filter': source_filter, 'asset_filter': asset_filter,
           'range_key': range_key}

    all_assets = _load_all_assets()
    if not all_assets:
        return ret

    ret['available_classes'] = sorted({a.get('_asset_class') for a in all_assets
                                       if a.get('_asset_class')})
    ret['available_assets'] = sorted({(a.get('source'), a.get('name'))
                                      for a in all_assets if a.get('name')})

    selected = _filter_assets(all_assets, scope, class_filter, source_filter,
                              asset_filter)
    if not selected:
        return ret

    earliest_buy = _earliest_first_buy(selected)
    start_date, end_date = _resolve_date_range(range_key, earliest_buy)
    if earliest_buy is not None and start_date < earliest_buy:
        start_date = earliest_buy
    # Step a few days back so the very first sample has at least one
    # transaction included; consolidate_asset_info() filters by `until_date`.
    if start_date >= end_date:
        start_date = end_date - timedelta(days=1)

    # Pre-fetch yfinance close history per asset.
    price_map = {}
    for a in selected:
        ticker = a.get('yfinance_ticker') or a.get('ticker') or a.get('name')
        price_map[id(a)] = _fetch_close_history(ticker, start_date) if ticker else None

    # USD/BRL historical series (best-effort).
    usdbrl_series = None
    if any(a.get('_currency') == 'USD' for a in selected):
        try:
            data = yf.Ticker('BRL=X').history(
                start=start_date - timedelta(days=10), auto_adjust=False)
            if data is not None and not data.empty and 'Close' in data.columns:
                series = data['Close'].copy()
                try:
                    series.index = series.index.tz_localize(None)
                except (TypeError, AttributeError):
                    pass
                usdbrl_series = series
        except Exception as e:  # noqa: BLE001
            app.logger.warning('dashboard: USD/BRL history failed: %s', e)
    fallback_rate = usd_exchange_rate('BRL') or 1.0

    sample_dates = _build_sample_dates(start_date, end_date, step_days)

    rows = []
    for when in sample_dates:
        rows.append(_aggregate_snapshot(selected, when, price_map,
                                        usdbrl_series, fallback_rate))
    history_df = pd.DataFrame(rows)

    # Round display columns.
    for col in ('position_total', 'liquid_cost', 'cost', 'wages_sum',
                'capital_gain', 'realized_gain', 'not_realized_gain',
                'rentability'):
        if col in history_df.columns:
            history_df[col] = history_df[col].round(2)

    kpis = compute_period_kpis(history_df)
    ret['valid'] = True
    ret['history'] = history_df
    ret['kpis'] = kpis
    ret['plots']['value'] = plot_portfolio_value(history_df, currency='BRL')
    ret['plots']['annual'] = plot_annual_returns(kpis.get('annual_returns', {}))
    return ret

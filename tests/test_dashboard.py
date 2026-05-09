"""Tests for app.processing.dashboard."""
from datetime import datetime
from unittest.mock import patch

import pandas as pd
import pytest

from app import db
from app.models import Transaction
from app.processing import (
    compute_period_kpis,
    plot_annual_returns,
    plot_portfolio_value,
    process_portfolio_history,
)
from app.processing.dashboard import (
    _build_sample_dates,
    _lookup_price,
    _resolve_date_range,
)


pytestmark = pytest.mark.usefixtures("request_ctx")


# ---------------------------------------------------------------------------
# Range resolution
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('rk', ['1m', '3m', '6m', 'ytd', '1y', '2y', '5y', 'all'])
def test_resolve_date_range_returns_pair(rk):
    start, end = _resolve_date_range(rk, earliest_buy=datetime(2020, 1, 1))
    assert isinstance(start, datetime) and isinstance(end, datetime)
    assert start <= end


def test_resolve_date_range_all_uses_earliest_buy():
    start, _ = _resolve_date_range('all', earliest_buy=datetime(2015, 6, 1))
    assert start == datetime(2015, 6, 1)


def test_resolve_date_range_unknown_falls_back_to_1y():
    start, end = _resolve_date_range('garbage')
    assert (end - start).days >= 360


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def test_lookup_price_returns_most_recent_value():
    series = pd.Series(
        [10.0, 11.0, 12.0],
        index=pd.to_datetime(['2024-01-01', '2024-01-05', '2024-01-10']),
    )
    assert _lookup_price(series, datetime(2024, 1, 7)) == 11.0
    assert _lookup_price(series, datetime(2024, 1, 10)) == 12.0


def test_lookup_price_before_data_returns_none():
    series = pd.Series([10.0], index=pd.to_datetime(['2024-01-05']))
    assert _lookup_price(series, datetime(2024, 1, 1)) is None


def test_lookup_price_handles_empty_series():
    assert _lookup_price(None, datetime(2024, 1, 1)) is None
    assert _lookup_price(pd.Series(dtype=float), datetime(2024, 1, 1)) is None


def test_build_sample_dates_includes_endpoint():
    start = datetime(2024, 1, 1)
    end = datetime(2024, 2, 1)
    dates = _build_sample_dates(start, end, step_days=5)
    assert len(dates) >= 2
    assert pd.Timestamp(end) == dates[-1]


def test_build_sample_dates_collapsed_when_range_is_zero():
    end = datetime(2024, 5, 1)
    dates = _build_sample_dates(end, end, step_days=5)
    assert dates == [pd.Timestamp(end)]


# ---------------------------------------------------------------------------
# compute_period_kpis
# ---------------------------------------------------------------------------

def test_compute_period_kpis_empty():
    out = compute_period_kpis(pd.DataFrame())
    assert out['absolute_return'] == 0.0
    assert out['period_pct'] == 0.0
    assert out['annual_returns'] == {}


def test_compute_period_kpis_basic_profit():
    df = pd.DataFrame([
        {'date': pd.Timestamp('2024-01-02'), 'position_total': 1000.0,
         'liquid_cost': 800.0, 'capital_gain': 200.0, 'wages_sum': 0.0},
        {'date': pd.Timestamp('2024-12-30'), 'position_total': 1500.0,
         'liquid_cost': 800.0, 'capital_gain': 700.0, 'wages_sum': 30.0},
    ])
    k = compute_period_kpis(df)
    assert k['start_value'] == 1000.0
    assert k['end_value'] == 1500.0
    assert k['absolute_return'] == 700.0           # 1500 - 800
    assert k['period_change'] == 500.0             # 1500 - 1000
    assert k['period_pct'] == pytest.approx(50.0)
    # capital_gain / end_cost
    assert k['simple_return_pct'] == pytest.approx(700.0 / 800.0 * 100.0)
    assert 2024 in k['annual_returns']


def test_compute_period_kpis_handles_zero_cost():
    df = pd.DataFrame([
        {'date': pd.Timestamp('2024-01-02'), 'position_total': 0.0,
         'liquid_cost': 0.0, 'capital_gain': 0.0, 'wages_sum': 0.0},
        {'date': pd.Timestamp('2024-12-30'), 'position_total': 0.0,
         'liquid_cost': 0.0, 'capital_gain': 0.0, 'wages_sum': 0.0},
    ])
    k = compute_period_kpis(df)
    assert k['period_pct'] == 0.0
    assert k['simple_return_pct'] == 0.0


# ---------------------------------------------------------------------------
# Plot helpers (smoke)
# ---------------------------------------------------------------------------

def test_plot_portfolio_value_returns_div():
    df = pd.DataFrame([
        {'date': pd.Timestamp('2024-01-02'), 'position_total': 10.0,
         'liquid_cost': 8.0},
        {'date': pd.Timestamp('2024-02-02'), 'position_total': 12.0,
         'liquid_cost': 8.0},
    ])
    out = plot_portfolio_value(df)
    assert isinstance(out, str)
    assert '<div' in out


def test_plot_portfolio_value_empty_returns_empty_string():
    assert plot_portfolio_value(pd.DataFrame()) == ''


def test_plot_annual_returns_renders_when_present():
    out = plot_annual_returns({2023: 5.0, 2024: -2.5})
    assert '<div' in out


def test_plot_annual_returns_empty():
    assert plot_annual_returns({}) == ''


# ---------------------------------------------------------------------------
# process_portfolio_history (integration with mocked yfinance + DB rows)
# ---------------------------------------------------------------------------

def _seed_generic_buys(asset='AAA', qty=10, price=5.0, date='2024-01-02'):
    db.session.add(Transaction(
        origin_id=f'g-{asset}-{date}', source='generic', record_type='extract',
        date=date, asset=asset, product=asset,
        raw_label='Buy', category='BUY', direction='Credito',
        quantity=qty, price=price, total=qty * price, currency='BRL',
    ))
    db.session.commit()


class _FakeTicker:
    """Minimal stand-in for yf.Ticker used by dashboard internals."""

    def __init__(self, ticker):
        self.ticker = ticker

    def history(self, start=None, end=None, auto_adjust=False):
        # Return a couple of months of synthetic closes.
        idx = pd.date_range('2024-01-02', '2024-06-28', freq='5B')
        prices = pd.Series(range(10, 10 + len(idx)), index=idx, dtype=float)
        return pd.DataFrame({'Close': prices})


def test_process_portfolio_history_empty_returns_invalid(db_session):
    # Disable cache so each test starts fresh.
    from app.utils.memocache import invalidate_processing_cache
    invalidate_processing_cache(category='dashboard')
    out = process_portfolio_history(scope='total', range_key='1y')
    assert out['valid'] is False


def test_process_portfolio_history_total_with_one_asset(db_session):
    from app.utils.memocache import invalidate_processing_cache
    invalidate_processing_cache(category='dashboard')
    invalidate_processing_cache(category='asset')
    invalidate_processing_cache(category='consolidate')

    _seed_generic_buys(asset='AAA', qty=10, price=5.0, date='2024-01-02')

    with patch('app.processing.get_online_info') as mock_online, \
         patch('app.processing.dashboard.yf.Ticker', _FakeTicker):
        mock_online.side_effect = lambda t, info: info.update(
            {'last_close_price': 6.0, 'currency': 'BRL', 'asset_class': 'Generic'}
        ) or info
        out = process_portfolio_history(scope='total', range_key='6m')

    assert out['valid'] is True
    history = out['history']
    assert not history.empty
    expected_cols = {'date', 'position_total', 'liquid_cost', 'cost',
                     'capital_gain', 'rentability'}
    assert expected_cols.issubset(set(history.columns))
    # End value should be position * last fake close.
    assert history.iloc[-1]['position_total'] > 0


def test_process_portfolio_history_class_filter_excludes_others(db_session):
    from app.utils.memocache import invalidate_processing_cache
    invalidate_processing_cache(category='dashboard')
    invalidate_processing_cache(category='asset')
    invalidate_processing_cache(category='consolidate')

    _seed_generic_buys(asset='AAA', qty=10, price=5.0, date='2024-01-02')

    with patch('app.processing.get_online_info') as mock_online, \
         patch('app.processing.dashboard.yf.Ticker', _FakeTicker):
        mock_online.side_effect = lambda t, info: info.update(
            {'last_close_price': 6.0, 'currency': 'BRL', 'asset_class': 'Generic'}
        ) or info
        out = process_portfolio_history(scope='class', class_filter='Equity',
                                        range_key='6m')

    # No assets match the 'Equity' class -> invalid.
    assert out['valid'] is False
    assert 'Generic' in out.get('available_classes', [])

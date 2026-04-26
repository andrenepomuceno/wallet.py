import pandas as pd
import pytest
import numpy as np
from unittest.mock import patch

from app import db
from app.models import Transaction
from app.processing import (
    calc_avg_price,
    consolidate_asset_info,
    process_b3_asset_request,
    process_avenue_asset_request,
    process_generic_asset_request,
    process_b3_movimentation_request,
    process_b3_negotiation_request,
    process_avenue_extract_request,
    process_generic_extract_request,
    process_consolidate_request,
    adjust_for_splits,
    merge_movimentation_negotiation,
    consolidate_total,
    consolidate_group,
    load_products,
    load_consolidate,
    _extract_json_object,
)


pytestmark = pytest.mark.usefixtures("request_ctx")


def test_calc_avg_price_basic():
    df = pd.DataFrame({'Quantity': [10, 20], 'Price': [10.0, 20.0]})
    # avg = (10*10 + 20*20) / 30 = 500/30
    assert calc_avg_price(df) == pytest.approx(500.0 / 30.0)


def test_calc_avg_price_zero_quantity():
    df = pd.DataFrame({'Quantity': [], 'Price': []})
    assert calc_avg_price(df) == 0


def test_consolidate_asset_info_basic():
    buys = pd.DataFrame({
        'Date': pd.to_datetime(['2024-01-01', '2024-02-01']),
        'Quantity': [10.0, 10.0],
        'Price': [10.0, 20.0],
        'Total': [100.0, 200.0],
        'Movimentation': ['Compra', 'Compra'],
    })
    sells = pd.DataFrame({
        'Date': pd.to_datetime(['2024-03-01']),
        'Quantity': [-5.0],
        'Price': [25.0],
        'Total': [-125.0],
        'Movimentation': ['Venda'],
    })
    wages = pd.DataFrame({
        'Date': pd.to_datetime(['2024-02-15']),
        'Total': [10.0],
    })
    taxes = pd.DataFrame({
        'Date': pd.to_datetime(['2024-03-02']),
        'Total': [2.0],
    })
    asset_info = {'ticker': 'TEST'}
    dfs = {'buys': buys, 'sells': sells, 'wages': wages, 'taxes': taxes}
    out = consolidate_asset_info(dfs, asset_info,
                                 until_date=pd.Timestamp('2024-04-01'),
                                 date_close_price=30.0)
    assert out['buy_quantity'] == 20.0
    assert out['sell_quantity'] == 5.0
    assert out['position'] == 15.0
    assert out['avg_price'] == pytest.approx(15.0)  # (100+200)/20
    assert out['cost'] == 300.0
    # Realized: (25 - 15) * 5 = 50
    assert out['realized_gain'] == 50.0
    # Not realized: (30 - 15) * 15 = 225
    assert out['not_realized_gain'] == 225.0
    # liquid_cost = 300 - 10 + 2 = 292
    assert out['liquid_cost'] == 292.0
    assert out['valid'] is True


def test_consolidate_asset_info_sold_out():
    buys = pd.DataFrame({
        'Date': pd.to_datetime(['2024-01-01']),
        'Quantity': [10.0], 'Price': [10.0], 'Total': [100.0],
        'Movimentation': ['Compra'],
    })
    sells = pd.DataFrame({
        'Date': pd.to_datetime(['2024-02-01']),
        'Quantity': [-10.0], 'Price': [15.0], 'Total': [-150.0],
        'Movimentation': ['Venda'],
    })
    empty = pd.DataFrame({'Date': pd.to_datetime([]), 'Total': []})
    out = consolidate_asset_info(
        {'buys': buys, 'sells': sells, 'wages': empty, 'taxes': empty},
        {'ticker': 'X'},
    )
    assert out['position'] == 0
    assert out['asset_class'] == 'Sold'


def test_adjust_for_splits():
    # Three days; on day 2 a 2:1 split occurs. Pre-split close should be /2.
    df = pd.DataFrame({
        'Close': [100.0, 50.0, 50.0],
        'Stock Splits': [0.0, 2.0, 0.0],
    })
    out = adjust_for_splits(df.copy())
    # Day 0 (before split): 100 / 2 = 50
    assert out.iloc[0]['Close'] == pytest.approx(50.0)
    # Day 1 (split day onwards): unchanged
    assert out.iloc[1]['Close'] == pytest.approx(50.0)
    assert out.iloc[2]['Close'] == pytest.approx(50.0)


def test_merge_movimentation_negotiation():
    mov = pd.DataFrame({
        'Date': pd.to_datetime(['2024-01-01']),
        'Movimentation': ['Compra'], 'Quantity': [10],
        'Price': [10.0], 'Total': [100.0],
        'Produto': ['PETR4'], 'Asset': ['PETR4'],
    })
    neg = pd.DataFrame({
        'Date': pd.to_datetime(['2024-01-02']),
        'Quantidade': [5], 'Preço': [11.0], 'Valor': [55.0],
        'Código de Negociação': ['PETR4'], 'Asset': ['PETR4'],
    })
    # Negotiation df after sql_to_df has these renamed already; emulate raw
    neg = neg.rename(columns={
        'Quantidade': 'Quantity',
    })
    merged = merge_movimentation_negotiation(mov, neg, 'Compra')
    assert len(merged) == 2


def test_consolidate_total_handles_zero_liquid():
    df = pd.DataFrame({'liquid_cost': [0.0], 'capital_gain': [0.0]})
    out = consolidate_total(df)
    assert out['rentability'] == 0


@patch('app.processing.get_online_info')
def test_process_b3_asset_request(mock_online, db_session):
    mock_online.side_effect = lambda t, info: info.update({'last_close_price': 50.0}) or info
    db.session.add(Transaction(
        origin_id='m1', source='b3', record_type='movimentation',
        date='2024-01-15', asset='PETR4', product='PETR4 - PETROBRAS',
        institution='X', raw_label='Compra', category='BUY',
        direction='Credito', quantity=100, price=10.0, total=1000.0,
        currency='BRL',
    ))
    db.session.add(Transaction(
        origin_id='m2', source='b3', record_type='movimentation',
        date='2024-02-15', asset='PETR4', product='PETR4 - PETROBRAS',
        institution='X', raw_label='Dividendo', category='DIVIDEND',
        direction='Credito', quantity=0, price=0, total=25.0,
        currency='BRL',
    ))
    db.session.commit()
    info = process_b3_asset_request('PETR4')
    assert info['valid'] is True
    assert info['ticker'] == 'PETR4'
    assert info['position'] == 100.0
    assert info['wages_sum'] == 25.0


@patch('app.processing.get_online_info')
def test_process_avenue_asset_request(mock_online, db_session):
    mock_online.side_effect = lambda t, info: info.update({'last_close_price': 220.0}) or info
    db.session.add(Transaction(
        origin_id='a1', source='avenue', record_type='extract',
        date='2024-03-01', settlement_date='2024-03-03', time='',
        asset='NVDA', product='NVDA',
        description='Compra de 5 NVDA a $ 200,00 cada',
        raw_label='Compra', category='BUY', direction='Credito',
        quantity=5, price=200.0, total=-1000.0, balance=0.0,
        currency='USD',
    ))
    db.session.commit()
    info = process_avenue_asset_request('NVDA')
    assert info['valid'] is True
    assert info['ticker'] == 'NVDA'
    assert info['position'] == 5.0
    assert info['currency'] == 'USD'


@patch('app.processing.get_online_info')
def test_process_generic_asset_request(mock_online, db_session):
    mock_online.side_effect = lambda t, info: info.update({'last_close_price': 7.0}) or info
    db.session.add(Transaction(
        origin_id='g1', source='generic', record_type='extract',
        date='2024-01-01', asset='AAA', product='AAA',
        raw_label='Buy', category='BUY', direction='Credito',
        quantity=10, price=5.0, total=50.0, currency='BRL',
    ))
    db.session.commit()
    info = process_generic_asset_request('AAA')
    assert info['valid'] is True
    assert info['position'] == 10.0


def test_process_consolidate_request_empty(db_session):
    out = process_consolidate_request()
    assert out['valid'] is False


def test_process_request_helpers_empty(db_session):
    # Just exercise the request handlers with empty DB
    class FakeReq:
        method = 'GET'
    df = process_b3_movimentation_request(FakeReq())
    assert df.empty
    assert process_b3_negotiation_request().empty
    assert process_avenue_extract_request().empty
    assert process_generic_extract_request().empty


def test_load_products_and_consolidate(db_session):
    db.session.add(Transaction(
        origin_id='g1', source='generic', record_type='extract',
        date='2024-01-01', asset='AAA', product='AAA',
        raw_label='Buy', category='BUY', direction='Credito',
        quantity=10, price=5.0, total=50.0, currency='BRL',
    ))
    db.session.commit()
    products = load_products('generic')
    assert 'AAA' in products

    with patch('app.processing.get_online_info') as mock_online:
        mock_online.side_effect = lambda t, info: info.update({'last_close_price': 6.0}) or info
        df = load_consolidate(['AAA'], process_generic_asset_request, 'generic')
    assert len(df) == 1
    assert 'url' in df.columns


@pytest.mark.parametrize("raw,expected", [
    ('```json\n{"ticker": "PETR4.SA"}\n```', '{"ticker": "PETR4.SA"}'),
    ('Sure, here: {"ticker": "AAPL"} thanks', '{"ticker": "AAPL"}'),
    ('plain text', None),
    (None, None),
])
def test_extract_json_object(raw, expected):
    assert _extract_json_object(raw) == expected

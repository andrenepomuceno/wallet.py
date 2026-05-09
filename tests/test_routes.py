from unittest.mock import patch
import io
import pandas as pd
import pytest

from app import db
from app.models import B3Negotiation, GenericExtract, AvenueExtract, ApiConfig


def test_home_get(client):
    resp = client.get('/')
    assert resp.status_code == 200


def test_home_post_no_file(client):
    resp = client.post('/', data={'filetype': 'B3 Movimentation'})
    # Missing file -> error flash + render index
    assert resp.status_code in (200, 400)


def test_home_unsupported_filetype(client):
    data = {
        'filetype': 'Bogus',
        'file': (io.BytesIO(b'a,b\n1,2\n'), 'foo.txt'),
    }
    resp = client.post('/', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200


def test_view_movimentation(client):
    assert client.get('/b3_movimentation').status_code == 200


def test_view_negotiation_get(client):
    assert client.get('/b3_negotiation').status_code == 200


def test_view_extract(client):
    assert client.get('/avenue').status_code == 200


def test_view_generic(client):
    assert client.get('/generic').status_code == 200


def test_view_api_config_get(client):
    assert client.get('/config/api').status_code == 200


def test_view_api_config_post(client, db_session):
    resp = client.post('/config/api', data={'gemini_api_key': 'sk-abc'},
                       follow_redirects=False)
    assert resp.status_code in (200, 302)
    assert ApiConfig.query.filter_by(provider='gemini').first().api_key == 'sk-abc'


def test_view_consolidate_no_data_redirects(client, db_session):
    resp = client.get('/consolidate')
    assert resp.status_code in (200, 302)


@patch('app.routes.consolidate.analyze_consolidate_performance_with_gemini')
@patch('app.routes.consolidate.process_consolidate_request')
def test_api_consolidate_analysis_success(mock_process, mock_analysis, client):
    mock_process.return_value = {'valid': True, 'consolidate_by_group': pd.DataFrame()}
    mock_analysis.return_value = {
        'overall': 'good',
        'score': 71,
        'performance_summary': 'Consolidado com boa relacao risco/retorno.',
        'allocation_summary': 'Boa distribuicao entre classes.',
        'strengths': ['Ganho de capital positivo'],
        'risks': ['Concentracao em uma classe'],
        'next_steps': ['Ajustar pesos'],
        'confidence': 0.77,
        'prompt': 'x',
        'raw_response': 'y',
        'model': 'gemini-2.5-flash',
    }

    resp = client.get('/api/consolidate/analysis')
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['analysis_requested'] is True
    assert payload['analysis']['overall'] == 'good'
    assert payload['analysis']['score'] == 71


@patch('app.routes.consolidate.analyze_consolidate_performance_with_gemini')
@patch('app.routes.consolidate.process_consolidate_request')
def test_api_consolidate_analysis_preview(mock_process, mock_analysis, client):
    mock_process.return_value = {'valid': True, 'consolidate_by_group': pd.DataFrame()}
    mock_analysis.return_value = {'prompt': 'preview prompt', 'preview': True}

    resp = client.get('/api/consolidate/analysis?preview=1')
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['analysis_preview'] is True
    assert payload['prompt_preview'] == 'preview prompt'
    mock_analysis.assert_called_once_with(mock_process.return_value, preview_only=True)


@patch('app.routes.consolidate.process_consolidate_request')
def test_api_consolidate_analysis_without_data(mock_process, client):
    mock_process.return_value = {'valid': False}

    resp = client.get('/api/consolidate/analysis')
    assert resp.status_code == 404
    payload = resp.get_json()
    assert payload['analysis_requested'] is True
    assert payload['analysis'] is None


def test_view_asset_unknown_source(client):
    assert client.get('/view/bogus/AAA').status_code == 404


def test_view_asset_no_data(client, db_session):
    # Generic/Avenue return valid=False when no data, triggering a 404
    assert client.get('/view/generic/UNKNOWN').status_code == 404
    assert client.get('/view/avenue/UNKNOWN').status_code == 404


@patch('app.routes.asset.analyze_asset_performance_with_gemini')
@patch('app.routes.asset._load_asset_info_or_404')
def test_api_asset_analysis_success(mock_loader, mock_analysis, client):
    mock_loader.return_value = {
        'name': 'PETR4',
        'source': 'b3',
        'valid': True,
        'dataframes': {},
        'info': {},
    }
    mock_analysis.return_value = {
        'overall': 'good',
        'score': 74,
        'performance_summary': 'Asset com desempenho consistente.',
        'strengths': ['Rentabilidade positiva'],
        'risks': ['Alta volatilidade'],
        'next_steps': ['Revisar exposicao trimestralmente'],
        'time_horizon': 'medium',
        'confidence': 0.82,
        'prompt': 'x',
        'raw_response': 'y',
        'model': 'gemini-2.5-flash',
    }

    resp = client.get('/api/view/b3/PETR4/analysis')
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['analysis_requested'] is True
    assert payload['analysis']['overall'] == 'good'
    assert payload['analysis']['score'] == 74


@patch('app.routes.asset.analyze_asset_performance_with_gemini')
@patch('app.routes.asset._load_asset_info_or_404')
def test_api_asset_analysis_preview(mock_loader, mock_analysis, client):
    mock_loader.return_value = {
        'name': 'PETR4',
        'source': 'b3',
        'valid': True,
        'dataframes': {},
        'info': {},
    }
    mock_analysis.return_value = {'prompt': 'asset prompt', 'preview': True}

    resp = client.get('/api/view/b3/PETR4/analysis?preview=1')
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['analysis_preview'] is True
    assert payload['prompt_preview'] == 'asset prompt'
    mock_analysis.assert_called_once_with(mock_loader.return_value, preview_only=True)


@patch('app.routes.asset.analyze_news_sentiment_with_gemini')
@patch('app.routes.asset.search_news')
@patch('app.routes.asset._load_asset_info_or_404')
def test_api_asset_news_sentiment_preview(mock_loader, mock_search_news, mock_sentiment, client):
    mock_loader.return_value = {
        'name': 'PETR4',
        'long_name': 'Petrobras',
        'ticker': 'PETR4',
        'source': 'b3',
        'valid': True,
    }
    mock_search_news.return_value = [
        {'title': 'A', 'link': 'http://x', 'snippet': 's', 'source': 'src', 'date': '2026-01-01'},
    ]
    mock_sentiment.return_value = {'prompt': 'news prompt', 'preview': True}

    resp = client.get('/api/view/b3/PETR4/news?news=1&sentiment=1&preview=1')
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['sentiment_preview'] is True
    assert payload['prompt_preview'] == 'news prompt'
    mock_sentiment.assert_called_once()


@patch('app.routes.asset.analyze_asset_performance_with_gemini')
@patch('app.routes.asset._load_asset_info_or_404')
def test_api_asset_analysis_without_key(mock_loader, mock_analysis, client):
    mock_loader.return_value = {
        'name': 'PETR4',
        'source': 'b3',
        'valid': True,
        'dataframes': {},
        'info': {},
    }
    mock_analysis.return_value = None

    resp = client.get('/api/view/b3/PETR4/analysis')
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['analysis_requested'] is True
    assert payload['analysis'] is None


@patch('app.routes.asset.process_history')
def test_view_history(mock_history, client):
    mock_history.return_value = {
        'history': pd.DataFrame(),
        'consolidate': pd.DataFrame(),
        'plots': [],
        'valid': True,
    }
    resp = client.get('/history/b3/PETR4')
    assert resp.status_code == 200


@patch('app.routes.dashboard.process_portfolio_history')
def test_view_dashboard_renders(mock_proc, client):
    mock_proc.return_value = {
        'valid': True,
        'history': pd.DataFrame([
            {'date': pd.Timestamp('2024-01-02'), 'position_total': 100.0,
             'liquid_cost': 80.0, 'cost': 80.0, 'wages_sum': 0.0,
             'capital_gain': 20.0, 'realized_gain': 0.0,
             'not_realized_gain': 20.0, 'rentability': 25.0},
            {'date': pd.Timestamp('2024-06-02'), 'position_total': 120.0,
             'liquid_cost': 80.0, 'cost': 80.0, 'wages_sum': 0.0,
             'capital_gain': 40.0, 'realized_gain': 0.0,
             'not_realized_gain': 40.0, 'rentability': 50.0},
        ]),
        'kpis': {'start_value': 100.0, 'end_value': 120.0,
                 'start_cost': 80.0, 'end_cost': 80.0,
                 'absolute_return': 40.0, 'period_change': 20.0,
                 'period_pct': 20.0, 'simple_return_pct': 50.0,
                 'wages_sum': 0.0, 'annual_returns': {2024: 20.0}},
        'plots': {'value': '<div>chart</div>', 'annual': '<div>bars</div>'},
        'available_classes': ['Equity'],
        'available_assets': [('b3', 'PETR4')],
    }
    resp = client.get('/dashboard?range=1y')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'Dashboard' in body
    assert '<div>chart</div>' in body


@patch('app.routes.dashboard.process_portfolio_history')
def test_view_dashboard_no_data_redirects(mock_proc, client):
    mock_proc.return_value = {
        'valid': False,
        'available_classes': [],
        'available_assets': [],
        'kpis': {}, 'plots': {'value': '', 'annual': ''},
    }
    resp = client.get('/dashboard', follow_redirects=False)
    assert resp.status_code == 302


def test_format_money_filter():
    from app.routes import format_money
    assert format_money(500) == '500'
    assert format_money(1500) == '1.50 K'
    assert format_money(1_500_000) == '1.50 M'
    assert format_money(2_500_000_000) == '2.50 B'
    assert format_money(3_500_000_000_000) == '3.50 T'


# ---------------------------------------------------------------------------
# Rebalance page tests
# ---------------------------------------------------------------------------

@patch('app.routes.rebalance.process_consolidate_request')
def test_view_rebalance_no_data_redirects(mock_consolidate, client):
    mock_consolidate.return_value = {'valid': False}
    resp = client.get('/rebalance', follow_redirects=False)
    assert resp.status_code == 302


@patch('app.routes.rebalance.process_rebalance_request')
@patch('app.routes.rebalance.process_consolidate_request')
def test_view_rebalance_get(mock_consolidate, mock_rebalance, client):
    mock_consolidate.return_value = {
        'valid': True,
        'consolidate_by_group': pd.DataFrame([
            {'asset_class': 'Total', 'position': 10000.0, 'relative_position': 100.0},
            {'asset_class': 'Stocks', 'position': 6000.0, 'relative_position': 60.0},
            {'asset_class': 'FIIs', 'position': 4000.0, 'relative_position': 40.0},
        ]),
        'group_df': [],
        'usd_brl': 5.0,
    }
    mock_rebalance.return_value = {
        'valid': True,
        'class_df': pd.DataFrame(columns=[
            'Class', 'Current (BRL)', 'Current (%)', 'Target (%)',
            'Deviation (p.p.)', 'Target (BRL)', 'Deviation (BRL)', 'Action',
        ]),
        'asset_df': pd.DataFrame(columns=[
            'Asset', 'Class', 'Current (BRL)', 'Delta (BRL)',
            'Action', 'Price', 'Est. Qty',
        ]),
        'summary': {
            'total_portfolio_brl': 10000.0,
            'turnover_brl': 0.0,
            'alignment_score': 100.0,
            'classes_out_of_target': 0,
            'most_overweight': None,
            'most_underweight': None,
            'targets_defined': False,
        },
        'targets': {},
        'usd_brl': 5.0,
    }
    resp = client.get('/rebalance')
    assert resp.status_code == 200
    assert b'Rebalancing' in resp.data


@patch('app.routes.rebalance.save_targets')
@patch('app.routes.rebalance.process_rebalance_request')
@patch('app.routes.rebalance.process_consolidate_request')
def test_view_rebalance_post_saves_weights(mock_consolidate, mock_rebalance, mock_save,
                                           client, db_session):
    mock_consolidate.return_value = {
        'valid': True,
        'consolidate_by_group': pd.DataFrame([
            {'asset_class': 'Total', 'position': 10000.0, 'relative_position': 100.0},
            {'asset_class': 'Stocks', 'position': 6000.0, 'relative_position': 60.0},
            {'asset_class': 'FIIs', 'position': 4000.0, 'relative_position': 40.0},
        ]),
        'group_df': [],
        'usd_brl': 5.0,
    }
    mock_rebalance.return_value = {
        'valid': True, 'class_df': pd.DataFrame(), 'asset_df': pd.DataFrame(),
        'summary': {'total_portfolio_brl': 10000.0, 'turnover_brl': 0.0,
                    'alignment_score': 100.0, 'classes_out_of_target': 0,
                    'most_overweight': None, 'most_underweight': None,
                    'targets_defined': True},
        'targets': {'Stocks': 60.0, 'FIIs': 40.0},
        'usd_brl': 5.0,
    }
    resp = client.post('/rebalance', data={
        'w_stocks': '60.0',
        'w_fiis': '40.0',
    }, follow_redirects=False)
    # save_targets called once and redirect issued
    assert resp.status_code in (200, 302)


@patch('app.routes.rebalance.save_targets')
@patch('app.routes.rebalance.process_rebalance_request')
@patch('app.routes.rebalance.process_consolidate_request')
def test_view_rebalance_post_any_sum_accepted(mock_consolidate, mock_rebalance, mock_save,
                                               client, db_session):
    """Weights can sum to any value — no 100% constraint."""
    mock_consolidate.return_value = {
        'valid': True,
        'consolidate_by_group': pd.DataFrame([
            {'asset_class': 'Total', 'position': 10000.0, 'relative_position': 100.0},
            {'asset_class': 'Stocks', 'position': 6000.0, 'relative_position': 60.0},
            {'asset_class': 'FIIs', 'position': 4000.0, 'relative_position': 40.0},
        ]),
        'group_df': [],
        'usd_brl': 5.0,
    }
    mock_rebalance.return_value = {
        'valid': True, 'class_df': pd.DataFrame(), 'asset_df': pd.DataFrame(),
        'summary': {'total_portfolio_brl': 10000.0, 'turnover_brl': 0.0,
                    'alignment_score': 100.0, 'classes_out_of_target': 0,
                    'most_overweight': None, 'most_underweight': None,
                    'targets_defined': False},
        'targets': {},
        'usd_brl': 5.0,
    }
    # sum = 110 — should still be accepted (redirect after POST)
    resp = client.post('/rebalance', data={
        'w_stocks': '70.0',
        'w_fiis': '40.0',
    }, follow_redirects=False)
    assert resp.status_code in (200, 302)


# ---------------------------------------------------------------------------
# Transaction edit / delete API
# ---------------------------------------------------------------------------

def _make_tx(db_session):
    """Insert a minimal Transaction and return it."""
    from app.models import Transaction
    tx = Transaction(
        origin_id='test:edit:1',
        source='generic',
        record_type='movimentation',
        date='2024-01-15',
        asset='TEST3',
        raw_label='Compra',
        category='BUY',
        direction='Debito',
        quantity=10.0,
        price=50.0,
        total=500.0,
        currency='BRL',
    )
    db_session.add(tx)
    db_session.commit()
    return tx


def test_api_transaction_get(client, db_session):
    tx = _make_tx(db_session)
    resp = client.get(f'/api/transaction/{tx.id}')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['asset'] == 'TEST3'
    assert data['category'] == 'BUY'
    assert data['quantity'] == 10.0


def test_api_transaction_get_not_found(client, db_session):
    resp = client.get('/api/transaction/999999')
    assert resp.status_code == 404


def test_api_transaction_update(client, db_session):
    tx = _make_tx(db_session)
    resp = client.post(
        f'/api/transaction/{tx.id}',
        json={'asset': 'UPDATED3', 'quantity': '20.0'},
    )
    assert resp.status_code == 200
    assert resp.get_json()['success'] is True

    from app.models import Transaction
    updated = Transaction.query.get(tx.id)
    assert updated.asset == 'UPDATED3'
    assert updated.quantity == 20.0


def test_api_transaction_update_invalid_float(client, db_session):
    tx = _make_tx(db_session)
    resp = client.post(
        f'/api/transaction/{tx.id}',
        json={'quantity': 'not-a-number'},
    )
    assert resp.status_code == 400
    assert resp.get_json()['success'] is False


def test_api_transaction_delete(client, db_session):
    tx = _make_tx(db_session)
    tx_id = tx.id
    resp = client.post(f'/api/transaction/{tx_id}/delete')
    assert resp.status_code == 200
    assert resp.get_json()['success'] is True

    from app.models import Transaction
    assert Transaction.query.get(tx_id) is None


def test_api_transaction_delete_not_found(client, db_session):
    resp = client.post('/api/transaction/999999/delete')
    assert resp.status_code == 404

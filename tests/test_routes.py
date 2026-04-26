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


def test_format_money_filter():
    from app.routes import format_money
    assert format_money(500) == '500'
    assert format_money(1500) == '1.50 K'
    assert format_money(1_500_000) == '1.50 M'
    assert format_money(2_500_000_000) == '2.50 B'
    assert format_money(3_500_000_000_000) == '3.50 T'

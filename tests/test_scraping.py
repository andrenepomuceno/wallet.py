from unittest.mock import patch, MagicMock
import pandas as pd
import pytest
from app.utils import scraping


def test_scrape_data_success():
    fake_html = b'<html><body><span>R$ 100,00</span></body></html>'
    with patch.object(scraping.request_cache, 'get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.content = fake_html
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        out = scraping.scrape_data('http://x', '//span')
    assert out == ['R$ 100,00']


def test_scrape_data_failure():
    with patch.object(scraping.request_cache, 'get', side_effect=Exception('boom')):
        assert scraping.scrape_data('http://x', '//span') is None


def test_usd_exchange_rate():
    with patch.object(scraping.request_cache, 'get') as mock_get:
        mock_get.return_value.json.return_value = {'rates': {'BRL': 5.0}}
        assert scraping.usd_exchange_rate('BRL') == 5.0


def test_usd_exchange_rate_failure():
    with patch.object(scraping.request_cache, 'get', side_effect=Exception('boom')):
        assert scraping.usd_exchange_rate('BRL') is None


def test_get_yfinance_data():
    fake_hist = pd.DataFrame({
        'Close': [10.0, 11.0, 12.0, 13.0, 14.0],
    })
    fake_info = {
        'currency': 'USD', 'quoteType': 'EQUITY', 'longName': 'Test Inc',
    }
    with patch.object(scraping.yf, 'Ticker') as mock_ticker:
        mock_ticker.return_value.info = fake_info
        mock_ticker.return_value.history.return_value = fake_hist
        out = scraping.get_yfinance_data('TEST')
    assert out['last_close_price'] == 14.0
    assert out['previous_close'] == 13.0
    assert out['currency'] == 'USD'
    assert out['asset_class'] == 'EQUITY'

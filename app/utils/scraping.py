import requests_cache
# import yfinance_cache as yf
import yfinance as yf
from lxml import html
from app import app

# Module-level session holder. Initialized with safe defaults at import time
# (no DB access required). Reassigned by rebuild_request_cache() once the DB
# is ready / when the user updates TTLs in the UI.
request_cache = requests_cache.CachedSession(
    'request_cache',
    expire_after=60 * 60,
    allowable_methods=('GET', 'POST'),
)


def _get_session():
    """Always read the current session via the module global so rebuilds are
    picked up by callers that captured a reference earlier."""
    return request_cache


def build_request_cache(default_ttl=3600, urls_expire_after=None):
    """Create a new CachedSession with the given TTL config."""
    return requests_cache.CachedSession(
        'request_cache',
        expire_after=default_ttl,
        urls_expire_after=urls_expire_after or {},
        allowable_methods=('GET', 'POST'),
    )


def rebuild_request_cache():
    """Rebuild the module-level session from CacheConfig rows in the DB.
    Imported lazily to avoid a circular import (models -> app -> scraping)."""
    global request_cache
    try:
        from app.models import get_cache_ttls
        default_ttl, urls_expire_after = get_cache_ttls()
    except Exception as e:
        app.logger.warning('rebuild_request_cache: falling back to defaults (%s)', e)
        default_ttl, urls_expire_after = 3600, {}
    request_cache = build_request_cache(default_ttl, urls_expire_after)
    app.logger.info(
        'request_cache rebuilt: default_ttl=%ss, url_rules=%d',
        default_ttl, len(urls_expire_after),
    )
    return request_cache


def clear_request_cache():
    """Drop all cached responses without changing TTL configuration."""
    try:
        _get_session().cache.clear()
        app.logger.info('request_cache cleared')
        return True
    except Exception as e:
        app.logger.error('clear_request_cache Exception: %s', e)
        return False


def scrape_data(url, xpath):
    try:
        response = _get_session().get(url, timeout=10)
        response.raise_for_status()
        tree = html.fromstring(response.content)
        elements = tree.xpath(xpath)
        ret = [element.text_content().strip() for element in elements]
        app.logger.debug('scrape_data done!')
        return ret
    except Exception as e:
        app.logger.error("scrape_data Exception: %s", e)

def usd_exchange_rate(currency = 'BRL'):
    url = 'https://api.exchangerate-api.com/v4/latest/USD'
    try:
        response = _get_session().get(url)
        data = response.json()
        rate = data['rates'][currency]
        app.logger.debug('usd_exchange_rate done!')
        return rate
    except Exception as e:
        app.logger.error("usd_exchange_rate Exception: %s", e)

def get_yfinance_data(ticker):
    """Scrape yfinance online data for the specified asset.

    Note: yfinance now requires curl_cffi internally and is incompatible with
    custom requests/requests_cache sessions, so we let yfinance manage its own
    transport.
    """
    stock = yf.Ticker(ticker)
    info = stock.info or {}

    data = stock.history(period='5d', auto_adjust=False)
    if data is None or data.empty or 'Close' not in data.columns:
        raise RuntimeError(f'yfinance returned no history for {ticker}')

    close = data['Close']
    last_close_price = float(close.iloc[-1])
    previous_close = float(close.iloc[-2]) if len(close) >= 2 else last_close_price
    close_5d = float(close.mean())
    last_close_variation = (
        100 * (last_close_price / previous_close - 1) if previous_close else 0.0
    )

    return {
        'last_close_price': round(last_close_price, 2),
        'currency': info.get('currency', ''),
        'long_name': info.get('longName', ''),
        'asset_class': info.get('quoteType', ''),
        'info': info,
        'previous_close': round(previous_close, 2),
        'close_5d': round(close_5d, 2),
        'last_close_variation': round(last_close_variation, 2),
    }


def cached_json_post(url, headers=None, json_payload=None, timeout=12):
    """POST JSON through the shared cached session and return parsed JSON."""
    response = _get_session().post(
        url,
        headers=headers,
        json=json_payload,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()

import requests_cache
# import yfinance_cache as yf
import yfinance as yf
from lxml import html
from app import app

request_cache = requests_cache.CachedSession('request_cache', expire_after=60*60)

def scrape_data(url, xpath):
    try:
        response = request_cache.get(url, timeout=10)
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
        response = request_cache.get(url)
        data = response.json()
        rate = data['rates'][currency]
        app.logger.debug('usd_exchange_rate done!')
        return rate
    except Exception as e:
        app.logger.error("usd_exchange_rate Exception: %s", e)

def get_yfinance_data(ticker):
    """Scrape yfinance online data for the specified asset"""
    stock = yf.Ticker(ticker, session=request_cache)
    info = stock.info

    asset_info = {}

    # last_close_price = info['previousClose']
    currency = info['currency']
    asset_class = info['quoteType']
    long_name = info['longName']

    data = stock.history(period='5d', auto_adjust=False)
    last_close_price = data['Close'].iloc[-1]
    previous_close = data['Close'].iloc[-2]
    close_5d = data['Close'].mean()
    last_close_variation = 100 * (last_close_price/previous_close - 1)

    asset_info['last_close_price'] = round(last_close_price, 2)
    asset_info['currency'] = currency
    asset_info['long_name'] = long_name
    asset_info['asset_class'] = asset_class
    asset_info['info'] = stock.info
    asset_info['previous_close'] = round(previous_close, 2)
    asset_info['close_5d'] = round(close_5d, 2)
    asset_info['last_close_variation'] = round(last_close_variation, 2)

    # print(json.dumps(stock.info, indent = 4))

    return asset_info

# Price Integration

How Wallet.py resolves prices for assets from multiple sources.

---

## 🎯 General Strategy

The system tries multiple methods in cascade:

```
1. B3 Stocks (XXXX3/XXXX4)?       → yfinance + .SA
2. B3 REITs (XXXX11)?              → yfinance + .SA
3. Crypto (BTC, ETH)?             → yfinance + -USD + exchange rate
4. Custom XPath Scraping?         → specific website
5. Fallback → yfinance direct
```

---

## 🔄 get_online_info() Flow

Function in `app/processing.py`:

```python
def get_online_info(asset):
    """
    Fetch price, chart, and fundamentals for an asset
    
    Returns:
    {
        'price': float,
        'currency': str,
        'chart': str (HTML Plotly div),
        'fundamentals': dict,
        'timestamp': str
    }
    """
    
    # 1. Detect asset type
    ticker_type = detect_ticker_type(asset)
    
    # 2. Resolve yfinance ticker
    if ticker_type == 'b3_stock':
        yfinance_ticker = f"{asset}.SA"
    elif ticker_type == 'b3_fii':
        yfinance_ticker = f"{asset}.SA"
    elif ticker_type == 'crypto':
        yfinance_ticker = f"{asset}-USD"
    elif ticker_type in scrape_dict:
        # XPath scraping
        return scrape_price(asset)
    else:
        yfinance_ticker = asset
    
    # 3. Fetch yfinance
    try:
        data = yf.Ticker(yfinance_ticker)
        price = data.info.get('currentPrice')
        
        # Convert USD to BRL if crypto
        if ticker_type == 'crypto':
            usd_brl = get_usd_brl_rate()
            price *= usd_brl
            currency = 'BRL'
        else:
            currency = data.info.get('currency', 'BRL')
        
        # Generate chart
        chart = generate_candlestick_chart(data)
        
        # Fetch fundamentals
        fundamentals = {
            'pe': data.info.get('trailingPE'),
            'dividend_yield': data.info.get('dividendYield'),
            'market_cap': data.info.get('marketCap'),
            '52_week_high': data.info.get('fiftyTwoWeekHigh'),
            '52_week_low': data.info.get('fiftyTwoWeekLow'),
        }
        
        return {
            'price': price,
            'currency': currency,
            'chart': chart,
            'fundamentals': fundamentals,
            'timestamp': datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error fetching price for {asset}: {e}")
        return {
            'price': None,
            'currency': None,
            'chart': '',
            'fundamentals': {},
            'error': str(e)
        }
```

---

## 🏆 Asset Type Detection

Function in `app/utils/parsing.py`:

### B3 Stocks (XXXX3 / XXXX4)

**Pattern:** 4 alphanumeric characters + `3` or `4`

```python
import re

B3_STOCK_PATTERN = r'^[A-Z]{4}[34]$'  # ITUB3, VALE3, WEGE4

def is_b3_stock(ticker):
    return bool(re.match(B3_STOCK_PATTERN, ticker))

# Examples
is_b3_stock('ITUB3')   # True
is_b3_stock('AAPL')    # False
is_b3_stock('WEGE4')   # True
```

### B3 REITs (XXXX11)

**Pattern:** 4 alphanumeric characters + `11`

```python
B3_FII_PATTERN = r'^[A-Z]{4}11$'  # HGLG11, CSHG11

def is_b3_fii(ticker):
    return bool(re.match(B3_FII_PATTERN, ticker))

# Examples
is_b3_fii('HGLG11')    # True
is_b3_fii('ITUB3')     # False
is_b3_fii('CSHG11')    # True
```

### Crypto

**Pattern:** Known (BTC, ETH, etc) OR 4-8 uppercase characters

```python
KNOWN_CRYPTO = {'BTC', 'ETH', 'XRP', 'LTC', 'ADA', 'SOL', 'DOGE', 'XLM', 'DOT', 'AVAX'}

def is_crypto(ticker):
    if ticker.upper() in KNOWN_CRYPTO:
        return True
    # Fallback: try yfinance with -USD
    try:
        data = yf.Ticker(f"{ticker}-USD")
        return data.info.get('quoteType') == 'CRYPTOCURRENCY'
    except:
        return False

# Examples
is_crypto('BTC')       # True (known)
is_crypto('ETH')       # True (known)
is_crypto('XRP')       # True (known)
is_crypto('SHIB')      # True (may be on yfinance)
```

### Complete Detection

```python
def detect_ticker_type(ticker):
    """Detect ticker type"""
    ticker = ticker.upper()
    
    if is_b3_stock(ticker):
        return 'b3_stock'
    elif is_b3_fii(ticker):
        return 'b3_fii'
    elif is_crypto(ticker):
        return 'crypto'
    elif ticker in scrape_dict:
        return 'custom'
    else:
        return 'generic'  # Fallback

# Examples
detect_ticker_type('ITUB3')    # 'b3_stock'
detect_ticker_type('HGLG11')   # 'b3_fii'
detect_ticker_type('BTC')      # 'crypto'
detect_ticker_type('CUSTOM')   # 'generic' (tries yfinance direct)
```

---

## 💱 USD/BRL Exchange Rate

Function in `app/utils/scraping.py`:

```python
import requests_cache
from datetime import datetime

# Cache for 60 minutes
cache_session = requests_cache.CachedSession('usd_brl_cache', expire_after=3600)

def get_usd_brl_rate():
    """Fetch USD/BRL exchange rate"""
    try:
        # Free exchange rate API
        response = cache_session.get(
            'https://api.exchangerate-api.com/v4/latest/USD'
        )
        data = response.json()
        rate = data['rates']['BRL']
        return rate
    except Exception as e:
        logger.error(f"Error fetching USD/BRL: {e}")
        # Fallback: use hardcoded rate (update periodically)
        return 5.0

# Usage
rate = get_usd_brl_rate()
price_brl = price_usd * rate
```

---

## 📊 Candlestick Chart

Function to generate price history:

```python
import plotly.graph_objects as go
import yfinance as yf
import plotly.io as pyo

def generate_candlestick_chart(ticker_data, period='1y'):
    """Generate candlestick chart"""
    try:
        # Fetch history
        df = ticker_data.history(period=period)
        
        if df.empty:
            return ''
        
        # Create figure
        fig = go.Figure(data=[
            go.Candlestick(
                x=df.index,
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close']
            )
        ])
        
        fig.update_layout(
            title='Price History (1 Year)',
            yaxis_title='Price (BRL)',
            xaxis_title='Date',
            template='plotly_dark',
            height=500
        )
        
        # Return as HTML div
        return pyo.plot(fig, output_type='div')
    
    except Exception as e:
        logger.error(f"Error generating chart: {e}")
        return ''
```

---

## 🎨 Custom XPath Scraping

For assets not found on yfinance:

### Configuration

In `app/processing.py`, at the beginning of the file:

```python
scrape_dict = {
    'CUSTOM_TICKER': {
        'url': 'https://example.com/price',
        'xpath': "//span[@class='preco']/text()",
        'currency': 'BRL',
        'multiplier': 1.0  # To convert (e.g., divide by 100)
    },
    'CRYPTO_CUSTOM': {
        'url': 'https://coinmarketcap.com/currencies/example/',
        'xpath': "//span[@data-field='price']/text()",
        'currency': 'USD',
        'multiplier': 1.0
    }
}
```

### Scraping

```python
from lxml import html
import requests

def scrape_price(asset):
    """Scrape price via XPath"""
    if asset not in scrape_dict:
        return None
    
    config = scrape_dict[asset]
    
    try:
        # Fetch HTML
        response = requests.get(config['url'], timeout=5)
        response.raise_for_status()
        
        # Parse XPath
        tree = html.fromstring(response.content)
        price_text = tree.xpath(config['xpath'])
        
        if not price_text:
            raise ValueError(f"XPath didn't find element at {config['url']}")
        
        # Clean and convert
        price_str = price_text[0].strip()
        price_str = price_str.replace('R$', '').replace(',', '.').strip()
        price = float(price_str) * config['multiplier']
        
        # Convert USD if needed
        if config['currency'] == 'USD':
            usd_brl = get_usd_brl_rate()
            price *= usd_brl
        
        return {
            'price': price,
            'currency': 'BRL',
            'source': 'scrape',
            'timestamp': datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error scraping {asset}: {e}")
        return None
```

---

## ⏰ Caching

### yfinance Cache (60 min)

```python
import yfinance_cache as yf

# Automatic via yfinance_cache
data = yf.Ticker('ITUB3.SA')  # Returns from cache if < 60 min

# Clear cache (force refresh)
# rm ~/.cache/yfinance_cache
```

### requests Cache (60 min)

```python
import requests_cache

# Configured globally
cache_session = requests_cache.CachedSession(
    'wallet_cache',
    expire_after=3600  # 60 minutes
)

# Usage
response = cache_session.get('https://api.example.com/price')
```

### Clear Cache Manually

```bash
# Linux/Mac
rm -rf ~/.cache/yfinance
rm wallet_cache.sqlite

# Windows
rmdir /s %APPDATA%\.cache\yfinance
del wallet_cache.sqlite
```

---

## 🆚 Source Benchmark

| Source | Speed | Accuracy | Coverage | Notes |
|--------|-------|----------|----------|-------|
| yfinance | Fast | Very good | Excellent | Best overall option |
| XPath Scraping | Variable | Good | Limited | For custom assets |
| Free APIs | Fast | Good | Medium | May require API key |

---

## ❌ Troubleshooting

### "Price not found for asset X"

```python
# Debug
from app.processing import get_online_info
info = get_online_info('XXXX3')
print(info)  # See error

# Checklist
1. Is ticker correct? (ITUB3, not ITUB 3)
2. Does asset exist on yfinance?
   → yfinance.Ticker('ITUB3.SA').info
3. Is XPath configured if custom?
4. Is there internet connection?
```

### Price different from expected

```python
# B3 stocks need .SA
ticker = 'ITUB3.SA'  # ✅ Correct
ticker = 'ITUB3'     # ❌ Wrong (may give wrong price)

# Crypto must convert BRL
price_brl = price_usd * usd_brl_rate  # ✅ Correct
price_brl = price_usd                  # ❌ Wrong
```

### Cache out of date

```python
# Option 1: Clear cache
import os
os.system('rm -rf ~/.cache/yfinance')

# Option 2: Disable cache (development)
os.environ['YFINANCE_CACHE_DISABLE'] = '1'

# Option 3: Reduce TTL
cache_session = requests_cache.CachedSession(
    'wallet_cache',
    expire_after=60  # 1 minute instead of 60
)
```

---

## 🚀 Future Optimizations

- [ ] Redis cache for distribution
- [ ] Multiple price sources (automatic fallback)
- [ ] Price alerts
- [ ] Price history (time-series)
- [ ] Custom price API

---

## 🔗 References

- [yfinance Docs](https://yfinance.readthedocs.io/)
- [ExchangeRate-API](https://www.exchangerate-api.com/)
- [lxml XPath](https://lxml.de/xpathxpath.html)

---

**Next:** See [Development Guide](DEVELOPMENT.md) to add new price sources.

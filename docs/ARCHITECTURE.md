# Architecture

This document describes the technical structure, data flow, and patterns used in the project.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser / Client                         │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│        Flask Routes Package (app/routes/)                   │
│  - upload, transactions, asset, consolidate, admin         │
└───────────────┬───────────────────────────────────────────┘
                │
    ┌───────────┴─────────────┬──────────────────┐
    ▼                         ▼                  ▼
[Importing]            [Processing]        [Models/ORM]
app/importing.py      app/processing/      app/models/
    │                     │                    │
    ├─ Parse CSV/XLSX     ├─ Query DB         ├─ B3Movimentation
    ├─ Normalize cols     ├─ Consolidate     ├─ B3Negotiation
    ├─ Dedup (origin_id)  ├─ Fetch prices    ├─ AvenueExtract
    └─ Save to DB         ├─ Generate charts └─ GenericExtract
                          └─ *_sql_to_df()
                    │
                    ▼
        ┌──────────────────────┐
        │  SQLite Database     │
        │ instance/wallet.db   │
        └──────────────────────┘
                    │
                    ▼
        ┌──────────────────────┐
        │  External APIs       │
        │ - yfinance (prices)  │
        │ - XPath scraping     │
        └──────────────────────┘
```

---

## 📁 Folder Structure

### `/app/` — Application Core

```
app/
├── __init__.py              # Flask app setup, SQLAlchemy init, logging
├── models/                  # ORM + converters + config/cache models
│   ├── __init__.py
│   ├── config.py
│   ├── transactions.py
│   └── converters.py
├── importing.py             # CSV/XLSX parsing, normalization, dedup
├── processing/              # Core processing split by concern
│   ├── __init__.py
│   ├── prices.py
│   ├── extracts.py
│   ├── assets.py
│   ├── consolidate.py
│   └── history.py
├── routes/                  # Flask route modules
│   ├── __init__.py
│   ├── upload.py
│   ├── transactions.py
│   ├── asset.py
│   ├── consolidate.py
│   └── admin.py
├── forms.py                 # Flask-WTF forms
├── utils/
│   ├── parsing.py          # Ticker detection (XXXX3/4, XXXX11)
│   ├── scraping.py         # requests_cache session, yfinance wrapper, XPath scraping
│   ├── memocache.py        # Persistent TTL memoization via ProcessingCache table
│   └── serper.py           # Serper.dev API integration for news search
├── static/
│   ├── css/wallet.css      # Styles (Bootstrap 5 dark theme)
│   └── js/                 # Optional JavaScript
└── templates/              # Jinja2 templates
    ├── base.html           # Base layout, navbar
    ├── index.html          # Home/upload
    ├── view_consolidate.html  # Consolidated portfolio
    ├── view_asset.html     # Asset details
    └── others...
```

### `/instance/` — Local Data

```
instance/
└── wallet.db              # SQLite database (auto-created)
```

### `/uploads/` — Imported Files

```
uploads/
├── avenue-report-statement.csv
├── report-statement.csv
└── ...
```

---

## 🗂️ Data Models

### SQLAlchemy Models (models/)

#### Transaction Models

Each transaction model stores the raw columns from the respective broker CSV export and has an `origin_id` column for deduplication.

| Model | Table | Source |
|-------|-------|--------|
| `B3Movimentation` | `b3_movimentation` | B3 movement extract |
| `B3Negotiation` | `b3_negotiation` | B3 negotiation extract |
| `AvenueExtract` | `avenue_extract` | Avenue (US) statement |
| `GenericExtract` | `generic_extract` | Custom generic format |

Column details: see [Database](DATABASE.md).

Each model has a companion `*_sql_to_df(result)` function that converts ORM objects to a pandas DataFrame with standardized columns: `Date`, `Asset`, `Movimentation`, `Quantity`, `Price`, `Total`.

#### Configuration & Cache Models

- **`ApiConfig`** — Stores API keys for external services (`gemini`, `serper`).
- **`CacheConfig`** — Configurable TTLs for HTTP caches (yfinance, exchange rate, scraping) and processing caches (`asset`, `consolidate`).
- **`ProcessingCache`** — Persistent pickled memoization for expensive processing functions (`consolidate_asset_info`, etc.). TTL per category is read from `CacheConfig`.

---

## 🔄 Data Flow

### 1️⃣ Upload & Import

```
CSV/XLSX File (User)
    ↓
routes/upload.py: home() → saves to uploads/
    ↓
importing.py: parse_<source>()
    ├─ Reads with pandas
    ├─ Normalizes column names
    ├─ Converts dates → 'YYYY-MM-DD'
    ├─ Converts numbers → float, precision 8
    ├─ Generates origin_id = f"{filepath}:{gen_hash(filepath)}:{row_index}"
    ├─ Checks for duplicates (origin_id already exists?)
    └─ db.session.add() → Commit
    ↓
SQLite (instance/wallet.db)
```

**Deduplication Function:**
```python
origin_id = f"{filepath}:{sha256(filepath).hexdigest()}:{row_index}"
```

Prevents re-importing the same file multiple times.

### 2️⃣ Consolidation & Processing

```
User clicks "Consolidate"
    ↓
routes/consolidate.py: view_consolidate() → calls processing.process_consolidate_request()
    ↓
processing package:
    ├─ Iterates each asset type found in DB
    ├─ For each asset:
    │   ├─ Query: get_all_transactions(asset_code)
    │   ├─ Converts SQLAlchemy → pandas via *_sql_to_df()
    │   ├─ Classifies:
    │   │   ├─ Buys (Compra)
    │   │   ├─ Sells (Venda)
    │   │   ├─ Wages (Dividendo, Credito)
    │   │   └─ Taxes (Imposto, Debito)
    │   ├─ Calculates current position (quantity)
    │   ├─ Fetches online price → get_online_info(asset)
    │   ├─ Calculates profitability
    │   └─ Builds card with KPIs
    ├─ Aggregates total profitability
    └─ Generates charts (Plotly)
    ↓
Passes to template (Jinja2)
    ↓
HTML + Plotly DIVs rendered in browser
```

### 3️⃣ Asset Details

```
User clicks on an asset
    ↓
routes/asset.py: view_asset(source, asset)
    ├─ Calls processing.process_<source>_asset_request(asset_code)
    ├─ Returns dataframes: {buys, sells, wages, taxes}
    ├─ Fetches online price
    ├─ Calculates KPIs
    ├─ Generates candlestick chart (price history)
    └─ Fetches fundamentals (Yahoo Finance)
    ↓
template/view_asset.html
    ├─ KPI cards
    ├─ Transaction tables
    ├─ Plotly charts
    └─ Fundamentals
    ↓
HTML rendered
```

---

## 💾 Price Resolution (get_online_info)

### Strategy by Asset Type

#### B3 Stocks (XXXX3 / XXXX4)
```
ITUB3 → ITUB3.SA → yfinance
```

#### B3 REITs (XXXX11)
```
HGLG11 → HGLG11.SA → yfinance
```

#### Crypto
```
BTC → BTC-USD → yfinance → × usd_exchange_rate('BRL')
ETH → ETH-USD → yfinance → × usd_exchange_rate('BRL')
```

#### Custom (XPath)
Defined in `scrape_dict` at the beginning of `app/processing/prices.py`:
```python
scrape_dict = {
    'Tesouro Selic 2029': {
        'url': 'https://taxas-tesouro.com/resgatar/tesouro-selic-2029/',
        'xpath': '...',
        'class': 'Renda Fixa',
        'currency': 'BRL',
    },
    ...
}
```

#### Gemini AI Fallback
When standard ticker detection fails, `guess_yfinance_ticker_with_gemini(asset_name)` is called (requires a Gemini API key stored in `ApiConfig`). The system tries a compatible Gemini model (fallback candidates) to resolve the best Yahoo Finance ticker symbol.

#### News Sentiment via Gemini
On the asset detail page, news can be fetched from Serper and analyzed on demand via Gemini. The sentiment flow is intentionally manual (button-triggered) and returns:

- Overall sentiment (`positive|neutral|negative`)
- Per-item sentiment + confidence + reason
- Prompt and raw model response (for transparency/debug)

#### Final Fallback
Tries yfinance directly with the raw ticker.

---

## 🔐 Code Patterns

### 1. Adding a New Data Source

**Step 1: Model (app/models/transactions.py + app/models/converters.py)**
```python
class NewSource(db.Model):
    __tablename__ = 'new_source'
    id = db.Column(db.Integer, primary_key=True)
    origin_id = db.Column(db.String, unique=True)  # IMPORTANT!
    date = db.Column(db.String)
    asset = db.Column(db.String)
    movimentation = db.Column(db.String)
    quantity = db.Column(db.Float)
    price = db.Column(db.Float)
    total = db.Column(db.Float)

def new_source_sql_to_df():
    """Converts ORM → pandas with standardized columns"""
    results = db.session.query(NewSource).all()
    return pd.DataFrame([
        {
            'Date': r.date,
            'Asset': r.asset,
            'Movimentation': r.movimentation,  # Normalize!
            'Quantity': r.quantity,
            'Price': r.price,
            'Total': r.total
        }
        for r in results
    ])
```

**Step 2: Import (importing.py)**
```python
def parse_new_source(filepath):
    """Parse CSV/XLSX from new source"""
    df = pd.read_csv(filepath)
    
    # Normalize columns
    df.columns = ['date', 'asset', 'qty', 'price', 'total']
    
    # Convert dates
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    
    # Convert numbers
    for col in ['qty', 'price', 'total']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    
    # Deduplicate
    file_hash = gen_hash(filepath)
    for idx, row in df.iterrows():
        origin_id = f"{filepath}:{file_hash}:{idx}"
        
        # Check duplicate
        existing = db.session.query(NewSource).filter_by(origin_id=origin_id).first()
        if existing:
            continue
        
        # Insert
        entry = NewSource(
            origin_id=origin_id,
            date=row['date'],
            asset=row['asset'],
            movimentation=normalize_movimentation(row['movimentation']),
            quantity=round(row['qty'], 8),
            price=row['price'],
            total=row['total']
        )
        db.session.add(entry)
    
    db.session.commit()
```

**Step 3: Processing (app/processing/assets.py and related modules)**
```python
def process_new_source_asset_request(asset):
    """Process consolidation for an asset from new source"""
    df = new_source_sql_to_df()
    df = df[df['Asset'].str.contains(asset, case=False, na=False)]
    
    dataframes = {
        'buys': df[df['Movimentation'] == 'Compra'],
        'sells': df[df['Movimentation'] == 'Venda'],
        'wages': df[df['Movimentation'].isin(['Dividendo', 'Credito'])],
        'taxes': df[df['Movimentation'].isin(['Imposto', 'Debito'])]
    }
    
    asset_info = consolidate_asset_info(dataframes, asset)
    return asset_info
```

**Step 4: Route (app/routes/*.py)**
```python
@app.route('/view_new_source/<asset>')
def view_new_source(asset):
    asset_info = processing.process_new_source_asset_request(asset)
    return render_template('view_new_source.html', asset_info=asset_info)
```

### 2. Common Precautions

✅ **Always use `origin_id` for dedup**
```python
# ✅ Correct
origin_id = f"{filepath}:{gen_hash(filepath)}:{row_index}"
existing = db.session.query(Model).filter_by(origin_id=origin_id).first()

# ❌ Wrong
if row in other_rows:  # Unreliable!
```

✅ **Convert dates to string 'YYYY-MM-DD'**
```python
# ✅ Correct
date_str = pd.to_datetime(date_value).dt.strftime('%Y-%m-%d')

# ❌ Wrong
date = pd.to_datetime(date_value)  # Keeps as Timestamp
```

✅ **Precision 8 decimals for quantities**
```python
# ✅ Correct
quantity = round(qty, 8)  # Avoids float errors with crypto

# ❌ Wrong
quantity = qty  # May lose precision
```

✅ **Always use `.like(f'%{asset}%')` case-insensitive**
```python
# ✅ Correct
df = df[df['Asset'].str.contains(asset, case=False, na=False)]

# ❌ Wrong
if asset in df['Asset']:  # Case-sensitive, may not find
```

✅ **Check if DataFrame is not empty**
```python
# ✅ Correct
if len(df) > 0:
    value = df['column'].iloc[0]

# ❌ Wrong
value = df['column'].iloc[0]  # Error if df empty!
```

---

## 🎨 Templates & UI

All templates use **Bootstrap 5 Dark Theme** + **Plotly** for charts.

### Base Layout (base.html)
- Sticky navbar with logo and menu
- Fluid container
- Footer
- CSS/JS links

### Charts (Embedded DIVs)
```python
# In app/processing/history.py
fig = go.Figure(...)
chart_div = pyo.plot(fig, output_type='div')

# In template (Jinja2)
{{ chart_div | safe }}
```

Never save charts as separate HTML files.

---

## 📊 Consolidation Flow (consolidate_asset_info)

```python
def consolidate_asset_info(dataframes, asset):
    """
    Input: {'buys': df, 'sells': df, 'wages': df, 'taxes': df}
    Output: {'quantity', 'cost_basis', 'price', 'total', 'profit', 'profit_pct', ...}
    """
    buys = dataframes['buys']
    sells = dataframes['sells']
    wages = dataframes['wages']
    taxes = dataframes['taxes']
    
    # Quantity
    qty_buy = buys['Quantity'].sum() if len(buys) > 0 else 0
    qty_sell = sells['Quantity'].sum() if len(sells) > 0 else 0
    quantity = qty_buy - qty_sell
    
    # Cost
    cost_buy = buys['Total'].sum() if len(buys) > 0 else 0
    cost_sell = sells['Total'].sum() if len(sells) > 0 else 0
    cost_wages = wages['Total'].sum() if len(wages) > 0 else 0
    cost_taxes = taxes['Total'].sum() if len(taxes) > 0 else 0
    cost_basis = cost_buy - cost_sell + cost_taxes
    
    # Current price
    price = get_online_info(asset)['price']
    total_value = quantity * price
    
    # Profitability
    profit = total_value - cost_basis + cost_wages
    profit_pct = (profit / cost_basis * 100) if cost_basis != 0 else 0
    
    return {
        'asset': asset,
        'quantity': round(quantity, 8),
        'price': price,
        'total_value': total_value,
        'cost_basis': cost_basis,
        'profit': profit,
        'profit_pct': profit_pct,
        ...
    }
```

---

## 🔗 Module Relationships

```
routes package (Controller)
    ├─ app/forms.py (Forms)
    ├─ app/models/ (ORM)
    ├─ app/importing.py (Import)
    │   └─ app/utils/parsing.py (Ticker detection)
    └─ app/processing/ (Logic)
        ├─ app/models/ (Queries)
        ├─ app/utils/scraping.py (Prices)
        └─ Plotly (Charts)
```

---

## 🚀 Performance

- **Price cache:** yfinance_cache (60 min)
- **Scraping cache:** requests_cache (60 min)
- **Indexes:** `origin_id` is indexed for fast dedup
- **Queries:** Always filter by asset before processing

---

## 📝 Logging

Configured in `app/__init__.py`:

```python
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

Useful for debugging imports and price errors.

---

**Next:** Read [Development Guide](DEVELOPMENT.md) to learn how to contribute.

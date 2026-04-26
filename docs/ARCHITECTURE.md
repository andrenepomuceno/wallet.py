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
    ├─ Parse CSV/XLSX     ├─ Query DB         ├─ Transaction (unified)
    ├─ Translate row →    ├─ Filter by source │   - source
    │  Transaction        │  + category        │   - record_type
    ├─ Dedup (origin_id)  ├─ Fetch prices     │   - category (canonical)
    └─ Save to DB         ├─ Generate charts  │   - raw_label (preserved)
                          └─ transactions_sql_to_df()
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

#### Transaction Model (unified)

A single `Transaction` ORM (`app/models/transactions.py`) stores every row
from every source. Discriminator columns identify origin and shape:

| Column | Values |
|--------|--------|
| `source` | `'b3'` \| `'avenue'` \| `'generic'` |
| `record_type` | `'movimentation'` \| `'negotiation'` \| `'extract'` |
| `category` | Canonical: `BUY`, `SELL`, `DIVIDEND`, `INTEREST`, `TAX`, `FEE`, `RENT_WAGE`, `SPLIT`, `BONUS`, `REIMBURSE`, `REDEMPTION`, `AUCTION`, `TRANSFER`, `OTHER` |
| `raw_label` | Original CSV string preserved for audit/UI display |

Label → category translation lives in `app/models/category_mapping.py:classify()`
and is reused by importers, manual-entry routes, and the startup migration job.

Column details: see [Database](DATABASE.md).

`transactions_sql_to_df(result)` (in `app/models/converters.py`) converts a
list of `Transaction` rows into a pandas DataFrame with standardized columns
(`Date`, `Asset`, `Movimentation`, `Quantity`, `Price`, `Total`, `Category`,
`Direction`, `Source`, `RecordType`, `Produto`, `Currency`, plus a few legacy
aliases used by templates).

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
    ├─ Iterates assets discovered per source via load_products('<source>')
    ├─ For each asset:
    │   ├─ Query: Transaction.query.filter_by(source=...).filter(asset.like(...))
    │   ├─ Converts SQLAlchemy → pandas via transactions_sql_to_df()
    │   ├─ Classifies by canonical Category column:
    │   │   ├─ Buys      (Category in {BUY, SPLIT, BONUS})
    │   │   ├─ Sells     (Category == SELL)
    │   │   ├─ Wages     (Category in {DIVIDEND, INTEREST, REIMBURSE, AUCTION, REDEMPTION})
    │   │   └─ Taxes     (Category == TAX)
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

**Step 1: Row translator (`app/import_translators.py`)**
```python
from app.models import Transaction
from app.models import category_mapping as cm

def new_source_row(row):
    raw_label = row.get('movimentation', '')
    direction = row.get('direction')
    total = float(row.get('total', 0) or 0)
    category = cm.classify(
        source='new_source',
        record_type='extract',
        raw_label=raw_label,
        direction=direction,
        total=total,
    )
    return Transaction(
        source='new_source',
        record_type='extract',
        date=row['date'],
        asset=row['asset'],
        product=row.get('product') or row['asset'],
        raw_label=raw_label,
        category=category,
        direction=direction,
        quantity=row['quantity'],
        price=row['price'],
        total=total,
        currency='BRL',
    )
```

If the new source uses labels not yet in the mapping, extend
`app/models/category_mapping.py`. Unknown labels fall back to `OTHER` with a
warning — imports never fail on a new label.

**Step 2: Importer (`app/importing.py`)**
```python
def import_new_source(df, filepath):
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    for col in ('quantity', 'price', 'total'):
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    return _bulk_insert_transactions(
        df, filepath, new_source_row, suffix=':ns',
    )
```

The `suffix` keeps `origin_id` unique when one CSV produces multiple
`record_type`s (B3 already uses `:mov` and `:neg`).

**Step 3: Processing (`app/processing/assets.py`)**
```python
from app.models import Transaction, transactions_sql_to_df
from app.models import category_mapping as cat

def process_new_source_asset_request(asset):
    rows = (Transaction.query
            .filter_by(source='new_source')
            .filter(Transaction.asset.like(f'%{asset}%'))
            .order_by(Transaction.date.asc())
            .all())
    df = transactions_sql_to_df(rows)
    dataframes = {
        'buys':  df.loc[df['Category'] == cat.BUY],
        'sells': df.loc[df['Category'] == cat.SELL],
        'wages': df.loc[df['Category'].isin([cat.DIVIDEND, cat.INTEREST])],
        'taxes': df.loc[df['Category'] == cat.TAX],
    }
    return consolidate_asset_info(dataframes, {'ticker': asset})
```

**Step 4: Source loader (`app/processing/consolidate.py`)**
Add `load_products('new_source')` and a `load_consolidate(...,
process_new_source_asset_request, 'new_source')` call in
`process_consolidate_request`.

**Step 5: Route + template** in `app/routes/` and `app/templates/`.

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

# Database

Documentation of SQLite schema and access patterns.

---

## 📊 Schema

Wallet.py uses SQLite with the tables below (SQLAlchemy models in `app/models/`).

All transactional data — regardless of source (B3 movimentation, B3 negotiation,
Avenue, Generic, or manual entry) — lives in a single unified `transaction`
table. A startup job (`migrate_legacy_to_transaction()`) copies any pre-existing
rows from the legacy per-source tables into `transaction` and then drops them.

### 1. transaction (unified)

```sql
CREATE TABLE transaction (
    id INTEGER PRIMARY KEY,
    origin_id VARCHAR UNIQUE,                 -- dedup key: '<filepath>:<sha256>:<row>:<suffix>'
                                              -- suffix = ':mov' | ':neg' | ':av' | ':gen'
                                              -- manual entries use 'FORM:<sha256[:16]>'

    -- Discriminators
    source VARCHAR NOT NULL,                  -- 'b3' | 'avenue' | 'generic'
    record_type VARCHAR NOT NULL,             -- 'movimentation' | 'negotiation' | 'extract'

    -- Dates
    date VARCHAR NOT NULL,                    -- 'YYYY-MM-DD'
    settlement_date VARCHAR,                  -- Avenue 'liquidação'
    time VARCHAR,                             -- Avenue 'hora'

    -- Asset identity
    asset VARCHAR,                            -- Parsed ticker (PETR4, NVDA, ...)
    product VARCHAR,                          -- Original product/code/description string
    institution VARCHAR,                      -- Broker name

    -- Movement classification
    raw_label VARCHAR,                        -- Original CSV label ('Compra', 'Dividendos', 'Buy', ...)
    category VARCHAR NOT NULL,                -- Canonical: BUY | SELL | DIVIDEND | INTEREST
                                              --   | TAX | FEE | RENT_WAGE | SPLIT | BONUS
                                              --   | REIMBURSE | REDEMPTION | AUCTION
                                              --   | TRANSFER | OTHER
    direction VARCHAR,                        -- 'Credito' | 'Debito'

    -- Numerics (sign convention preserved per source)
    quantity FLOAT,
    price FLOAT,
    total FLOAT,
    balance FLOAT,                            -- Avenue saldo

    -- Currency / overflow
    currency VARCHAR NOT NULL DEFAULT 'BRL',  -- 'BRL' | 'USD'
    description VARCHAR,                      -- Avenue descrição
    meta JSON                                 -- mercado, prazo, etc.
);

CREATE UNIQUE INDEX ix_transaction_origin_id ON transaction (origin_id);
CREATE INDEX ix_transaction_asset ON transaction (asset);
CREATE INDEX ix_transaction_source_asset_date ON transaction (source, asset, date);
```

`transactions_sql_to_df()` (in `app/models/converters.py`) converts a list of
`Transaction` rows into the standard DataFrame used by processing
(`Date`, `Asset`, `Movimentation`, `Quantity`, `Price`, `Total`, `Category`,
`Direction`, `Source`, `RecordType`, `Produto`, `Currency`, plus a few legacy
aliases used by templates).

### Canonical category mapping

`app/models/category_mapping.py:classify(source, record_type, raw_label, direction, total)`
maps every observed CSV label to a canonical category. Unknown labels log a
warning and fall back to `OTHER` so imports never fail on new B3/Avenue
operation types. Importers, manual-entry routes, and the migration job all go
through this single function.

### 2. api_config

Stores API keys for external services.

Stores API keys for external services.

```sql
CREATE TABLE api_config (
    id INTEGER PRIMARY KEY,
    provider VARCHAR(50) UNIQUE NOT NULL,     -- 'gemini' or 'serper'
    api_key VARCHAR(255) NOT NULL
);
```

### 6. cache_config

Configurable TTLs for both HTTP and processing caches.

```sql
CREATE TABLE cache_config (
    id INTEGER PRIMARY KEY,
    category VARCHAR(50) UNIQUE NOT NULL,     -- 'default', 'yfinance', 'exchange_rate', etc.
    ttl_seconds INTEGER NOT NULL DEFAULT 3600,
    url_pattern VARCHAR(255),                 -- URL glob for HTTP cache rules (NULL = processing cache)
    updated_at DATETIME
);
```

Default categories: `default` (3600 s), `yfinance` (900 s, `*yahoo.com*`), `exchange_rate` (3600 s), `scraping` (3600 s), `asset` (600 s), `consolidate` (600 s).

### 7. processing_cache

Persistent memoization table. Stores pickled return values from expensive processing functions, keyed by `(category, key)`.

```sql
CREATE TABLE processing_cache (
    id INTEGER PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    key VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL,
    payload BLOB NOT NULL,
    UNIQUE (category, key)
);
```

---

## 🔑 Special Fields

### origin_id (Deduplication)

**Format:** `{filepath}:{sha256(filepath).hexdigest()}:{row_index}`

**Example:**
```
/home/user/uploads/avenue-statement.csv:a1b2c3d4e5f6g7h8:0
/home/user/uploads/avenue-statement.csv:a1b2c3d4e5f6g7h8:1
```

**Purpose:** Prevents re-importing the same file

**Check:**
```python
# Before inserting
existing = db.session.query(B3Movimentation).filter_by(origin_id=origin_id).first()
if not existing:
    db.session.add(entry)
```

### date (Date)

**Format:** `'YYYY-MM-DD'` as string

**Conversion on import:**
```python
df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
```

**Never:** Don't use Timestamp, DateTime, or Integer — always string!

### quantity (Quantity)

**Precision:** 8 decimal places

**Reason:** Crypto (Bitcoin = 0.00000001 BTC possible) and fractional shares

**Conversion:**
```python
quantity = round(qty, 8)
```

### movimentation (Operation Type)

**Standardized values by source:**

| Source | Values |
|--------|--------|
| B3 | `'Compra'`, `'Venda'`, `'Dividendo'`, `'Credito'`, `'Debito'` |
| Avenue | `'Compra'`, `'Venda'`, `'Dividendos'`, `'Impostos'` |
| Generic | `'Buy'`, `'Sell'`, `'Wages'`, `'Taxes'` |

**Normalization in processing.py:**
```python
# Conversion map
movimentation_map = {
    'Buy': 'Compra',
    'Sell': 'Venda',
    'Wages': 'Dividendo',  # or 'Credito'
    'Taxes': 'Impostos'     # or 'Debito'
}
```

---

## 🔍 Common Queries

### Get all B3 movimentation rows containing a ticker

```python
# Use `.produto` (the raw product name column) with .like()
results = db.session.query(B3Movimentation).filter(
    B3Movimentation.produto.like('%ITUB%')
).all()
```

The `b3_movimentation_sql_to_df()` helper then extracts the ticker with `parse_b3_ticker()`.

### Get all B3 negotiation rows for an asset

```python
results = db.session.query(B3Negotiation).filter(
    B3Negotiation.codigo.like('%ITUB%')
).all()
```

### Get by date range (all sources)

```python
# B3Movimentation uses column `data`
results = db.session.query(B3Movimentation).filter(
    B3Movimentation.data >= '2024-01-01',
    B3Movimentation.data <= '2024-12-31'
).all()

# GenericExtract uses column `date`
results = db.session.query(GenericExtract).filter(
    GenericExtract.date >= '2024-01-01',
    GenericExtract.date <= '2024-12-31'
).all()
```

### Get API key

```python
from app.models import get_api_key

api_key = get_api_key('gemini')   # Returns None if not configured
api_key = get_api_key('serper')
```

### Count transactions by type

```python
from sqlalchemy import func

result = db.session.query(
    B3Movimentation.movimentacao,
    func.count(B3Movimentation.id).label('count')
).group_by(B3Movimentation.movimentacao).all()

# Result
[('Compra', 50), ('Venda', 20), ('Dividendo', 15)]
```

### Sum quantity by asset

```python
from sqlalchemy import func

result = db.session.query(
    B3Movimentation.asset,
    func.sum(B3Movimentation.quantity).label('total_qty')
).group_by(B3Movimentation.asset).all()

# Result
[('ITUB3', 1000), ('VALE3', 500)]
```

### Remove duplicates (debug)

```python
from app.models import B3Movimentation

# See duplicates
duplicates = db.session.query(B3Movimentation.origin_id).group_by(
    B3Movimentation.origin_id
).having(func.count(B3Movimentation.id) > 1).all()

# Remove (be careful!)
for origin_id in duplicates:
    entries = db.session.query(B3Movimentation).filter_by(
        origin_id=origin_id
    ).all()
    # Keep first, delete rest
    for entry in entries[1:]:
        db.session.delete(entry)
db.session.commit()
```

---

## 📈 Data Analysis

### Profitability by asset

```python
def calculate_profitability(asset):
    """Calculate P&L of an asset"""
    from app.models import B3Movimentation
    
    # All transactions
    all_trans = db.session.query(B3Movimentation).filter(
        B3Movimentation.asset.like(f'%{asset}%')
    ).all()
    
    # Separate by type
    buys = [t for t in all_trans if t.movimentation == 'Compra']
    sells = [t for t in all_trans if t.movimentation == 'Venda']
    wages = [t for t in all_trans if t.movimentation in ['Dividendo', 'Credito']]
    
    # Totals
    cost = sum(b.total for b in buys) - sum(s.total for s in sells)
    wages_total = sum(w.total for w in wages)
    
    # Current price (via yfinance)
    from app.utils.scraping import get_price
    price = get_price(asset)
    
    # Quantity
    qty = sum(b.quantity for b in buys) - sum(s.quantity for s in sells)
    current_value = qty * price
    
    # Profit
    profit = current_value + wages_total - cost
    profit_pct = (profit / cost * 100) if cost > 0 else 0
    
    return {
        'asset': asset,
        'cost': cost,
        'current_value': current_value,
        'wages': wages_total,
        'profit': profit,
        'profit_pct': profit_pct
    }
```

### Portfolio allocation

```python
def portfolio_allocation():
    """Calculate allocation by asset"""
    from app.models import B3Movimentation, AvenueExtract
    
    allocation = {}
    
    # B3
    b3_assets = db.session.query(B3Movimentation.asset).distinct().all()
    for (asset,) in b3_assets:
        profitability = calculate_profitability(asset)
        allocation[asset] = profitability['current_value']
    
    # Avenue
    avenue_assets = db.session.query(AvenueExtract.asset).distinct().all()
    for (asset,) in avenue_assets:
        # Similar logic
        pass
    
    # Total
    total = sum(allocation.values())
    
    # Percentages
    for asset in allocation:
        allocation[asset] = {
            'value': allocation[asset],
            'pct': allocation[asset] / total * 100
        }
    
    return allocation
```

---

## 🛠️ Maintenance

### Backups

```bash
# Backup
cp instance/wallet.db instance/wallet.db.backup.$(date +%Y%m%d)

# Restore
cp instance/wallet.db.backup.20240415 instance/wallet.db
```

### Clean imported data

```python
# Remove all transactions from a source
db.session.query(B3Movimentation).delete()
db.session.commit()

# Remove specific transactions
db.session.query(B3Movimentation).filter(
    B3Movimentation.date < '2023-01-01'
).delete()
db.session.commit()
```

### Check integrity

```bash
# SQLite integrity check
sqlite3 instance/wallet.db "PRAGMA integrity_check;"

# Expected result
# ok
```

### Optimize database

```bash
# VACUUM: recovers space from deletes
sqlite3 instance/wallet.db "VACUUM;"

# ANALYZE: updates index statistics
sqlite3 instance/wallet.db "ANALYZE;"
```

---

## ⚠️ Best Practices

✅ **Always use origin_id as primary dedup key**

✅ **Keep dates as string 'YYYY-MM-DD'**

✅ **Use 8 decimals precision for quantities**

✅ **Filter in DB, not in memory**

❌ **Don't use raw SQL strings — use ORM**

❌ **Don't delete `origin_id` — it's for audit**

❌ **Don't modify historical transactions — only add new ones**

---

## 🔗 References

- [SQLAlchemy Models](../app/models/)
- [Processing Modules](../app/processing/)
- [Imports in importing.py](../app/importing.py)

---

**Next:** Read [Price Integration](PRICE_INTEGRATION.md) to understand price resolution.

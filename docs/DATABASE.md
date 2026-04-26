# Database

Documentation of SQLite schema and access patterns.

---

## 📊 Schema

Wallet.py uses SQLite with 4 main tables (SQLAlchemy models in `app/models.py`):

### 1. b3_movimentation

B3 transactions (Movement — dividends, credits, debits)

```sql
CREATE TABLE b3_movimentation (
    id INTEGER PRIMARY KEY,
    origin_id VARCHAR UNIQUE NOT NULL,
    date VARCHAR NOT NULL,                    -- 'YYYY-MM-DD'
    asset VARCHAR NOT NULL,                   -- Asset code (ITUB3, HGLG11, etc)
    movimentation VARCHAR NOT NULL,           -- 'Compra', 'Venda', 'Dividendo', 'Credito', 'Debito'
    quantity FLOAT NOT NULL,                  -- Precision 8 decimals (crypto)
    price FLOAT NOT NULL,                     -- Unit price
    total FLOAT NOT NULL                      -- Quantity × Price
);

CREATE UNIQUE INDEX idx_b3_movimentation_origin_id ON b3_movimentation(origin_id);
```

### 2. b3_negotiation

B3 transactions (Negotiation — buys and sells)

```sql
CREATE TABLE b3_negotiation (
    id INTEGER PRIMARY KEY,
    origin_id VARCHAR UNIQUE NOT NULL,
    date VARCHAR NOT NULL,
    asset VARCHAR NOT NULL,
    movimentation VARCHAR NOT NULL,           -- 'Compra' or 'Venda'
    quantity FLOAT NOT NULL,
    price FLOAT NOT NULL,
    total FLOAT NOT NULL
);

CREATE UNIQUE INDEX idx_b3_negotiation_origin_id ON b3_negotiation(origin_id);
```

### 3. avenue_extract

Avenue transactions (US Broker)

```sql
CREATE TABLE avenue_extract (
    id INTEGER PRIMARY KEY,
    origin_id VARCHAR UNIQUE NOT NULL,
    date VARCHAR NOT NULL,
    asset VARCHAR NOT NULL,                   -- US ticker (AAPL, GOOGL) or crypto
    movimentation VARCHAR NOT NULL,           -- 'Compra', 'Venda', 'Dividendos', 'Impostos'
    quantity FLOAT NOT NULL,
    price FLOAT NOT NULL,                     -- Price in USD
    total FLOAT NOT NULL                      -- Total in USD
);

CREATE UNIQUE INDEX idx_avenue_extract_origin_id ON avenue_extract(origin_id);
```

### 4. generic_extract

Generic transactions (custom format)

```sql
CREATE TABLE generic_extract (
    id INTEGER PRIMARY KEY,
    origin_id VARCHAR UNIQUE NOT NULL,
    date VARCHAR NOT NULL,
    asset VARCHAR NOT NULL,
    movimentation VARCHAR NOT NULL,           -- 'Buy', 'Sell', 'Wages', 'Taxes'
    quantity FLOAT NOT NULL,
    price FLOAT NOT NULL,
    total FLOAT NOT NULL
);

CREATE UNIQUE INDEX idx_generic_extract_origin_id ON generic_extract(origin_id);
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

### Get all transactions for an asset

```python
# ORM
results = db.session.query(B3Movimentation).filter(
    B3Movimentation.asset.like(f'%ITUB%')
).all()

# Result
[
    B3Movimentation(date='2024-01-10', asset='ITUB3', movimentation='Compra', quantity=100, ...),
    B3Movimentation(date='2024-02-15', asset='ITUB3', movimentation='Dividendo', quantity=0, ...)
]
```

### Get by date

```python
# Between dates
results = db.session.query(B3Movimentation).filter(
    db.and_(
        B3Movimentation.date >= '2024-01-01',
        B3Movimentation.date <= '2024-12-31'
    )
).all()

# After date
results = db.session.query(B3Movimentation).filter(
    B3Movimentation.date >= '2024-01-01'
).all()
```

### Count transactions by type

```python
from sqlalchemy import func

result = db.session.query(
    B3Movimentation.movimentation,
    func.count(B3Movimentation.id).label('count')
).group_by(B3Movimentation.movimentation).all()

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

- [SQLAlchemy Models](../app/models.py)
- [Queries in processing.py](../app/processing.py)
- [Imports in importing.py](../app/importing.py)

---

**Next:** Read [Price Integration](PRICE_INTEGRATION.md) to understand price resolution.

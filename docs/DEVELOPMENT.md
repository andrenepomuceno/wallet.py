# Development Guide

This guide is for developers who want to contribute or extend Wallet.py.

---

## 🛠️ Development Setup

### 1. Clone and Setup Environment

```bash
git clone git@github.com:andrenepomuceno/wallet.py.git
cd wallet.py

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Run in Debug Mode

```bash
export FLASK_ENV=development
export FLASK_DEBUG=1
./wallet.py
```

The application will automatically reload when you edit files.

### 3. Environment Variables (optional)

The application reads `FLASK_ENV`, `FLASK_DEBUG`, and `PORT` from the environment.
There is no `.env` file loader — export variables directly or set them in your shell profile.

```bash
export FLASK_ENV=development
export FLASK_DEBUG=1
export PORT=5000
```

API keys (Gemini, Serper) and cache TTLs are stored in the SQLite DB and configured at runtime via **http://localhost:5000/config/api**.

---

## 📐 Code Patterns

### Conventions

#### Dates
- **Storage:** Always `'YYYY-MM-DD'` as string
- **Conversion on import:**
  ```python
  df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
  ```

#### Numbers
- **Floats in DB:** Always convert via pandas
  ```python
  df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0.0)
  quantity = round(quantity, 8)  # 8 decimals for crypto
  ```

#### Identifiers
- **origin_id (dedup):** `f"{filepath}:{gen_hash(filepath)}:{row_index}"`
  ```python
  # In importing.py
  file_hash = gen_hash(filepath)
  for idx, row in df.iterrows():
      origin_id = f"{filepath}:{file_hash}:{idx}"
  ```

#### Movimentation Labels
- **B3:** Portuguese — `'Compra'`, `'Venda'`, `'Dividendo'`, `'Credito'`, `'Debito'`
- **Avenue:** Portuguese — `'Compra'`, `'Venda'`, `'Dividendos'`, `'Impostos'`
- **Generic:** English — `'Buy'`, `'Sell'`, `'Wages'`, `'Taxes'`

#### Processing Cache (`utils/memocache.py`)

Expensive processing functions are wrapped with `@ttl_memoize(category='...')`. Results are stored pickled in the `ProcessingCache` table. TTL per category is read from `CacheConfig`. Invalidate with `invalidate_processing_cache(category)`.

```python
from app.utils.memocache import ttl_memoize

@ttl_memoize(category='asset')
def consolidate_asset_info(dataframes, asset_info):
    ...
```

#### News Search (`utils/serper.py`)

```python
from app.utils.serper import search_news

news = search_news('ITUB3 stock', num=8)
# Returns list of {title, link, snippet, source, date, imageUrl} or [] if no key
```

#### API Keys

```python
from app.models import get_api_key

gemini_key = get_api_key('gemini')   # None if not configured
serper_key = get_api_key('serper')
```

#### Precision
- **Quantities:** `round(qty, 8)` to avoid float errors
- **Prices:** Native float, no rounding
- **Totals:** `qty × price`, no rounding

### Guardrails

✅ **Always check if DataFrame is empty before accessing:**
```python
# ✅ Correct
if len(df) > 0:
    value = df['column'].iloc[0]
else:
    value = 0

# ❌ Wrong
value = df['column'].iloc[0]  # Fails if df empty
```

✅ **Use `.like()` with SQLAlchemy, never raw SQL:**
```python
# ✅ Correct
results = db.session.query(Model).filter(Model.asset.like(f'%{asset}%')).all()

# ❌ Wrong
results = db.session.execute(f"SELECT * WHERE asset = '{asset}'")
```

✅ **Case-insensitive in pandas:**
```python
# ✅ Correct
df = df[df['Asset'].str.contains(asset, case=False, na=False)]

# ❌ Wrong
df = df[df['Asset'] == asset]
```

---

## 🆕 Adding a New Data Source

Follow the 4 steps in the [Architecture diagram](ARCHITECTURE.md#1-adding-a-new-data-source):

### Example: Add "XP Investimentos"

#### Step 1: Model (app/models/transactions.py + app/models/converters.py)

```python
class XPExtract(db.Model):
    __tablename__ = 'xp_extract'
    
    id = db.Column(db.Integer, primary_key=True)
    origin_id = db.Column(db.String, unique=True)  # CRUCIAL for dedup
    date = db.Column(db.String)  # 'YYYY-MM-DD'
    asset = db.Column(db.String)
    movimentation = db.Column(db.String)  # Normalized
    quantity = db.Column(db.Float)
    price = db.Column(db.Float)
    total = db.Column(db.Float)


def xp_extract_sql_to_df():
    """Converts ORM → pandas"""
    results = db.session.query(XPExtract).all()
    if not results:
        return pd.DataFrame(columns=['Date', 'Asset', 'Movimentation', 'Quantity', 'Price', 'Total'])
    
    return pd.DataFrame([
        {
            'Date': r.date,
            'Asset': r.asset,
            'Movimentation': r.movimentation,
            'Quantity': r.quantity,
            'Price': r.price,
            'Total': r.total
        }
        for r in results
    ])
```

#### Step 2: Import (app/importing.py)

```python
def parse_xp_extract(filepath):
    """Parse CSV from XP Investimentos"""
    df = pd.read_csv(filepath, encoding='utf-8')
    
    # Rename columns
    # Example: XP uses 'Data', 'Ticker', 'Tipo', 'Qtde', 'Preço', 'Total'
    df = df.rename(columns={
        'Data': 'date',
        'Ticker': 'asset',
        'Tipo': 'movimentation',
        'Qtde': 'quantity',
        'Preço': 'price',
        'Total': 'total'
    })
    
    # Convert dates
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    
    # Convert numbers
    for col in ['quantity', 'price', 'total']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    
    # Normalize movimentation
    def normalize_xp_movimentation(mov):
        mov = str(mov).lower()
        if 'compra' in mov or 'buy' in mov:
            return 'Compra'
        elif 'venda' in mov or 'sell' in mov:
            return 'Venda'
        elif 'div' in mov:
            return 'Dividendo'
        elif 'imposto' in mov or 'tax' in mov:
            return 'Impostos'
        return 'Outro'
    
    df['movimentation'] = df['movimentation'].apply(normalize_xp_movimentation)
    
    # Deduplication
    file_hash = gen_hash(filepath)
    for idx, row in df.iterrows():
        origin_id = f"{filepath}:{file_hash}:{idx}"
        
        # Check duplicate
        existing = db.session.query(XPExtract).filter_by(origin_id=origin_id).first()
        if existing:
            continue
        
        # Insert
        entry = XPExtract(
            origin_id=origin_id,
            date=row['date'],
            asset=row['asset'],
            movimentation=row['movimentation'],
            quantity=round(row['quantity'], 8),
            price=row['price'],
            total=row['total']
        )
        db.session.add(entry)
    
    db.session.commit()
```

#### Step 3: Processing (app/processing/assets.py and related modules)

```python
def process_xp_asset_request(asset):
    """Process consolidation for an asset from XP"""
    df = xp_extract_sql_to_df()
    
    if len(df) == 0:
        return None
    
    # Filter by asset
    df = df[df['Asset'].str.contains(asset, case=False, na=False)]
    
    if len(df) == 0:
        return None
    
    # Classify
    dataframes = {
        'buys': df[df['Movimentation'] == 'Compra'],
        'sells': df[df['Movimentation'] == 'Venda'],
        'wages': df[df['Movimentation'].isin(['Dividendo', 'Credito'])],
        'taxes': df[df['Movimentation'].isin(['Impostos', 'Debito'])]
    }
    
    # Consolidate
    asset_info = consolidate_asset_info(dataframes, asset)
    
    # Add transaction tables
    asset_info['buys'] = dataframes['buys'].to_dict('records')
    asset_info['sells'] = dataframes['sells'].to_dict('records')
    asset_info['wages'] = dataframes['wages'].to_dict('records')
    asset_info['taxes'] = dataframes['taxes'].to_dict('records')
    
    # Fetch online price
    online_info = get_online_info(asset)
    asset_info['price'] = online_info.get('price', 0)
    asset_info['chart'] = online_info.get('chart', '')
    asset_info['fundamentals'] = online_info.get('fundamentals', {})
    
    return asset_info
```

#### Step 4: Route (app/routes/*.py)

```python
@app.route('/import_xp', methods=['POST'])
def import_xp():
    """Import XP Investimentos file"""
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('home'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('home'))
    
    if not (file.filename.endswith('.csv') or file.filename.endswith('.xlsx')):
        flash('File must be CSV or XLSX', 'error')
        return redirect(url_for('home'))
    
    # Save file
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
    file.save(filepath)
    
    try:
        importing.parse_xp_extract(filepath)
        flash(f'XP Investimentos imported successfully!', 'success')
    except Exception as e:
        flash(f'Import error: {str(e)}', 'error')
    
    return redirect(url_for('home'))


@app.route('/view_xp/<asset>')
def view_xp(asset):
    """View XP asset"""
    asset_info = processing.process_xp_asset_request(asset)
    
    if not asset_info:
        flash(f'Asset {asset} not found', 'warning')
        return redirect(url_for('home'))
    
    return render_template('view_xp.html', asset_info=asset_info)
```

#### Step 5: Template (app/templates/view_xp.html)

Copy `view_asset.html` and customize as needed.

---

## 🐛 Debugging

### Enable Detailed Logs

```python
# In app/__init__.py
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# In your code
logger.debug(f"Asset: {asset}, Quantity: {quantity}")
logger.error(f"Error fetching price: {e}")
```

### Debug Database

```bash
# Access SQLite directly
sqlite3 instance/wallet.db

# See tables
.tables

# See schema
.schema b3_movimentation

# See data
SELECT * FROM b3_movimentation LIMIT 5;
```

### Debug Parser

```python
# In importing.py, add prints/logs
import logging
logger = logging.getLogger(__name__)

def parse_xp_extract(filepath):
    df = pd.read_csv(filepath)
    logger.debug(f"Columns found: {df.columns.tolist()}")
    logger.debug(f"First rows:\n{df.head()}")
    
    # ... rest of code
```

---

## ✅ Testing

Currently no formal test suite. Recommendations:

### Add unit tests

```bash
pip install pytest pytest-flask pytest-cov
```

### Example: test_importing.py

```python
import pytest
from app import app, db
from app.importing import parse_xp_extract
import tempfile
import os

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_parse_xp_extract(client):
    """Test XP parser"""
    # Create fake CSV
    content = """Data,Ticker,Tipo,Qtde,Preço,Total
2024-01-15,AAPL,Compra,10,150.00,1500.00
2024-02-20,AAPL,Venda,5,160.00,800.00"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(content)
        filepath = f.name
    
    try:
        parse_xp_extract(filepath)
        
        from app.models import XPExtract
        entries = db.session.query(XPExtract).all()
        assert len(entries) == 2
        assert entries[0].asset == 'AAPL'
        assert entries[0].quantity == 10
    finally:
        os.unlink(filepath)
```

### Run tests

```bash
pytest tests/ -v --cov=app
```

---

## 🚀 Performance & Optimizations

### Price Cache

Configured in `app/utils/scraping.py`:

```python
# 60-minute cache
cache_session = requests_cache.CachedSession('yfinance.cache', expire_after=3600)
```

### Index origin_id

Already done, but verify in schema:

```sql
CREATE UNIQUE INDEX idx_origin_id ON b3_movimentation(origin_id);
```

### Lazy Loading

Use `.all()` only when necessary; filter first:

```python
# ✅ Correct - Filters in DB
results = db.session.query(B3Movimentation).filter(
    B3Movimentation.asset.like(f'%{asset}%')
).all()

# ❌ Slow - Brings all, then filters
results = db.session.query(B3Movimentation).all()
filtered = [r for r in results if asset in r.asset]
```

---

## 📦 Build & Deploy

### Production Dependencies

```bash
pip freeze > requirements.txt
```

### Versioning

Recommend [Semantic Versioning](https://semver.org/):
- `0.1.0` — Initial alpha
- `0.2.0` — New data source, improvements
- `1.0.0` — First stable release

### Deploy (recommendations)

1. **Gunicorn** — Production WSGI server
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 wallet:app
   ```

2. **Nginx** — Reverse proxy
3. **Systemd** — Manage service
4. **PostgreSQL** — Production DB (instead of SQLite)

---

## 🔗 Contributing

1. Fork the repository
2. Create a branch: `git checkout -b feature/your-feature`
3. Commit: `git commit -m "Add feature"`
4. Push: `git push origin feature/your-feature`
5. Open a Pull Request

### Pull Request Checklist

- [ ] Tested changes locally
- [ ] Added tests if relevant
- [ ] Updated documentation
- [ ] Followed project code standards
- [ ] No hardcodes or secrets
- [ ] No unnecessary dependencies

---

## 📖 Internal References

- [Architecture](ARCHITECTURE.md) — Code structure
- [Database](DATABASE.md) — Schema and queries
- [Price Integration](PRICE_INTEGRATION.md) — Price resolution

---

**Ready to contribute?** See [GitHub Issues](https://github.com/andrenepomuceno/wallet.py/issues) for open tasks!

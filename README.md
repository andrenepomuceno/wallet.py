# Wallet.py

Flask-based investment portfolio analyzer that imports financial data from multiple Brazilian and US brokers, consolidates positions with live market prices, and provides interactive charts and detailed per-asset analytics.

![Python](https://img.shields.io/badge/Python-3.x-blue) ![Flask](https://img.shields.io/badge/Flask-dark--theme-green) ![SQLite](https://img.shields.io/badge/SQLite-local-lightgrey)

## Features

- **Multi-source import** — Upload CSV/XLSX from B3 (Brazilian stock exchange), Avenue (US broker), or a generic format
- **Automatic deduplication** — File hashing + `origin_id` prevents reimporting the same data
- **Live price tracking** — Fetches current prices from yfinance (B3 stocks `.SA`, crypto `-USD`, custom XPath scraping)
- **Portfolio consolidation** — Merges all sources, groups by asset class, calculates position, rentability, and allocation
- **Per-asset detail view** — KPI cards, buy/sell/wage/tax tables, price history candlestick chart, fundamentals from Yahoo Finance
- **Historical analysis** — Rentability evolution over time with Plotly interactive charts
- **Manual entry** — Add transactions directly via web forms with duplicate detection
- **Dark theme UI** — Bootstrap 5 dark mode with responsive layout, sticky navbar, and drag-and-drop file upload

## Supported Data Sources

| Source | Format | Transaction Labels |
|--------|--------|--------------------|
| **B3 Movimentation** | XLSX/CSV from [Área do Investidor](https://www.investidor.b3.com.br/extrato/movimentacao) | `Compra`, `Venda`, `Dividendo`, `Credito`/`Debito` |
| **B3 Negotiation** | XLSX/CSV from [Área do Investidor](https://www.investidor.b3.com.br/extrato/negociacao) | `Compra`, `Venda` |
| **Avenue Extract** | CSV from Avenue broker (old and new format auto-detected) | `Compra`, `Venda`, `Dividendos`, `Impostos` |
| **Generic Extract** | Custom CSV with columns: `Date, Asset, Movimentation, Quantity, Price, Total` | `Buy`, `Sell`, `Wages`, `Taxes` |

## Architecture

```
wallet.py (entrypoint)
├── app/
│   ├── __init__.py          # Flask app, SQLAlchemy, logging config
│   ├── models.py            # 4 ORM models + *_sql_to_df() converters
│   ├── importing.py         # CSV/XLSX parsing, normalization, dedup
│   ├── processing.py        # Core logic: consolidation, price fetching, charts
│   ├── routes.py            # Flask views + Jinja2 rendering
│   ├── forms.py             # FlaskForm definitions
│   ├── utils/
│   │   ├── parsing.py       # B3 ticker regex (XXXX3/4, XXXX11)
│   │   └── scraping.py      # yfinance wrapper, XPath scraping, USD/BRL rate
│   ├── static/css/wallet.css
│   └── templates/           # Jinja2 templates (Bootstrap 5 dark theme)
├── instance/wallet.db       # SQLite database (auto-created)
├── uploads/                 # Uploaded CSV/XLSX files
└── tests/                   # (empty — no test suite yet)
```

### Data Flow

1. **Upload** → `routes.py home()` saves file to `uploads/`, reads with pandas
2. **Import** → `importing.py` normalizes columns, deduplicates via `origin_id = filepath:sha256:row_index`, stores in SQLite
3. **Processing** → `processing.py` queries DB → `*_sql_to_df()` converters → classifies buys/sells/wages/taxes → `consolidate_asset_info()` calculates metrics
4. **Rendering** → `routes.py` passes data to Jinja2 templates with embedded Plotly charts

## Setup

```bash
git clone git@github.com:andrenepomuceno/wallet.py.git
cd wallet.py

python3 -m venv venv
source venv/bin/activate

pip3 install -r requirements.txt

./wallet.py
```

Access at **http://localhost:5000**

The SQLite database (`instance/wallet.db`) is created automatically on first run — no migrations needed.

## Usage

### 1. Import Data

- Go to the **Upload** page
- Drag & drop (or click to select) a CSV/XLSX file
- Choose the data source type and click **Upload**

### 2. Get the Data

**B3 (Brazilian Exchange):**
- Download XLSX/CSV from (PDF not supported):
  - [Área do Investidor > Extrato > Negociação](https://www.investidor.b3.com.br/extrato/negociacao)
  - [Área do Investidor > Extrato > Movimentação](https://www.investidor.b3.com.br/extrato/movimentacao)

**Avenue (US Broker):**
- Export the account statement CSV from Avenue's platform
- Both old format (`Data,Hora,Liquidação,...`) and new format (`Data transação,Data liquidação,...`) are auto-detected

**Generic:**
- Create a CSV with columns: `Date,Asset,Movimentation,Quantity,Price,Total`
- Date format: `YYYY-MM-DD`
- Movimentation values: `Buy`, `Sell`, `Wages`, `Taxes`

### 3. Consolidate & Analyze

- Click **Consolidate** in the navbar to see your full portfolio
- Click on any asset for detailed view with charts, fundamentals, and transaction history
- Use **History** links to see rentability evolution over time

## Tech Stack

- **Backend**: Flask, SQLAlchemy, pandas, numpy
- **Market Data**: yfinance, requests_cache (60min TTL), lxml (XPath scraping)
- **Frontend**: Bootstrap 5 (dark theme), Bootstrap Table, Bootstrap Icons, Plotly.js
- **Database**: SQLite (via Flask-SQLAlchemy)
- **Charts**: Plotly (`pyo.plot(fig, output_type='div')` embedded in templates)

## License

See repository for license details.

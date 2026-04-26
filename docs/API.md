# API Reference

HTTP endpoints exposed by Wallet.py.

---

## 🌐 HTTP Endpoints

### Home & Upload

#### GET /
Home page with file upload form.

**Response:** HTML (`index.html`)

#### POST /
Upload a CSV/XLSX file for import.

**Form fields:**
- `file` (multipart) — CSV or XLSX file
- `filetype` (form) — Source type string:
  - `B3 Movimentation`
  - `B3 Negotiation`
  - `Avenue Extract`
  - `Generic Extract`

**Response:** Redirect to the corresponding view page on success, redirect to `/` on error. Flash messages indicate result.

---

### Source Views (read-only tables)

#### GET /b3_movimentation
B3 movement extract table with optional filter form.

**Response:** HTML (`view_movimentation.html`)

#### GET|POST /b3_negotiation
B3 negotiation extract table. POST adds a manual entry.

**Response:** HTML (`view_negotiation.html`)

#### GET|POST /avenue
Avenue extract table. POST adds a manual entry.

**Response:** HTML (`view_extract.html`)

#### GET|POST /generic
Generic extract table. POST adds a manual entry.

**Response:** HTML (`view_generic.html`)

---

### Consolidation

#### GET /consolidate
Consolidated portfolio view: active positions grouped by asset class.

**Response:** HTML (`view_consolidate.html`)

**Context variables:**
- `by_group` — DataFrame with one row per asset class (Class, Currency, Position, Cost, Wages, Rent Wages, Taxes, Liquid Cost, Realized Gain, Not Realized Gain, Capital Gain, Rentability, Rel. Position)
- `group_df` — List of dicts, one per asset group, each with `name`, `df` (per-asset DataFrame with Name, Links, Close Price, 1D Variation, Shares, Position, Avg Price, …)
- `info` — Raw dict from `process_consolidate_request()`

#### GET /sold
Consolidated view showing only fully-sold positions.

**Response:** HTML (`view_consolidate.html`) filtered to sold groups.

---

### Asset Details

#### GET /view/\<source\>/\<asset\>
Detailed view of a single asset.

**Path parameters:**
- `source` — `b3`, `avenue`, or `generic`
- `asset` — Asset ticker (e.g. `ITUB3`, `BTC`, `AAPL`)

**Response:** HTML (`view_asset.html`)

**Context variables:**
- `info` — Full asset info dict from `process_*_asset_request()`
- `buys`, `sells`, `wages`, `taxes` — Filtered DataFrames
- `movimentation`, `negotiation`, `rent` — Optional extra DataFrames
- `graph_html` — Plotly candlestick chart HTML div
- `news` — List of recent news articles from Serper.dev (empty if no key configured)

**Returns 404** if source is invalid or asset not found.

---

### History

#### GET /history/\<source\>/\<asset\>
Historical position evolution chart for an asset.

**Path parameters:**
- `source` — `b3`, `avenue`, or `generic`
- `asset` — Asset ticker

**Response:** HTML (`view_history.html`)

---

### Configuration

#### GET|POST /config/api
View and update API keys (Gemini, Serper) and cache TTLs.

**Form fields (POST):**
- `gemini_api_key` — Gemini API key (for AI ticker resolution)
- `serper_api_key` — Serper.dev API key (for news search)
- `cache_default_ttl` — Default HTTP cache TTL (seconds)
- `cache_yfinance_ttl` — yfinance cache TTL (seconds)
- `cache_exchange_ttl` — Exchange rate cache TTL (seconds)
- `cache_scraping_ttl` — XPath scraping cache TTL (seconds)

**Response:** HTML (`view_api_config.html`)

#### POST /config/cache/clear
Clears all cached HTTP responses (does not change TTL configuration).

**Response:** Redirect to `/config/api` with flash message.

---

## 📦 ORM Models

See [Database](DATABASE.md) for full schema. Summary:

| Model | Table | Key columns |
|-------|-------|-------------|
| `B3Movimentation` | `b3_movimentation` | `produto`, `movimentacao`, `quantidade`, `preco_unitario`, `valor_operacao` |
| `B3Negotiation` | `b3_negotiation` | `codigo`, `tipo`, `quantidade`, `preco`, `valor` |
| `AvenueExtract` | `avenue_extract` | `produto`, `movimentacao`, `quantidade`, `preco_unitario`, `valor` |
| `GenericExtract` | `generic_extract` | `asset`, `movimentation`, `quantity`, `price`, `total` |
| `ApiConfig` | `api_config` | `provider`, `api_key` |
| `CacheConfig` | `cache_config` | `category`, `ttl_seconds`, `url_pattern` |
| `ProcessingCache` | `processing_cache` | `category`, `key`, `payload` |

All transaction models expose a `*_sql_to_df(result)` function that normalises columns to `Date`, `Asset`, `Movimentation`, `Quantity`, `Price`, `Total`.


---

### consolidate_asset_info(dataframes, asset)

Calcula KPIs consolidados de um ativo.

```python
def consolidate_asset_info(
    dataframes: dict,           # {'buys': df, 'sells': df, 'wages': df, 'taxes': df}
    asset: str
) -> dict:
    """
    Returns:
    {
        'asset': str,
        'quantity': float,
        'price': float,
        'total_value': float,
        'cost_basis': float,
        'profit': float,
        'profit_pct': float,
        'average_buy_price': float,
        'total_dividends': float,
        'total_taxes': float
    }
    """
```

---

### consolidate_all()

Consolida todo o portfólio.

```python
def consolidate_all() -> dict:
    """
    Returns:
    {
        'portfolio': [
            {asset_info_dict},
            ...
        ],
        'total_value': float,
        'total_profit': float,
        'total_profit_pct': float,
        'allocation_chart': str,     # HTML Plotly
        'evolution_chart': str       # HTML Plotly
    }
    """
```

---

## 📤 Funções de Import (importing.py)

### parse_b3_movimentation(filepath)

```python
def parse_b3_movimentation(filepath: str) -> None:
    """
    Lê XLSX/CSV da B3 Movimentação, normaliza e importa.
    
    Raises:
        - FileNotFoundError
        - pd.errors.EmptyDataError
        - ValueError (colunas inválidas)
    """
```

---

### parse_b3_negotiation(filepath)

```python
def parse_b3_negotiation(filepath: str) -> None:
    """Lê XLSX/CSV da B3 Negociação"""
```

---

### parse_avenue_extract(filepath)

```python
def parse_avenue_extract(filepath: str) -> None:
    """
    Lê CSV da Avenue (detecta formato antigo/novo)
    Auto-detecta e normaliza
    """
```

---

### parse_generic_extract(filepath)

```python
def parse_generic_extract(filepath: str) -> None:
    """
    Lê CSV genérico com colunas:
    Date, Asset, Movimentation, Quantity, Price, Total
    """
```

---

## 🛠️ Utilidades (utils/)

### parsing.py

```python
def detect_ticker_type(ticker: str) -> str:
    """
    Detecta tipo de ticker.
    
    Returns: 'b3_stock', 'b3_fii', 'crypto', 'custom', 'generic'
    """

def is_b3_stock(ticker: str) -> bool:
    """Verifica se é ação B3 (XXXX3/XXXX4)"""

def is_b3_fii(ticker: str) -> bool:
    """Verifica se é FII B3 (XXXX11)"""

def is_crypto(ticker: str) -> bool:
    """Verifica se é cripto (BTC, ETH, etc)"""
```

---

### scraping.py

```python
def get_online_info(asset: str) -> dict:
    """Wrapper para fetch de preços (já mencionado acima)"""

def get_usd_brl_rate() -> float:
    """Retorna taxa de câmbio USD/BRL (com cache)"""

def generate_candlestick_chart(ticker_data) -> str:
    """Gera chart Plotly candlestick em HTML div"""

def scrape_price(asset: str) -> dict:
    """XPath scraping customizado para ativos especiais"""
```

---

## 🔐 Segurança

### origin_id (Deduplicação)

```
Formato: {filepath}:{sha256(filepath).hexdigest()}:{row_index}

Exemplo:
/home/user/uploads/report.csv:a1b2c3d4...z9y8x7w6:0
/home/user/uploads/report.csv:a1b2c3d4...z9y8x7w6:1
```

**Propósito:**
- Evita reimportação do mesmo arquivo
- Permite auditoria (rastrear origem do dado)
- Chave única no banco

---

### Sem Autenticação (Atualmente)

⚠️ A aplicação não tem autenticação. Dados são locais e não sincronizados.

**Recomendações futuras:**
- Adicionar login/senha
- Criptografar DB
- Sincronizar com cloud (E2E encrypted)

---

## 📊 Formatos de Dados

### Datas

**Formato:** `'YYYY-MM-DD'` (string)

```python
# Sempre converter para string
date_str = pd.to_datetime(date_value).dt.strftime('%Y-%m-%d')
```

### Números

**Quantidades:** Precisão 8 decimais
```python
quantity = round(quantity, 8)
```

**Preços/Totais:** Float nativo
```python
price = float(price_str)
```

### Movimentation

**Português (B3/Avenue):**
- `'Compra'`
- `'Venda'`
- `'Dividendo'`, `'Credito'`
- `'Impostos'`, `'Debito'`

**Inglês (Generic):**
- `'Buy'`
- `'Sell'`
- `'Wages'`
- `'Taxes'`

---

## 📈 Charts (Plotly)

Todos os gráficos são retornados como **HTML divs** (não arquivos separados).

```python
import plotly.graph_objects as go
import plotly.io as pyo

fig = go.Figure(...)
chart_div = pyo.plot(fig, output_type='div')

# Em template Jinja2
{{ chart_div | safe }}
```

---

## 🚀 Limites

| Limite | Valor | Notas |
|--------|-------|-------|
| Tamanho máximo de arquivo | 50 MB | Configurável em Flask |
| Registros por query | Sem limite | Pode ficar lento com 100k+ |
| Cache de preço | 60 min | Configurável |
| Timeout yfinance | 5 sec | Configurável |

---

## ⚡ Rate Limiting

**Atualmente:** Sem rate limiting implementado

**Recomendações:**
- Adicionar Flask-Limiter
- Limit: 10 uploads/hora por IP
- Limit: 100 consolidate/hora

---

## 🔗 Relacionamentos

```
B3Movimentation ──┐
B3Negotiation  ─┬─┤
AvenueExtract  ─┼─┼─→ Asset Code
GenericExtract ─┘    (FK implícita via string)
                     │
                     ▼
              get_online_info(asset)
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
    yfinance   XPath Scrape  USD/BRL Rate
```

---

## 📝 Logging

```python
import logging

logger = logging.getLogger(__name__)

logger.debug(f"Debug: {value}")
logger.info(f"Info: {value}")
logger.warning(f"Aviso: {value}")
logger.error(f"Erro: {value}")
```

**Nível configurável em `app/__init__.py`**

---

**Próximo:** Veja [Banco de Dados](BANCO_DE_DADOS.md) para detalhes de schema e queries.

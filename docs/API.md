# Referência de APIs

Endpoints e modelos de dados do Wallet.py.

---

## 🌐 Endpoints HTTP

### Home & Upload

#### GET /
```
Página inicial com upload de arquivo
```

**Response:** HTML (template: `index.html`)

#### POST /upload
```
Upload de arquivo (CSV/XLSX) para importação
```

**Parameters:**
- `file` (multipart) — Arquivo CSV ou XLSX
- `source` (form) — Tipo de fonte:
  - `b3_movimentation`
  - `b3_negotiation`
  - `avenue`
  - `generic`

**Response:**
- Sucesso: Redirect para `/` com flash `"Arquivo importado com sucesso"`
- Erro: Redirect para `/` com flash de erro

**Status Codes:**
- 302 — Sucesso (redirect)
- 400 — Arquivo inválido
- 413 — Arquivo muito grande

---

### Consolidação

#### GET /consolidate
```
Visualizar portfólio consolidado
```

**Response:** HTML (template: `view_consolidate.html`)

**Dados retornados:**
```python
{
    'portfolio': [
        {
            'asset': 'ITUB3',
            'quantity': 1000,
            'price': 26.50,
            'total_value': 26500.00,
            'cost_basis': 25000.00,
            'profit': 1500.00,
            'profit_pct': 6.0,
            'allocation_pct': 15.5
        },
        ...
    ],
    'total_value': 170000.00,
    'total_profit': 15000.00,
    'total_profit_pct': 9.8,
    'allocation_chart': '<div>...</div>',  # Plotly div
    'evolution_chart': '<div>...</div>'
}
```

---

### Detalhes de Ativo

#### GET /view_asset/<asset>
```
Visualizar detalhes de um ativo específico
```

**Parameters:**
- `asset` (path) — Código do ativo (ex: ITUB3, BTC, AAPL)

**Response:** HTML (template: `view_asset.html`)

**Dados retornados:**
```python
{
    'asset': 'ITUB3',
    'quantity': 500,
    'price': 26.50,
    'total_value': 13250.00,
    'cost_basis': 12500.00,
    'profit': 750.00,
    'profit_pct': 6.0,
    'average_buy_price': 25.00,
    'highest_price': 27.50,
    'lowest_price': 24.00,
    'buys': [
        {
            'date': '2024-01-15',
            'quantity': 300,
            'price': 24.50,
            'total': 7350.00
        },
        {
            'date': '2024-02-20',
            'quantity': 200,
            'price': 26.00,
            'total': 5200.00
        }
    ],
    'sells': [
        {
            'date': '2024-03-10',
            'quantity': 100,
            'price': 26.50,
            'total': 2650.00
        }
    ],
    'wages': [
        {
            'date': '2024-03-15',
            'description': 'Dividendo',
            'total': 50.00
        }
    ],
    'taxes': [
        {
            'date': '2024-04-01',
            'description': 'Imposto',
            'total': 10.00
        }
    ],
    'price_chart': '<div>...</div>',  # Plotly candlestick
    'fundamentals': {
        'pe': 12.5,
        'dividend_yield': 0.025,
        'market_cap': 500000000,
        '52_week_high': 28.00,
        '52_week_low': 22.00
    }
}
```

---

### Tabelas de Visualização

#### GET /view_table/<source>/<type>
```
Tabela raw de transações por fonte e tipo
```

**Parameters:**
- `source` — `b3_movimentation`, `b3_negotiation`, `avenue`, `generic`
- `type` — `buys`, `sells`, `wages`, `taxes`

**Response:** HTML (template: `view_table.html`)

**Dados:**
```python
{
    'transactions': [
        {
            'id': 1,
            'date': '2024-01-15',
            'asset': 'ITUB3',
            'movimentation': 'Compra',
            'quantity': 100,
            'price': 25.00,
            'total': 2500.00,
            'origin_id': 'file.csv:abc123:0'
        },
        ...
    ],
    'count': 42
}
```

---

### Configuração de API (Experimental)

#### GET /view_api_config
```
Visualizar e gerenciar configurações de APIs externas
```

**Response:** HTML (template: `view_api_config.html`)

---

## 📦 Modelos de Dados (ORM)

### B3Movimentation

```python
class B3Movimentation(db.Model):
    __tablename__ = 'b3_movimentation'
    
    id: int                    # PK auto-increment
    origin_id: str            # Chave dedup única
    date: str                 # 'YYYY-MM-DD'
    asset: str                # Código do ativo
    movimentation: str        # Tipo operação
    quantity: float           # Precisão 8 decimais
    price: float              # Preço unitário
    total: float              # Quantidade × Preço
```

**Valores de movimentation:**
- `'Compra'` — Buy
- `'Venda'` — Sell
- `'Dividendo'` — Dividend
- `'Credito'` — Credit
- `'Debito'` — Debit

---

### B3Negotiation

```python
class B3Negotiation(db.Model):
    __tablename__ = 'b3_negotiation'
    
    id: int
    origin_id: str            # Chave dedup única
    date: str                 # 'YYYY-MM-DD'
    asset: str                # Código do ativo
    movimentation: str        # 'Compra' ou 'Venda'
    quantity: float
    price: float
    total: float
```

---

### AvenueExtract

```python
class AvenueExtract(db.Model):
    __tablename__ = 'avenue_extract'
    
    id: int
    origin_id: str            # Chave dedup única
    date: str                 # 'YYYY-MM-DD'
    asset: str                # Ticker US ou crypto
    movimentation: str        # 'Compra', 'Venda', 'Dividendos', 'Impostos'
    quantity: float
    price: float              # Em USD
    total: float              # Em USD
```

---

### GenericExtract

```python
class GenericExtract(db.Model):
    __tablename__ = 'generic_extract'
    
    id: int
    origin_id: str            # Chave dedup única
    date: str                 # 'YYYY-MM-DD'
    asset: str                # Código do ativo
    movimentation: str        # 'Buy', 'Sell', 'Wages', 'Taxes'
    quantity: float
    price: float
    total: float
```

---

## 🔧 Funções Principais (processing.py)

### get_online_info(asset)

Fetch preço, chart e fundamentals de um ativo.

```python
def get_online_info(asset: str) -> dict:
    """
    Args:
        asset: Código do ativo (ex: 'ITUB3', 'BTC', 'AAPL')
    
    Returns:
    {
        'price': float,              # Preço em BRL
        'currency': str,             # 'BRL' ou 'USD'
        'chart': str,                # HTML Plotly candlestick
        'fundamentals': dict,        # PE, dividend_yield, etc
        'timestamp': str             # ISO 8601
    }
    """
```

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

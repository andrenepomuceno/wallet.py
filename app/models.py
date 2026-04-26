from datetime import datetime
import pandas as pd
from app import db
from app.utils.parsing import parse_b3_ticker


class ApiConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(50), unique=True, nullable=False)
    api_key = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f'<ApiConfig {self.provider}>'


def get_api_key(provider: str):
    config = ApiConfig.query.filter_by(provider=provider).first()
    if config is None:
        return None
    return config.api_key


class CacheConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), unique=True, nullable=False)
    ttl_seconds = db.Column(db.Integer, nullable=False, default=3600)
    url_pattern = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<CacheConfig {self.category}={self.ttl_seconds}s>'


# Default cache categories. The 'default' category has no url_pattern and is
# applied as the global expire_after fallback. Other categories map a URL glob
# pattern (matched by requests_cache) to a TTL in seconds. Categories without
# a url_pattern are processing-cache categories (in-process memoization),
# consumed by app.utils.memocache.
DEFAULT_CACHE_CONFIG = [
    {'category': 'default',       'ttl_seconds': 3600, 'url_pattern': None},
    {'category': 'yfinance',      'ttl_seconds': 900,  'url_pattern': '*yahoo.com*'},
    {'category': 'exchange_rate', 'ttl_seconds': 3600, 'url_pattern': '*exchangerate-api.com*'},
    {'category': 'scraping',      'ttl_seconds': 3600, 'url_pattern': '*taxas-tesouro.com*'},
    {'category': 'asset',         'ttl_seconds': 600,  'url_pattern': None},
    {'category': 'consolidate',   'ttl_seconds': 600,  'url_pattern': None},
]

# Categories that belong to the processing-cache layer (not HTTP).
PROCESSING_CACHE_CATEGORIES = {'asset', 'consolidate'}


def seed_default_cache_config():
    """Insert default CacheConfig rows when missing. Safe to call repeatedly."""
    changed = False
    for entry in DEFAULT_CACHE_CONFIG:
        existing = CacheConfig.query.filter_by(category=entry['category']).first()
        if existing is None:
            db.session.add(CacheConfig(**entry))
            changed = True
    if changed:
        db.session.commit()


def get_cache_ttls():
    """Return (default_ttl_seconds, urls_expire_after_dict) from the DB.
    Only HTTP categories (those with a url_pattern) populate the dict; the
    'default' category provides the global expire_after fallback."""
    default_ttl = 3600
    urls_expire_after = {}
    for row in CacheConfig.query.all():
        if row.category == 'default':
            default_ttl = int(row.ttl_seconds)
            continue
        if not row.url_pattern:
            # Processing-cache category — not an HTTP rule.
            continue
        urls_expire_after[row.url_pattern] = int(row.ttl_seconds)
    return default_ttl, urls_expire_after


def get_processing_ttl(category: str, default: int = 600) -> int:
    """Return the TTL in seconds for a processing-cache category."""
    row = CacheConfig.query.filter_by(category=category).first()
    if row is None:
        return default
    return int(row.ttl_seconds)


class ProcessingCache(db.Model):
    """Persistent memoization storage for expensive processing functions.
    Payload is a pickled Python object. Lookups are by (category, key)."""
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False, index=True)
    key = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    payload = db.Column(db.LargeBinary, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('category', 'key', name='uq_processing_cache_cat_key'),
    )

    def __repr__(self):
        return f'<ProcessingCache {self.category}/{self.key}>'

class B3Movimentation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    origin_id = db.Column(db.String)

    entrada_saida = db.Column(db.String)
    data = db.Column(db.String)
    movimentacao = db.Column(db.String)
    produto = db.Column(db.String)
    instituicao = db.Column(db.String)
    quantidade = db.Column(db.Float)
    preco_unitario = db.Column(db.Float)
    valor_operacao = db.Column(db.Float)

    def __repr__(self):
        return f'<B3Movimentation {self.id}>'

def b3_movimentation_sql_to_df(result):
    df = pd.DataFrame([(d.entrada_saida, d.data, d.movimentacao, d.produto,
                        d.instituicao, d.quantidade, d.preco_unitario,
                        d.valor_operacao) for d in result],
                      columns=['Entrada/Saída', 'Data', 'Movimentação', 'Produto',
                               'Instituição', 'Quantidade', 'Preço unitário',
                               'Valor da Operação'])
    df['Data'] = pd.to_datetime(df['Data'])

    df = df.rename(columns={
        'Data': 'Date',
        'Quantidade': 'Quantity',
        'Movimentação': 'Movimentation',
        'Preço unitário': 'Price',
        'Valor da Operação': 'Total'
    })

    df['Asset'] = parse_b3_ticker(df['Produto'])

    return df

class B3Negotiation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    origin_id = db.Column(db.String)

    data = db.Column(db.String)
    tipo = db.Column(db.String)
    mercado = db.Column(db.String)
    prazo = db.Column(db.String)
    instituicao = db.Column(db.String)
    codigo = db.Column(db.String)
    quantidade = db.Column(db.Float)
    preco = db.Column(db.Float)
    valor = db.Column(db.Float)

    def __repr__(self):
        return f'<B3Negotiation {self.id}>'

def b3_negotiation_sql_to_df(result):
    df = pd.DataFrame([(d.data, d.tipo, d.mercado, d.prazo,
                        d.instituicao, d.codigo, d.quantidade, d.preco,
                        d.valor) for d in result],
                        columns=[
                            'Data do Negócio', 'Tipo de Movimentação', 'Mercado',
                            'Prazo/Vencimento', 'Instituição', 'Código de Negociação',
                            'Quantidade', 'Preço', 'Valor'
                        ])
    df['Data do Negócio'] = pd.to_datetime(df['Data do Negócio'])
    df['Asset'] = parse_b3_ticker(df['Código de Negociação'])

    df = df.rename(columns={
        'Data do Negócio': 'Date',
        'Quantidade': 'Quantity',
        'Tipo de Movimentação': 'Movimentation',
        'Preço': 'Price',
        'Valor': 'Total'
    })

    return df

class AvenueExtract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    origin_id = db.Column(db.String)

    data = db.Column(db.String)
    hora = db.Column(db.String)
    liquidacao = db.Column(db.String)
    descricao = db.Column(db.String)
    valor = db.Column(db.Float)
    saldo = db.Column(db.Float)

    entrada_saida = db.Column(db.String)
    produto = db.Column(db.String)
    movimentacao = db.Column(db.String)
    quantidade = db.Column(db.Float)
    preco_unitario = db.Column(db.Float)

    def __repr__(self):
        return f'<AvenueExtract {self.id}>'

def avenue_extract_sql_to_df(result) -> pd.DataFrame:
    df = pd.DataFrame([(
        d.data, d.hora, d.liquidacao, d.descricao,
        d.valor, d.saldo, d.entrada_saida, d.produto,
        d.movimentacao, d.quantidade, d.preco_unitario
    ) for d in result],
    columns=[
        'Data', 'Hora', 'Liquidação', 'Descrição',
        'Valor (U$)', 'Saldo da conta (U$)',
        'Entrada/Saída', 'Produto', 'Movimentação', 'Quantidade',
        'Preço unitário'
    ])
    df['Data'] = pd.to_datetime(df['Data'])
    df['Liquidação'] = pd.to_datetime(df['Liquidação'])
    df['Asset'] = df['Produto']

    df = df.rename(columns={
        'Data': 'Date',
        'Quantidade': 'Quantity',
        'Movimentação': 'Movimentation',
        'Preço unitário': 'Price',
        'Valor (U$)': 'Total'
    })

    return df

class GenericExtract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    origin_id = db.Column(db.String)

    date = db.Column(db.String)
    asset = db.Column(db.String)
    movimentation = db.Column(db.String)
    quantity = db.Column(db.Float)
    price = db.Column(db.Float)
    total = db.Column(db.Float)
    # TODO currency support

    def __repr__(self):
        return f'<GenericExtract {self.id}>'

def generic_extract_sql_to_df(result):
    df = pd.DataFrame([(d.date, d.asset, d.movimentation, d.quantity,
                        d.price, d.total) for d in result],
                      columns=['Date', 'Asset', 'Movimentation', 'Quantity',
                               'Price', 'Total'])
    df['Date'] = pd.to_datetime(df['Date'])

    if len(df) > 0:
        def fill_movimentation(row):
            if row['Movimentation'] == '' or pd.isna(row['Movimentation']):
                return 'Buy' if row['Total'] >= 0 else 'Sell'
            return row['Movimentation']
        df['Movimentation'] = df.apply(fill_movimentation, axis=1)

    return df

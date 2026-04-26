"""Configuration & cache models: ApiConfig, CacheConfig, ProcessingCache."""
from datetime import datetime

from app import db


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

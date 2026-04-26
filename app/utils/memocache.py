"""Persistent TTL memoization for expensive processing functions.

Stores pickled return values in the ProcessingCache SQLAlchemy table, keyed by
(category, key). TTL is read from CacheConfig per category. Invalidation is
exposed via invalidate_processing_cache().
"""
import pickle
from datetime import datetime, timedelta
from functools import wraps
from threading import Lock

from app import app, db

# Bumping this invalidates all previously cached payloads automatically.
SCHEMA_VERSION = 'v1'

_write_lock = Lock()


def _build_key(func_name, args, kwargs):
    parts = [SCHEMA_VERSION, func_name]
    parts.extend(repr(a) for a in args)
    if kwargs:
        parts.extend(f'{k}={v!r}' for k, v in sorted(kwargs.items()))
    key = '|'.join(parts)
    # Cap length to fit the column (255).
    if len(key) > 250:
        import hashlib
        key = key[:200] + ':' + hashlib.sha256(key.encode()).hexdigest()[:32]
    return key


def _ttl_for(category):
    from app.models import get_processing_ttl
    return get_processing_ttl(category)


def _load(category, key, ttl_seconds):
    from app.models import ProcessingCache
    row = ProcessingCache.query.filter_by(category=category, key=key).first()
    if row is None:
        return None, False
    age = datetime.utcnow() - row.created_at
    if age > timedelta(seconds=ttl_seconds):
        # Expired — drop and miss.
        try:
            with _write_lock:
                db.session.delete(row)
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.warning('memocache: failed to evict expired %s/%s: %s',
                               category, key, e)
        return None, False
    try:
        return pickle.loads(row.payload), True
    except Exception as e:
        app.logger.warning('memocache: failed to unpickle %s/%s: %s',
                           category, key, e)
        # Drop poisoned entry.
        try:
            with _write_lock:
                db.session.delete(row)
                db.session.commit()
        except Exception:
            db.session.rollback()
        return None, False


def _store(category, key, value):
    from app.models import ProcessingCache
    try:
        payload = pickle.dumps(value)
    except Exception as e:
        app.logger.warning('memocache: payload not picklable for %s/%s: %s',
                           category, key, e)
        return
    try:
        with _write_lock:
            row = ProcessingCache.query.filter_by(
                category=category, key=key).first()
            if row is None:
                row = ProcessingCache(category=category, key=key,
                                      payload=payload,
                                      created_at=datetime.utcnow())
                db.session.add(row)
            else:
                row.payload = payload
                row.created_at = datetime.utcnow()
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.warning('memocache: failed to store %s/%s: %s',
                           category, key, e)


def ttl_memoize(category):
    """Decorator that memoizes the wrapped function's return value in the
    ProcessingCache table with the TTL configured for the given category."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            ttl = _ttl_for(category)
            if ttl <= 0:
                return func(*args, **kwargs)
            key = _build_key(func.__name__, args, kwargs)
            value, hit = _load(category, key, ttl)
            if hit:
                app.logger.debug('memocache HIT %s/%s', category, key)
                return value
            app.logger.debug('memocache MISS %s/%s', category, key)
            value = func(*args, **kwargs)
            _store(category, key, value)
            return value
        return wrapper
    return decorator


def invalidate_processing_cache(category=None):
    """Drop cached entries. If category is None, drop all processing-cache
    rows. Otherwise drop only that category."""
    from app.models import ProcessingCache
    try:
        with _write_lock:
            query = ProcessingCache.query
            if category is not None:
                query = query.filter_by(category=category)
            deleted = query.delete(synchronize_session=False)
            db.session.commit()
        app.logger.info('memocache invalidated %s rows (category=%s)',
                        deleted, category or 'ALL')
        return deleted
    except Exception as e:
        db.session.rollback()
        app.logger.error('invalidate_processing_cache failed: %s', e)
        return 0

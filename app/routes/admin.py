"""API/cache configuration views."""
import io
import os
import shutil
import zipfile
from datetime import datetime

from flask import flash, redirect, render_template, request, send_file, url_for

from app import app, db
from app.forms import ApiConfigForm
from app.models import ApiConfig, CacheConfig, get_api_key
from app.utils.memocache import invalidate_processing_cache
from app.utils.scraping import clear_request_cache, rebuild_request_cache

_CACHE_FIELD_TO_CATEGORY = {
    'cache_default_ttl': 'default',
    'cache_yfinance_ttl': 'yfinance',
    'cache_exchange_ttl': 'exchange_rate',
    'cache_scraping_ttl': 'scraping',
    'cache_serper_ttl': 'serper',
    'cache_gemini_ttl': 'gemini',
    'cache_asset_ttl': 'asset',
    'cache_consolidate_ttl': 'consolidate',
}

_HTTP_CACHE_CATEGORIES = {'default', 'yfinance', 'exchange_rate', 'scraping', 'serper', 'gemini'}


@app.route('/config/api', methods=['GET', 'POST'])
def view_api_config():
    form = ApiConfigForm()

    if form.validate_on_submit():
        for provider, field_name in (('gemini', 'gemini_api_key'),
                                     ('serper', 'serper_api_key')):
            new_key = (getattr(form, field_name).data or '').strip()
            if not new_key:
                continue
            row = ApiConfig.query.filter_by(provider=provider).first()
            if row is None:
                db.session.add(ApiConfig(provider=provider, api_key=new_key))
            else:
                row.api_key = new_key
            flash(f'Chave {provider.capitalize()} salva com sucesso!')

        cache_changed = False
        http_cache_changed = False
        for field_name, category in _CACHE_FIELD_TO_CATEGORY.items():
            value = getattr(form, field_name).data
            if value is None:
                continue
            row = CacheConfig.query.filter_by(category=category).first()
            if row is None:
                continue
            if row.ttl_seconds != int(value):
                row.ttl_seconds = int(value)
                cache_changed = True
                if category in _HTTP_CACHE_CATEGORIES:
                    http_cache_changed = True

        db.session.commit()

        if http_cache_changed:
            rebuild_request_cache()
        if cache_changed:
            flash('TTLs de cache atualizados.')

        return redirect(url_for('view_api_config'))

    cache_rows = {row.category: row for row in CacheConfig.query.all()}
    for field_name, category in _CACHE_FIELD_TO_CATEGORY.items():
        row = cache_rows.get(category)
        if row is not None:
            getattr(form, field_name).data = row.ttl_seconds

    has_gemini_key = bool(get_api_key('gemini'))
    has_serper_key = bool(get_api_key('serper'))
    return render_template('view_api_config.html', html_title='API Config',
                           form=form, has_gemini_key=has_gemini_key,
                           has_serper_key=has_serper_key,
                           cache_rows=cache_rows)


@app.route('/config/cache/clear', methods=['POST'])
def view_cache_clear():
    if clear_request_cache():
        flash('Cache de requisicoes limpo.')
    else:
        flash('Falha ao limpar o cache de requisicoes.')
    return redirect(url_for('view_api_config'))


@app.route('/config/cache/clear/processing', methods=['POST'])
def view_processing_cache_clear():
    deleted = invalidate_processing_cache()
    flash(f'Cache de processamento limpo ({deleted} entradas).')
    return redirect(url_for('view_api_config'))


# ---------------------------------------------------------------------------
# DB export / import
# ---------------------------------------------------------------------------

def _db_path():
    """Return the filesystem path to the SQLite database file."""
    uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if not uri.startswith('sqlite:'):
        return None
    # sqlite:///relative.db  →  instance/relative.db
    # sqlite:////abs/path.db →  /abs/path.db
    raw = uri[len('sqlite:///'):]
    if os.path.isabs(raw):
        return raw
    return os.path.join(app.instance_path, raw)


_SQLITE_MAGIC = b'SQLite format 3\x00'


@app.route('/db/export')
def view_db_export():
    """Download the SQLite database as a zip archive."""
    path = _db_path()
    if not path or not os.path.isfile(path):
        flash('Database file not found.')
        return redirect(url_for('view_transactions'))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(path, arcname=os.path.basename(path))
    buf.seek(0)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    download_name = f'wallet_{timestamp}.db.zip'
    return send_file(
        buf,
        mimetype='application/zip',
        as_attachment=True,
        download_name=download_name,
    )


@app.route('/db/import', methods=['POST'])
def view_db_import():
    """Replace the current database with an uploaded zip containing a .db file."""
    uploaded = request.files.get('db_zip')
    if not uploaded or not uploaded.filename:
        flash('No file selected.')
        return redirect(url_for('view_transactions'))

    if not uploaded.filename.lower().endswith('.zip'):
        flash('Please upload a .zip file.')
        return redirect(url_for('view_transactions'))

    path = _db_path()
    if not path:
        flash('Non-SQLite databases are not supported for import.')
        return redirect(url_for('view_transactions'))

    try:
        data = uploaded.read()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            db_entries = [n for n in zf.namelist() if n.lower().endswith('.db')]
            if len(db_entries) != 1:
                flash(f'The zip must contain exactly one .db file (found {len(db_entries)}).')
                return redirect(url_for('view_transactions'))

            db_bytes = zf.read(db_entries[0])

        if not db_bytes.startswith(_SQLITE_MAGIC):
            flash('The extracted file is not a valid SQLite database.')
            return redirect(url_for('view_transactions'))

        # Back up current DB before replacing
        if os.path.isfile(path):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = path.replace('.db', f'_backup_{timestamp}.db')
            shutil.copy2(path, backup_path)
            app.logger.info('DB backed up to %s', backup_path)

        # Dispose connection pool, replace file, re-open on next request
        db.engine.dispose()
        with open(path, 'wb') as f:
            f.write(db_bytes)

        invalidate_processing_cache()
        flash('Database imported successfully. A backup of the previous DB was saved.')
    except zipfile.BadZipFile:
        flash('The uploaded file is not a valid zip archive.')
    except Exception as e:
        app.logger.error('DB import failed: %s', e)
        flash(f'Import failed: {e}')

    return redirect(url_for('view_transactions'))


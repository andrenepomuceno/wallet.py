"""API/cache configuration views."""
from flask import flash, redirect, render_template, url_for

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

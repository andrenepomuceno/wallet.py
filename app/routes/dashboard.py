"""Dashboard view — portfolio time-series and annual returns."""
from flask import flash, redirect, render_template, request, url_for

from app import app
from app.processing import process_portfolio_history, RANGE_KEYS


_ALLOWED_SCOPES = ('total', 'class', 'asset')


@app.route('/dashboard', methods=['GET'])
def view_dashboard():
    scope = (request.args.get('scope') or 'total').lower()
    if scope not in _ALLOWED_SCOPES:
        scope = 'total'

    range_key = (request.args.get('range') or '1y').lower()
    if range_key not in RANGE_KEYS:
        range_key = '1y'

    class_filter = request.args.get('class') or None
    source_filter = request.args.get('source') or None
    asset_filter = request.args.get('asset') or None

    info = process_portfolio_history(
        scope=scope,
        class_filter=class_filter,
        source_filter=source_filter,
        asset_filter=asset_filter,
        range_key=range_key,
    )

    if not info.get('valid'):
        flash('No portfolio data found for the selected filters. '
              'Upload transactions or change the scope.')
        # If the dashboard has nothing at all, redirect to home.
        if not info.get('available_classes') and not info.get('available_assets'):
            return redirect(url_for('home'))

    return render_template(
        'view_dashboard.html',
        html_title='Dashboard',
        info=info,
        scope=scope,
        range_key=range_key,
        class_filter=class_filter,
        source_filter=source_filter,
        asset_filter=asset_filter,
        range_keys=RANGE_KEYS,
    )

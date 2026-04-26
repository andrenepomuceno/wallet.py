"""File upload + dispatch to source-specific importers."""
import os

import pandas as pd
from flask import flash, jsonify, redirect, render_template, request, url_for

from app import app, UPLOADS_FOLDER
from app.importing import (
    import_avenue_extract,
    import_b3_movimentation,
    import_b3_negotiation,
    import_generic_extract,
)


def _is_ajax_request(req):
    return req.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _process_upload(req):
    file = req.files.get('file')
    filetype = req.form.get('filetype', '')

    if not file or not file.filename:
        return {
            'success': False,
            'messages': [],
            'errors': ['Error! No file provided for upload.'],
            'redirect_endpoint': 'home',
            'render_home': True,
        }

    filepath = os.path.join(UPLOADS_FOLDER, file.filename)
    file.save(filepath)
    app.logger.debug('File %s saved at %s.', file.filename, filepath)

    if filepath.endswith('.csv'):
        df = pd.read_csv(filepath)
    elif filepath.endswith('.xlsx'):
        df = pd.read_excel(filepath)
    else:
        return {
            'success': False,
            'messages': [],
            'errors': ['Error! Filetype not supported.'],
            'redirect_endpoint': 'home',
            'render_home': True,
        }

    app.logger.debug('File %s loaded to dataframe!', file.filename)

    redirect_endpoint = 'home'
    success = False
    if filetype == 'B3 Movimentation':
        import_b3_movimentation(df, filepath)
        redirect_endpoint = 'view_movimentation'
        success = True
    elif filetype == 'B3 Negotiation':
        import_b3_negotiation(df, filepath)
        redirect_endpoint = 'view_negotiation'
        success = True
    elif filetype == 'Avenue Extract':
        import_avenue_extract(df, filepath)
        redirect_endpoint = 'view_extract'
        success = True
    elif filetype == 'Generic Extract':
        import_generic_extract(df, filepath)
        redirect_endpoint = 'view_generic_extract'
        success = True
    else:
        return {
            'success': False,
            'messages': [],
            'errors': [f'Error! Failed to parse {file.filename}.'],
            'redirect_endpoint': 'home',
            'render_home': True,
        }

    return {
        'success': success,
        'messages': [f'Successfully imported {file.filename}!'] if success else [],
        'errors': [],
        'redirect_endpoint': redirect_endpoint,
    }


@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method != 'POST':
        return render_template('index.html')

    result = _process_upload(request)

    if _is_ajax_request(request):
        return jsonify({
            'success': bool(result.get('success')),
            'messages': result.get('messages', []),
            'errors': result.get('errors', []),
            'redirect_url': url_for(result.get('redirect_endpoint', 'home')),
        })

    for message in result.get('messages', []):
        flash(message)
    for error in result.get('errors', []):
        flash(error)

    if result.get('render_home'):
        return render_template('index.html')

    return redirect(url_for(result.get('redirect_endpoint', 'home')))

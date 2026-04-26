"""File upload + dispatch to source-specific importers."""
import os

import pandas as pd
from flask import flash, redirect, render_template, request, url_for

from app import app, UPLOADS_FOLDER
from app.importing import (
    import_avenue_extract,
    import_b3_movimentation,
    import_b3_negotiation,
    import_generic_extract,
)


@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method != 'POST':
        return render_template('index.html')

    file = request.files['file']
    filetype = request.form['filetype']

    if not file:
        flash('Error! No file provided for upload.')
        return render_template('index.html')

    filepath = os.path.join(UPLOADS_FOLDER, file.filename)
    file.save(filepath)
    app.logger.debug('File %s saved at %s.', file.filename, filepath)

    if filepath.endswith('.csv'):
        df = pd.read_csv(filepath)
    elif filepath.endswith('.xlsx'):
        df = pd.read_excel(filepath)
    else:
        flash('Error! Filetype not supported.')
        return render_template('index.html')

    app.logger.debug('File %s loaded to dataframe!', file.filename)

    redirect_url = 'home'
    success = False
    if filetype == 'B3 Movimentation':
        import_b3_movimentation(df, filepath)
        redirect_url = 'view_movimentation'
        success = True
    elif filetype == 'B3 Negotiation':
        import_b3_negotiation(df, filepath)
        redirect_url = 'view_negotiation'
        success = True
    elif filetype == 'Avenue Extract':
        import_avenue_extract(df, filepath)
        redirect_url = 'view_extract'
        success = True
    elif filetype == 'Generic Extract':
        import_generic_extract(df, filepath)
        redirect_url = 'view_generic_extract'
        success = True
    else:
        flash(f'Error! Failed to parse {file.filename}.')

    if success:
        flash(f'Successfully imported {file.filename}!')

    return redirect(url_for(redirect_url))

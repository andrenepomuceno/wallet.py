#!/usr/bin/python3

from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import pandas as pd
import os
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Define the path for the SQLite database
DATABASE = 'wallet.db'

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        if 'file' not in request.files:
            app.logger.debug('File upload attempt with no file part in the request.')
            return render_template('index.html', message='No file part')

        file = request.files['file']
        if file.filename == '':
            app.logger.debug('File upload attempt without selecting a file.')
            return render_template('index.html', message='No selected file')

        if file:
            filepath = os.path.join('uploads', file.filename)
            file.save(filepath)
            app.logger.debug(f'File {file.filename} saved to {filepath}.')

            if filepath.endswith('.csv') or filepath.endswith('.xlsx'):
                try:
                    if filepath.endswith('.csv'):
                        df = pd.read_csv(filepath)
                    elif filepath.endswith('.xlsx'):
                        df = pd.read_excel(filepath)
                    app.logger.debug('File read into dataframe successfully.')

                    con = sqlite3.connect(DATABASE)
                    df.to_sql('investments', con, if_exists='replace', index=False)
                    con.close()
                    app.logger.debug('Dataframe saved to SQLite database successfully.')

                    return redirect(url_for('view_table'))
                except Exception as e:
                    app.logger.error(f'Error occurred: {e}')
                    return render_template('index.html', message='An error occurred while processing the file.')
            else:
                app.logger.debug('Invalid file format attempted to upload.')
                return render_template('index.html', message='Invalid file format')

    return render_template('index.html', message='')

@app.route('/view', methods=['GET', 'POST'])
def view_table():
    con = sqlite3.connect(DATABASE)
    query = 'SELECT * FROM investments'
    if request.method == 'POST':
        filters = request.form.to_dict()
        filter_clauses = []
        for key, value in filters.items():
            if value:
                if key in ['Quantidade', 'Preço unitário', 'Valor da Operação']:
                    # Filtragem para campos numéricos
                    filter_clauses.append(f"{key} = {value}")
                else:
                    # Filtragem para campos textuais e de data
                    filter_clauses.append(f"{key} LIKE '%{value}%'")
        if filter_clauses:
            query += ' WHERE ' + ' AND '.join(filter_clauses)
        app.logger.debug(f'Applying filters: {filter_clauses}')

    df = pd.read_sql_query(query, con)
    con.close()
    app.logger.debug('Data fetched from database with applied filters.')
    return render_template('view_table.html', tables=[df.to_html(classes='data')], titles=df.columns.values)

if __name__ == '__main__':
    app.run(debug=True)



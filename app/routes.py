from flask import render_template, request, redirect, url_for, flash

import os
from app import app, db, uploads_folder
from app.models import Generic_Extract, process_b3_movimentation, process_b3_negotiation, process_avenue_extract, process_generic_extract
from app.processing import process_generic_asset_request, process_b3_movimentation_request, process_b3_negotiation_request, process_b3_asset_request, process_consolidate_request
from app.processing import process_avenue_extract_request, process_avenue_asset_request, process_generic_extract_request
from app.forms import B3MovimentationFilterForm, GenericExtractAddForm
import pandas as pd

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        file = request.files['file']
        filetype = request.form['filetype']

        if not file:
            flash('Error! No file provided for upload.')
            return render_template('index.html')
        
        filepath = os.path.join(uploads_folder, file.filename)
        file.save(filepath)
        app.logger.debug(f'File {file.filename} saved at {filepath}.')

        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath)
        elif filepath.endswith('.xlsx'):
            df = pd.read_excel(filepath)
        else:
            flash('Error! Filetype not supported.')
            return render_template('index.html')
        
        app.logger.debug(f'File {file.filename} loaded to dataframe!')
        
        if filetype == 'B3 Movimentation':
            process_b3_movimentation(df)
            flash(f'Successfully imported {file.filename}!')
            return redirect(url_for('view_movimentation'))
        elif filetype == 'B3 Negotiation':
            process_b3_negotiation(df)
            flash(f'Successfully imported {file.filename}!')
            return redirect(url_for('view_negotiation'))
        elif filetype == 'Avenue Extract':
            process_avenue_extract(df)
            flash(f'Successfully imported {file.filename}!')
            return redirect(url_for('view_extract'))
        elif filetype == 'Generic Extract':
            process_generic_extract(df)
            flash(f'Successfully imported {file.filename}!')
            return redirect(url_for('view_generic_extract'))
        else:
            flash(f'Error! Failed to parse {file.filename}.')
            return render_template('index.html')
        
    return render_template('index.html')

@app.route('/movimentation', methods=['GET', 'POST'])
def view_movimentation():
    filterForm = B3MovimentationFilterForm()
    df = process_b3_movimentation_request(request)
    return render_template('view_movimentation.html', tables=[df.to_html(classes='pandas-dataframe')], filterForm=filterForm)

@app.route('/negotiation', methods=['GET', 'POST'])
def view_negotiation():
    df = process_b3_negotiation_request(request)
    return render_template('view_negotiation.html', tables=[df.to_html(classes='pandas-dataframe')])

@app.route('/view/<asset>', methods=['GET', 'POST'])
def view_asset(asset=None):
    asset_info = process_b3_asset_request(request, asset)
    dataframes = asset_info['dataframes']
    wages = dataframes['wages']
    all_movimentation = dataframes['movimentation']
    all_negotiation = dataframes['negotiation']
    buys_events = dataframes['buys']
    sells_events = dataframes['sells']
    return render_template(
        'view_asset.html', info=asset_info, 
        buys_events=buys_events[['Data','Movimentação','Quantidade','Preço unitário', 'Valor da Operação', 'Produto']].to_html(classes='pandas-dataframe'),
        sells_events=sells_events[['Data','Movimentação','Quantidade','Preço unitário', 'Valor da Operação', 'Produto']].to_html(classes='pandas-dataframe'),
        wages_events=wages[['Data', 'Valor da Operação', 'Movimentação','Produto']].to_html(classes='pandas-dataframe'),
        all_negotiation=all_negotiation[['Data do Negócio','Tipo de Movimentação','Quantidade','Preço','Valor','Código de Negociação']].to_html(),
        all_movimentation=all_movimentation[['Data','Entrada/Saída','Movimentação', 'Quantidade', 'Preço unitário', 'Valor da Operação','Produto']].to_html(classes='pandas-dataframe')
    )

@app.route('/extract', methods=['GET', 'POST'])
def view_extract():
    df = process_avenue_extract_request(request)
    return render_template('view_extract.html', tables=[df.to_html(classes='pandas-dataframe')])

@app.route('/extract/<asset>', methods=['GET', 'POST'])
def view_extract_asset(asset=None):
    # TODO unify with view_asset
    asset_info = process_avenue_asset_request(request, asset)
    dataframes = asset_info['dataframes']
    wages = dataframes['wages']
    all_movimentation = dataframes['movimentation']
    buys_events = dataframes['buys']
    sells_events = dataframes['sells']
    return render_template(
        'view_asset.html', info=asset_info, 
        buys_events=buys_events[['Data','Movimentação','Quantidade','Preço unitário', 'Valor da Operação', 'Produto']].to_html(classes='pandas-dataframe'),
        sells_events=sells_events[['Data','Movimentação','Quantidade','Preço unitário', 'Valor da Operação', 'Produto']].to_html(classes='pandas-dataframe'),
        wages_events=wages[['Data', 'Valor da Operação', 'Movimentação','Produto']].to_html(classes='pandas-dataframe'),
        all_movimentation=all_movimentation[['Data','Entrada/Saída','Movimentação', 'Quantidade', 'Preço unitário', 'Valor da Operação','Produto']].to_html(classes='pandas-dataframe')
    )

@app.route('/generic', methods=['GET', 'POST'])
def view_generic_extract():
    app.logger.info('view_generic_extract')

    addForm = GenericExtractAddForm()
    if addForm.validate_on_submit():
        app.logger.info('addForm On submit.')

        existing_entry = Generic_Extract.query.filter_by(
            date=addForm.date.data,
            asset=addForm.asset.data,
            movimentation=addForm.movimentation.data,
            quantity=addForm.quantity.data,
            price=addForm.price.data,
            total=addForm.total.data
        ).first()

        if not existing_entry:
            new_entry = Generic_Extract(
                date=addForm.date.data,
                asset=addForm.asset.data,
                movimentation=addForm.movimentation.data,
                quantity=addForm.quantity.data,
                price=addForm.price.data,
                total=addForm.total.data
            )
            db.session.add(new_entry)
            db.session.commit()
            app.logger.info('Added new entry to database!')
            flash('Entry added successfully!')
            return redirect(url_for('view_generic_extract'))
        else:
            app.logger.info('New entry already exists in the database!')
            flash('Entry already exists in the database.')
    else:
        app.logger.debug(f'Not submit. Errors: {addForm.errors}')
        for field, errors in addForm.errors.items():
            for error in errors:
                flash(f"Error validating field {getattr(addForm, field).label.text}: {error}")

    df = process_generic_extract_request(request)
    return render_template('view_generic.html', tables=[df.to_html(classes='pandas-dataframe')], addForm=addForm)

@app.route('/generic/<asset>', methods=['GET', 'POST'])
def view_generic_asset(asset=None):
    # TODO unify with view_asset
    asset_info = process_generic_asset_request(request, asset)
    dataframes = asset_info['dataframes']
    wages = dataframes['wages']
    all_movimentation = dataframes['movimentation']
    buys_events = dataframes['buys']
    sells_events = dataframes['sells']
    return render_template(
        'view_asset.html', info=asset_info, 
        buys_events=buys_events.to_html(classes='pandas-dataframe'),
        sells_events=sells_events.to_html(classes='pandas-dataframe'),
        wages_events=wages[['Date', 'Total', 'Movimentation','Asset']].to_html(classes='pandas-dataframe'),
        all_movimentation=all_movimentation.to_html(classes='pandas-dataframe')
    )

@app.route('/consolidate', methods=['GET', 'POST'])
def view_consolidate():
    info = process_consolidate_request(request)

    if not info['valid']:
        flash('Data not found! Please upload something.')
        return redirect(url_for('home'))

    
    consolidate = info['consolidate']
    consolidate = consolidate[['url','currency','last_close_price','position_sum','position_total','buy_avg_price',
                               'total_cost','wages_sum','rents_wage_sum','liquid_cost','rentability','rentability_by_year','age']]
    consolidate = consolidate.rename(columns={
        'url': 'Name',
        'currency': 'Currency',
        'last_close_price': 'Close Price',
        'position_sum': "Position",
        'position_total': 'Position',
        'buy_avg_price': 'Avg Price',
        'total_cost': 'Total Cost',
        'wages_sum': 'Wages',
        'rents_wage_sum': 'Rent Wages',
        'liquid_cost': 'Liquid Cost',
        'rentability': 'Rentability',
        'rentability_by_year': 'Rentability/year',
        'age': 'Age'
    })

    old = info['old']
    old = old[['url','currency','position_sum','buy_avg_price','total_cost','wages_sum','rents_wage_sum','liquid_cost']]
    old = old.rename(columns={
        'url': 'Name',
        'currency': 'Currency',
        'position_sum': "Position",
        'buy_avg_price': 'Avg Price',
        'total_cost': 'Total Cost',
        'wages_sum': 'Wages',
        'rents_wage_sum': 'Rent Wages',
        'liquid_cost': 'Liquid Cost'
    })

    return render_template('view_consolidate.html', info=info,
                           consolidate=consolidate.to_html(classes='pandas-dataframe', escape=False, index=False), 
                           old=old.to_html(classes='pandas-dataframe', escape=False, index=False))

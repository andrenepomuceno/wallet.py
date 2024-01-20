from flask import render_template, request, redirect, url_for, flash

import os
from app import app, db
from app.models import Generic_Extract, process_b3_movimentation, process_b3_negotiation, process_avenue_extract, process_generic_extract
from app.processing import view_generic_asset_request, view_movimentation_request, view_negotiation_request, view_asset_request, view_consolidate_request
from app.processing import view_extract_request, view_extract_asset_request, view_generic_extract_request
from app.forms import B3MovimentationFilterForm, GenericExtractAddForm

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        file = request.files['file']
        filetype = request.form['filetype']

        if not file:
            return render_template('index.html', message='No file provided for upload.')
        
        filepath = os.path.join('uploads', file.filename)
        file.save(filepath)
        app.logger.debug(f'File {file.filename} saved at {filepath}.')

        if filetype == 'B3 Movimentation':
            process_b3_movimentation(filepath)
            return redirect(url_for('view_movimentation'))
        elif filetype == 'B3 Negotiation':
            process_b3_negotiation(filepath)
            return redirect(url_for('view_negotiation'))
        elif filetype == 'Avenue Extract':
            process_avenue_extract(filepath)
            return redirect(url_for('view_extract'))
        elif filetype == 'Generic Extract':
            process_generic_extract(filepath)
            return redirect(url_for('view_generic_extract'))
        else:
            return render_template('index.html', message='Filetype not supported.')
        
    return render_template('index.html', message='')

@app.route('/movimentation', methods=['GET', 'POST'])
def view_movimentation():
    filterForm = B3MovimentationFilterForm()

    df = view_movimentation_request(request)
    return render_template('view_movimentation.html', tables=[df.to_html(classes='pandas-dataframe')], form=filterForm)

@app.route('/negotiation', methods=['GET', 'POST'])
def view_negotiation():
    df = view_negotiation_request(request)
    return render_template('view_negotiation.html', tables=[df.to_html(classes='pandas-dataframe')])

@app.route('/view/<asset>', methods=['GET', 'POST'])
def view_asset(asset=None):
    asset_info = view_asset_request(request, asset)
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
    df = view_extract_request(request)
    return render_template('view_extract.html', tables=[df.to_html(classes='pandas-dataframe')])

@app.route('/extract/<asset>', methods=['GET', 'POST'])
def view_extract_asset(asset=None):
    # TODO unify with view_asset
    asset_info = view_extract_asset_request(request, asset)
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

    df = view_generic_extract_request(request)
    return render_template('view_generic.html', tables=[df.to_html(classes='pandas-dataframe')], addForm=addForm)

@app.route('/generic/<asset>', methods=['GET', 'POST'])
def view_generic_asset(asset=None):
    # TODO unify with view_asset
    asset_info = view_generic_asset_request(request, asset)
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
    info = view_consolidate_request(request)
    
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

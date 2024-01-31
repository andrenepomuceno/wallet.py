from flask import render_template, request, redirect, url_for, flash

import os
from app import app, db, uploads_folder
from app.models import Generic_Extract, process_b3_movimentation, process_b3_negotiation, process_avenue_extract, process_generic_extract
from app.processing import plot_price_history, process_generic_asset_request, process_b3_movimentation_request, process_b3_negotiation_request, process_b3_asset_request, process_consolidate_request
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
    buys = dataframes['buys']
    sells = dataframes['sells']
    wages = dataframes['wages']
    taxes = dataframes['taxes']
    movimentation = dataframes['movimentation']
    negotiation = dataframes['negotiation']
    rent = dataframes['rent_wages']
    extended_info=asset_info['info']

    buys = buys[['Date','Movimentation','Quantity','Price', 'Total', 'Produto']].to_html(classes='pandas-dataframe')
    sells = sells[['Date','Movimentation','Quantity','Price', 'Total', 'Produto', 'Realized Gain']].to_html(classes='pandas-dataframe')
    wages = wages[['Date', 'Total', 'Movimentation','Produto']].to_html(classes='pandas-dataframe')
    taxes = taxes[['Date', 'Total', 'Movimentation','Produto']].to_html(classes='pandas-dataframe')
    rent = rent[['Date', 'Total', 'Movimentation','Produto']].to_html(classes='pandas-dataframe')
    movimentation = movimentation.to_html(classes='pandas-dataframe')
    negotiation = negotiation.to_html()

    graph_html = plot_price_history(asset_info)

    return render_template(
        'view_asset.html', 
        info=asset_info,
        extended_info=extended_info,
        buys=buys,
        sells=sells,
        wages=wages,
        taxes=taxes,
        rent=rent,
        negotiation=negotiation,
        movimentation=movimentation,
        graph_html=graph_html,
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
    buys = dataframes['buys']
    sells = dataframes['sells']
    wages = dataframes['wages']
    taxes = dataframes['taxes']
    movimentation = dataframes['movimentation']
    extended_info=asset_info['info']

    buys=buys[['Date','Movimentation','Quantity','Price', 'Total', 'Produto']].to_html(classes='pandas-dataframe')
    sells=sells[['Date','Movimentation','Quantity','Price', 'Total', 'Produto']].to_html(classes='pandas-dataframe')
    wages=wages[['Date', 'Total', 'Movimentation','Produto']].to_html(classes='pandas-dataframe')
    taxes=taxes[['Date', 'Total', 'Movimentation','Produto']].to_html(classes='pandas-dataframe')
    movimentation=movimentation[['Date','Entrada/Saída','Movimentation', 'Quantity', 'Price', 'Total','Produto']].to_html(classes='pandas-dataframe')

    graph_html = plot_price_history(asset_info)

    return render_template(
        'view_asset.html', 
        info=asset_info, 
        extended_info=extended_info,
        buys=buys,
        sells=sells,
        wages=wages,
        taxes=taxes,
        movimentation=movimentation,
        graph_html=graph_html,
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
    buys = dataframes['buys']
    sells = dataframes['sells']
    wages = dataframes['wages']
    taxes = dataframes['taxes']
    movimentation = dataframes['movimentation']
    extended_info = asset_info['info']

    buys=buys.to_html(classes='pandas-dataframe')
    sells=sells.to_html(classes='pandas-dataframe')
    wages=wages[['Date', 'Total', 'Movimentation','Asset']].to_html(classes='pandas-dataframe')
    taxes=taxes[['Date', 'Total', 'Movimentation','Asset']].to_html(classes='pandas-dataframe')
    movimentation=movimentation.to_html(classes='pandas-dataframe')

    graph_html = plot_price_history(asset_info)

    return render_template(
        'view_asset.html', 
        info=asset_info, 
        extended_info=extended_info,
        buys=buys,
        sells=sells,
        wages=wages,
        taxes=taxes,
        movimentation=movimentation,
        graph_html=graph_html,
    )

@app.route('/consolidate', methods=['GET', 'POST'])
def view_consolidate():
    info = process_consolidate_request(request)

    if not info['valid']:
        flash('Data not found! Please upload something.')
        return redirect(url_for('home'))
    
    consolidate = info['consolidate']
    consolidate = consolidate[['url', 'currency','last_close_price','position','position_total','avg_price',
                               'cost','wages_sum','rent_wages_sum', 'taxes_sum', 'liquid_cost','realized_gain',
                               'not_realized_gain','capital_gain','rentability','rentability_by_year','age_years']]
    consolidate = consolidate.rename(columns={
        'url': 'Name',
        'currency': 'Currency',
        'last_close_price': 'Close Price',
        'position': "Shares",
        'position_total': 'Position',
        'avg_price': 'Avg Price',
        'cost': 'Cost',
        'wages_sum': 'Wages',
        'rent_wages_sum': 'Rent Wages',
        'taxes_sum': 'Taxes',
        'liquid_cost': 'Liquid Cost',
        'realized_gain': 'Realized Gain',
        'not_realized_gain': ' Not Realized Gain',
        'capital_gain': 'Capital Gain',
        'rentability': 'Rentability',
        'rentability_by_year': 'Rentability/year',
        'age_years': 'Age',
    })

    old = consolidate.loc[consolidate['Shares'] <= 0]
    old = old.sort_values(by='Capital Gain', ascending=False)

    consolidate = consolidate.loc[consolidate['Shares'] > 0]
    consolidate_brl=consolidate.loc[consolidate['Currency'] == 'BRL'] #.to_html(classes='pandas-dataframe', escape=False, index=False)
    consolidate_usd=consolidate.loc[consolidate['Currency'] == 'USD'] #.to_html(classes='pandas-dataframe', escape=False, index=False)
    old=old #.to_html(classes='pandas-dataframe', escape=False, index=False)

    return render_template('view_consolidate.html', info=info,
                           consolidate=consolidate_brl, 
                           consolidate_usd=consolidate_usd, 
                           old=old)

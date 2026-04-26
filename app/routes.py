import os
import pandas as pd
from flask import render_template, request, redirect, url_for, flash, abort
from app import app, db, UPLOADS_FOLDER
from app.models import B3Negotiation, GenericExtract, AvenueExtract, ApiConfig, get_api_key
from app.importing import import_b3_movimentation, import_b3_negotiation, import_avenue_extract
from app.importing import import_generic_extract
from app.processing import plot_price_history, process_generic_asset_request
from app.processing import process_b3_negotiation_request, process_b3_asset_request
from app.processing import process_avenue_extract_request, process_avenue_asset_request
from app.processing import process_b3_movimentation_request, process_generic_extract_request
from app.processing import process_consolidate_request
from app.processing import process_history
from app.forms import B3MovimentationFilterForm, B3NegotiationAddForm, GenericExtractAddForm, AvenueExtractAddForm, ApiConfigForm

def format_money(value):
    if value >= 1e12:
        return f"{value / 1e12:.2f} T"
    elif value >= 1e9:
        return f"{value / 1e9:.2f} B"
    elif value >= 1e6:
        return f"{value / 1e6:.2f} M"
    elif value >= 1e3:
        return f"{value / 1e3:.2f} K"
    return str(value)
app.jinja_env.filters['format_money'] = format_money


def _flash_form_errors(form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(f"Error validating field {getattr(form, field).label.text}: {error}")


def _handle_manual_entry(model, form, field_map, redirect_endpoint, with_origin_id=True):
    """Validate `form`, dedup against `model` by field values, insert if new.

    `field_map` maps form attribute names to model column names.
    Returns a redirect Response on success, otherwise None (caller must render).
    """
    if not form.validate_on_submit():
        if form.errors:
            app.logger.debug('Not submit. Errors: %s', form.errors)
            _flash_form_errors(form)
        return None

    values = {col: getattr(form, attr).data for attr, col in field_map.items()}
    filter_kwargs = dict(values)
    if with_origin_id:
        filter_kwargs['origin_id'] = 'FORM'

    if model.query.filter_by(**filter_kwargs).first():
        app.logger.info('New entry already exists in the database!')
        flash('Entry already exists in the database.')
        return None

    insert_kwargs = dict(values)
    if with_origin_id:
        insert_kwargs['origin_id'] = 'FORM'
    db.session.add(model(**insert_kwargs))
    db.session.commit()
    app.logger.info('Added new entry to database!')
    flash('Entry added successfully!')
    return redirect(url_for(redirect_endpoint))

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

@app.route('/b3_movimentation', methods=['GET', 'POST'])
def view_movimentation():
    filter_form = B3MovimentationFilterForm()
    df = process_b3_movimentation_request(request)
    return render_template('view_movimentation.html', html_title='B3 Movimentation',
                           df=df, filter_form=filter_form)

@app.route('/b3_negotiation', methods=['GET', 'POST'])
def view_negotiation():
    app.logger.info('view_negotiation')

    add_form = B3NegotiationAddForm()
    response = _handle_manual_entry(
        B3Negotiation, add_form,
        field_map={
            'date': 'data', 'movimentation': 'tipo', 'mercado': 'mercado',
            'prazo': 'prazo', 'instituicao': 'instituicao', 'codigo': 'codigo',
            'quantity': 'quantidade', 'price': 'preco', 'total': 'valor',
        },
        redirect_endpoint='view_negotiation',
    )
    if response is not None:
        return response

    df = process_b3_negotiation_request()
    return render_template('view_negotiation.html', html_title='B3 Negotiation',
                           df=df, add_form=add_form)

@app.route('/avenue', methods=['GET', 'POST'])
def view_extract():
    app.logger.info('view_extract')

    add_form = AvenueExtractAddForm()
    response = _handle_manual_entry(
        AvenueExtract, add_form,
        field_map={
            'data': 'data', 'hora': 'hora', 'liquidacao': 'liquidacao',
            'descricao': 'descricao', 'valor': 'valor', 'saldo': 'saldo',
            'entrada_saida': 'entrada_saida', 'produto': 'produto',
            'movimentacao': 'movimentacao', 'quantidade': 'quantidade',
            'preco_unitario': 'preco_unitario',
        },
        redirect_endpoint='view_extract',
    )
    if response is not None:
        return response

    df = process_avenue_extract_request()
    return render_template('view_extract.html', html_title='Avenue Extract',
                           df=df, add_form=add_form)

@app.route('/generic', methods=['GET', 'POST'])
def view_generic_extract():
    app.logger.info('view_generic_extract')

    add_form = GenericExtractAddForm()
    response = _handle_manual_entry(
        GenericExtract, add_form,
        field_map={
            'date': 'date', 'asset': 'asset', 'movimentation': 'movimentation',
            'quantity': 'quantity', 'price': 'price', 'total': 'total',
        },
        redirect_endpoint='view_generic_extract',
        with_origin_id=False,
    )
    if response is not None:
        return response

    df = process_generic_extract_request()
    return render_template('view_generic.html', html_title='Generic Extract',
                           df=df, add_form=add_form)

@app.route('/config/api', methods=['GET', 'POST'])
def view_api_config():
    form = ApiConfigForm()

    if form.validate_on_submit():
        new_key = (form.gemini_api_key.data or '').strip()
        gemini_config = ApiConfig.query.filter_by(provider='gemini').first()

        if new_key:
            if gemini_config is None:
                gemini_config = ApiConfig(provider='gemini', api_key=new_key)
                db.session.add(gemini_config)
            else:
                gemini_config.api_key = new_key
            db.session.commit()
            flash('Chave Gemini salva com sucesso!')
            return redirect(url_for('view_api_config'))

        flash('Nenhuma chave informada. A configuracao atual foi mantida.')

    has_gemini_key = bool(get_api_key('gemini'))
    return render_template('view_api_config.html', html_title='API Config',
                           form=form, has_gemini_key=has_gemini_key)

def view_asset_helper(asset_info):
    dataframes = asset_info['dataframes']
    extended_info=asset_info['info']
    
    buys = dataframes['buys']
    sells = dataframes['sells']
    wages = dataframes['wages']
    taxes = dataframes['taxes']

    buys = buys[['Date', 'Movimentation', 'Quantity', 'Price',
                 'Total']]
    sells = sells[['Date','Movimentation','Quantity','Price',
                   'Total', 'Realized Gain']]
    wages = wages[['Date', 'Total', 'Movimentation']]
    taxes = taxes[['Date', 'Total', 'Movimentation']]

    graph_html = plot_price_history(asset_info)

    movimentation = pd.DataFrame()
    if 'movimentation' in dataframes:
        movimentation = dataframes['movimentation']

    negotiation = pd.DataFrame()
    if 'negotiation' in dataframes:
        negotiation = dataframes['negotiation']

    rent = pd.DataFrame()
    if 'rent_wages' in dataframes:
        rent = dataframes['rent_wages']
        rent = rent[['Date', 'Total', 'Movimentation']]

    asset = asset_info['name']
    return render_template(
        'view_asset.html', html_title=f'{asset}',
        info=asset_info,
        extended_info=extended_info,
        buys=buys,
        sells=sells,
        wages=wages,
        taxes=taxes,
        movimentation=movimentation,
        graph_html=graph_html,
        rent=rent,
        negotiation=negotiation,
    )

@app.route('/view/<source>/<asset>', methods=['GET', 'POST'])
def view_asset(source=None, asset=None):
    asset_info = {'valid': False}

    if source == 'b3':
        asset_info = process_b3_asset_request(asset)
    elif source == 'avenue':
        asset_info = process_avenue_asset_request(asset)
    elif source == 'generic':
        asset_info = process_generic_asset_request(asset)
    else:
        abort(404)

    if not asset_info['valid']:
        abort(404)

    return view_asset_helper(asset_info)

@app.route('/consolidate', methods=['GET', 'POST'])
def view_consolidate():
    info = process_consolidate_request()

    if not info['valid']:
        flash('Data not found! Please upload something.')
        return redirect(url_for('home'))

    by_group = info['consolidate_by_group']
    by_group = by_group[['asset_class', 'currency', 'position', 'rentability',
                         'cost', 'liquid_cost', 'wages', 'rents',
                         'taxes', 'capital_gain', 'realized_gain', 'not_realized_gain',
                         'relative_position']]
    by_group = by_group.rename(columns={
        'asset_class': 'Class',
        'currency': 'Currency',
        'position': 'Position',
        'cost': 'Cost',
        'wages': 'Wages',
        'rents': 'Rent Wages',
        'taxes': 'Taxes',
        'liquid_cost': 'Liquid Cost',
        'realized_gain': 'Realized Gain',
        'not_realized_gain': ' Not Realized Gain',
        'capital_gain': 'Capital Gain',
        'rentability': 'Rentability',
        'relative_position': 'Rel. Position'
    })

    group_df = info['group_df']
    for group in group_df:
        df = group['df']
        df = df[[
            'name', 'url', 'currency', 'last_close_price', 'last_close_variation',
            'position', 'position_total','avg_price',
            'cost','wages_sum','rent_wages_sum', 'taxes_sum', 'liquid_cost','realized_gain',
            'not_realized_gain','capital_gain','rentability',
            'rentability_by_year','age_years'
        ]]
        df = df.rename(columns={
            'name': 'Name',
            'url': 'Links',
            'history_url': 'History',
            'currency': 'Currency',
            'last_close_price': 'Close Price',
            'last_close_variation': '1D Variation',
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

        group['df'] = df

    return render_template('view_consolidate.html', html_title='Consolidate', info=info,
                           by_group=by_group,
                           group_df=group_df)

@app.route('/history/<source>/<asset>', methods=['GET', 'POST'])
def view_history(asset=None, source=None):
    ret = process_history(asset, source)
    consolidate = ret['consolidate']
    plots = ret['plots']
    return render_template('view_history.html', html_title=f'{asset} history',title=f'{asset}',
                           df=consolidate, plots=plots)

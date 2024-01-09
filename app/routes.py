from flask import render_template, request, redirect, url_for

import os
from app import app
from app.models import process_b3_movimentation, process_b3_negotiation
from app.utils.processing import view_movimentation_request, view_negotiation_request, view_asset_request, view_consolidate_request

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
        else:
            return render_template('index.html', message='Filetype not supported.')
        
    return render_template('index.html', message='')

@app.route('/movimentation', methods=['GET', 'POST'])
def view_movimentation():
    df = view_movimentation_request(request)
    return render_template('view_movimentation.html', tables=[df.to_html(classes='pandas-dataframe')])

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
    # negotiation_buys = dataframes['negotiation_buys']
    # negotiation_sells = dataframes['negotiation_sells']
    return render_template(
        'view_asset.html', info=asset_info, 
        buys_events=buys_events[['Data','Movimentação','Quantidade','Preço unitário', 'Valor da Operação', 'Produto']].to_html(classes='pandas-dataframe'),
        sells_events=sells_events[['Data','Movimentação','Quantidade','Preço unitário', 'Valor da Operação', 'Produto']].to_html(classes='pandas-dataframe'),
        wages_events=wages[['Data', 'Valor da Operação', 'Movimentação']].to_html(classes='pandas-dataframe'),

        # negotiation_buys=[negotiation_buys[['Data do Negócio','Quantidade','Preço', 'Valor']].to_html(classes='pandas-dataframe')],
        # negotiation_sells=[negotiation_sells[['Data do Negócio','Quantidade','Preço', 'Valor']].to_html(classes='pandas-dataframe')]

        all_negotiation=all_negotiation[['Data do Negócio','Tipo de Movimentação','Quantidade','Preço','Valor']].to_html(),
        all_movimentation=all_movimentation[['Data','Entrada/Saída','Movimentação', 'Quantidade', 'Preço unitário', 'Valor da Operação','Produto']].to_html(classes='pandas-dataframe')
    )

@app.route('/consolidate', methods=['GET', 'POST'])
def view_consolidate():
    info = view_consolidate_request(request)
    consolidate = info['consolidate']
    old = info['old']
    return render_template('view_consolidate.html', info=info, 
                           consolidate=consolidate[['url','ticker','currency','last_close_price',
                                                    'position_sum','position_total','buy_avg_price',
                                                    'total_cost','wages_sum','rents_wage_sum','liquid_cost',
                                                    'rentability','rentability_by_year']].to_html(classes='pandas-dataframe', escape=False), 
                           old=old[['url','ticker','currency','last_close_price',
                                    'position_sum','position_total','buy_avg_price',
                                    'total_cost','wages_sum','rents_wage_sum','liquid_cost',
                                    'rentability','rentability_by_year']].to_html(classes='pandas-dataframe', escape=False))
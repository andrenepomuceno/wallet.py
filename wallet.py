#!/usr/bin/python3

from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import os
import logging
import yfinance as yf
import requests
from lxml import html

def scrape_data(url, xpath):
    try:
        response = requests.get(url)
        response.raise_for_status()
        tree = html.fromstring(response.content)
        elements = tree.xpath(xpath)
        return [element.text_content().strip() for element in elements]
    except requests.RequestException as e:
        return [f"Erro ao acessar a URL: {e}"]
    except Exception as e:
        return [f"Erro ao realizar o scraping: {e}"]

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///wallet.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] (%(filename)s:%(funcName)s():%(lineno)d) %(message)s'
)

# ENTRADA_SAIDA = 'Entrada/Saída'    
# DATA = 'Data'
# MOVIMENTACAO = 'Movimentação'
# PRODUTO = 'Produto'
# INSTITUICAO = 'Instituição'
# QUANTIDADE = 'Quantidade'
# PRECO_UNITARIO = 'Preço unitário'
# VALOR_OPERACAO = 'Valor da Operação'

class B3_Movimentation(db.Model): # TODO rename to B3_Movimentations
    id = db.Column(db.Integer, primary_key=True)
    entrada_saida = db.Column(db.String)
    data = db.Column(db.String)
    movimentacao = db.Column(db.String)
    produto = db.Column(db.String)
    instituicao = db.Column(db.String)
    quantidade = db.Column(db.Float)
    preco_unitario = db.Column(db.Float)
    valor_operacao = db.Column(db.Float)

    def __repr__(self):
        return f'<B3_Movimentation {self.id}>'
    
class B3_Negotiation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String)
    tipo = db.Column(db.String)
    mercado = db.Column(db.String)
    prazo = db.Column(db.String)
    instituicao = db.Column(db.String)
    codigo = db.Column(db.String)
    quantidade = db.Column(db.Float)
    preco = db.Column(db.Float)
    valor = db.Column(db.Float)

    def __repr__(self):
        return f'<B3_Negotiation {self.id}>'

def process_b3_movimentation(file_path):
    app.logger.info(f'Processing file: {file_path}')
    
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    elif file_path.endswith('.xlsx'):
        df = pd.read_excel(file_path)

    df['Data'] = pd.to_datetime(df['Data'], format='%d/%m/%Y').dt.strftime('%Y-%m-%d')
    df['Preço unitário'] = pd.to_numeric(df['Preço unitário'], errors='coerce').fillna(0.0)
    df['Valor da Operação'] = pd.to_numeric(df['Valor da Operação'], errors='coerce').fillna(0.0)
    df['Quantidade'] = pd.to_numeric(df['Quantidade'], errors='coerce').fillna(0.0)
    df['Produto'] = df['Produto'].str.strip()

    app.logger.info('Inserting data into database...')
    for _, row in df.iterrows():
        # Verifica se a entrada já existe
        if not B3_Movimentation.query.filter_by(entrada_saida=row['Entrada/Saída'], data=row['Data'], movimentacao=row['Movimentação'],
                                          produto=row['Produto'], instituicao=row['Instituição'], quantidade=row['Quantidade']).first():
            new_entry = B3_Movimentation(
                entrada_saida=row['Entrada/Saída'],
                data=row['Data'],
                movimentacao=row['Movimentação'],
                produto=row['Produto'],
                instituicao=row['Instituição'],
                quantidade=row['Quantidade'],
                preco_unitario=row['Preço unitário'],
                valor_operacao=row['Valor da Operação']
            )
            db.session.add(new_entry)
    db.session.commit()

    return df

def process_b3_negotiation(file_path):
    app.logger.info(f'Processing B3 Negotiation file: {file_path}')
    
    if file_path.endswith('.xlsx'):
        df = pd.read_excel(file_path)

    df['Data do Negócio'] = pd.to_datetime(df['Data do Negócio'], format='%d/%m/%Y').dt.strftime('%Y-%m-%d')
    df['Quantidade'] = pd.to_numeric(df['Quantidade'], errors='coerce').fillna(0.0)
    df['Preço'] = pd.to_numeric(df['Preço'], errors='coerce').fillna(0.0)
    df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0.0)

    app.logger.info('Inserting data into database...')
    for _, row in df.iterrows():
        if not B3_Negotiation.query.filter_by(
            data=row['Data do Negócio'],                                  
            tipo=row['Tipo de Movimentação'],
            mercado=row['Mercado'],
            prazo=row['Prazo/Vencimento'],
            instituicao=row['Instituição'],
            codigo=row['Código de Negociação'],
            quantidade=row['Quantidade'],
            preco=row['Preço'],
            valor=row['Valor']
        ).first():
            new_entry = B3_Negotiation(
                data=row['Data do Negócio'],
                tipo=row['Tipo de Movimentação'],
                mercado=row['Mercado'],
                prazo=row['Prazo/Vencimento'],
                instituicao=row['Instituição'],
                codigo=row['Código de Negociação'],
                quantidade=row['Quantidade'],
                preco=row['Preço'],
                valor=row['Valor']
            )
            db.session.add(new_entry)
    db.session.commit()

    return df

def b3_movimentation_sql_to_df(result):
    df = pd.DataFrame([(d.entrada_saida, d.data, d.movimentacao, d.produto, 
                        d.instituicao, d.quantidade, d.preco_unitario, d.valor_operacao) for d in result], 
                      columns=['Entrada/Saída', 'Data', 'Movimentação', 'Produto',
                               'Instituição', 'Quantidade', 'Preço unitário', 'Valor da Operação'])
    df['Data'] = pd.to_datetime(df['Data'])
    return df

def b3_negotiation_sql_to_df(result):
    df = pd.DataFrame([(d.data, d.tipo, d.mercado, d.prazo, 
                        d.instituicao, d.codigo, d.quantidade, d.preco,
                        d.valor) for d in result], 
                      columns=['Data do Negócio', 'Tipo de Movimentação', 'Mercado', 'Prazo/Vencimento',
                               'Instituição', 'Código de Negociação', 'Quantidade', 'Preço',
                               'Valor'])
    df['Data do Negócio'] = pd.to_datetime(df['Data do Negócio'])
    return df

def view_movimentation_request(request):
    app.logger.info('view_movimentation_request')

    df = pd.DataFrame()
    query = B3_Movimentation.query.order_by(B3_Movimentation.data.asc())

    if request.method == 'POST':
        filters = request.form.to_dict()
        for key, value in filters.items():
            if value:
                column = getattr(B3_Movimentation, key, None)
                if column is not None:
                    if isinstance(column.type, db.Float):
                        # Filtragem para campos numéricos
                        query = query.filter(column == float(value))
                    else:
                        # Filtragem para campos textuais e de data
                        query = query.filter(column.like(f'%{value}%'))

    result = query.all()
    df = b3_movimentation_sql_to_df(result)
    if len(df) == 0:
        return df
    
    df['Produto_Parsed'] = df['Produto'].str.extract(r'^([A-Z0-9]{4}|[a-zA-Z0-9 .]+)', expand=False)
    df['Produto_Parsed'].fillna('', inplace=True)
    print(df['Produto_Parsed'].value_counts())
    #print(df['Produto'].value_counts())

    df['Ticker'] = parse_ticker(df['Produto'])

    grouped = df[['Entrada/Saída', 'Movimentação']].groupby(['Entrada/Saída'])
    print(grouped.value_counts())

    # print(df['Movimentação'].value_counts())

    return df

def view_negotiation_request(request):
    app.logger.info('view_negotiation_request')

    query = B3_Negotiation.query.order_by(B3_Negotiation.data.asc())
    result = query.all()
    df = b3_negotiation_sql_to_df(result)
    return df

def parse_ticker(column):
    result = column.str.extract(r'^([A-Z0-9]{4}[0-9]{1,2}|[a-zA-Z0-9 .]+)', expand=False)
    result.fillna('', inplace=True)
    return result

def view_asset_request(request, asset):
    app.logger.info(f'Processing view asset request for "{asset}".')

    asset_info = {}
    dataframes = {}

    asset_info['name'] = asset
    asset_info['currency'] = 'BRL'

    query = B3_Movimentation.query.filter(B3_Movimentation.produto.like(f'%{asset}%')).order_by(B3_Movimentation.data.asc())
    result = query.all()
    movimentation = b3_movimentation_sql_to_df(result)
    if len(movimentation) == 0:
        return asset_info
    dataframes['movimentation'] = movimentation

    movimentation['Ticker'] = parse_ticker(movimentation['Produto'])
    ticker = movimentation['Ticker'].value_counts().index[0]
    asset_info['ticker'] = ticker

    credit = movimentation.loc[movimentation['Entrada/Saída'] == "Credito"]
    debit = movimentation.loc[movimentation['Entrada/Saída'] == "Debito"]

    buys = credit.loc[
        (
            (credit['Movimentação'] == "Compra")
            | (credit['Movimentação'] == "Desdobro") 
            | (credit['Movimentação'] == "Bonificação em Ativos")
            | (credit['Movimentação'] == "Atualização")
        )
    ]
    dataframes['buys'] = buys
    if len(buys) > 0:
        first_buy = buys.iloc[0]['Data']
        age = pd.to_datetime("today") - first_buy

    sells = debit.loc[
        (
            (debit['Movimentação'] == "Venda")
        )
    ]
    dataframes['sells'] = sells

    wages = credit.loc[
        ((credit['Movimentação'] == "Dividendo") 
         | (credit['Movimentação'] == "Juros Sobre Capital Próprio") 
         | (credit['Movimentação'] == "Reembolso") 
         | (credit['Movimentação'] == "Rendimento")
         | (credit['Movimentação'] == "Leilão de Fração"))
    ]
    wages_sum = wages['Valor da Operação'].sum()

    dataframes['wages'] = wages
    asset_info['wages_sum'] = round(wages_sum, 2)

    rents_wage = credit.loc[(
        (credit['Movimentação'] == "Empréstimo")
        & (credit['Valor da Operação'] > 0)
    )]
    rents_wages_sum = rents_wage['Valor da Operação'].sum()
    asset_info['rents_wage_sum'] = round(rents_wages_sum, 2)

    dict = {
        "Tesouro Selic 2027": {
            'url': 'https://taxas-tesouro.com/resgatar/tesouro-selic-2027/',
            'xpath': '//*[@id="gatsby-focus-wrapper"]/div/div[2]/main/div[1]/div/div[1]/div[4]/div[2]/span'
        }
    }
    # print(scrape_data('https://taxas-tesouro.com/resgatar/tesouro-selic-2027/', '//*[@id="gatsby-focus-wrapper"]/div/div[2]/main/div[1]/div/div[1]/div[4]/div[2]/span'))

    query = B3_Negotiation.query.filter(B3_Negotiation.codigo.like(f'%{ticker}%')).order_by(B3_Negotiation.data.asc())
    result = query.all()
    negotiation = b3_negotiation_sql_to_df(result)
    last_close_price = None
    if len(negotiation) > 0:
        dataframes['negotiation'] = negotiation

        negotiation_buys = negotiation.loc[
            (
                (negotiation['Tipo de Movimentação'] == "Compra")
            )
        ]
        dataframes['negotitation_buys'] = negotiation_buys

        first_buy = negotiation_buys.iloc[0]['Data do Negócio']
        age = pd.to_datetime("today") - first_buy

        negotiation_sells = negotiation.loc[
            (
                (negotiation['Tipo de Movimentação'] == "Venda")
            )
        ]
        dataframes['negotitation_sells'] = negotiation_sells

        def consolidate(movimentation, negotiation, tipo):
            df1 = movimentation[["Data", "Movimentação", "Quantidade", "Preço unitário", "Valor da Operação"]]

            df2 = negotiation.copy()
            df2.rename(columns={"Data do Negócio": "Data", "Preço": "Preço unitário", "Valor": "Valor da Operação"}, inplace=True)
            df2["Movimentação"] = tipo
            df2 = df2[["Data", "Movimentação", "Quantidade", "Preço unitário", "Valor da Operação"]]

            df_merged = pd.concat([df1, df2], ignore_index=True)
            df_merged.sort_values(by='Data', inplace=True)

            return df_merged

        buys = consolidate(buys, negotiation_buys, 'Compra')
        dataframes['buys'] = buys
        sells = consolidate(sells, negotiation_sells, 'Venda')
        dataframes['sells'] = sells

        stock = yf.Ticker(ticker + ".SA")
        hist = stock.history(period="1d")
        if not hist.empty:
            last_close_price = hist['Close'].iloc[-1]
            asset_info['last_close_price'] = round(last_close_price, 2)
        # try:
        #     currency = stock.info['currency']
        #     asset_info['currency'] = currency
        # except KeyError:
        #     pass

    else:
        print('Warning! Negotiation data not found!')
        dataframes['negotiation'] = pd.DataFrame(columns=['Data do Negócio', 'Tipo de Movimentação', 'Mercado', 'Prazo/Vencimento',
                                                          'Instituição', 'Código de Negociação', 'Quantidade', 'Preço','Valor'])
        # return asset_info

    asset_info['first_buy'] = first_buy.strftime("%Y-%m-%d")
    asset_info['age'] = age.days

    buys_sum = buys['Quantidade'].sum()
    asset_info['buys_sum'] = buys_sum

    total_sell = sells['Valor da Operação'].sum()
    asset_info['total_sell'] = total_sell

    total_cost = buys['Valor da Operação'].sum() - total_sell
    asset_info['total_cost'] = round(total_cost, 2)

    liquid_cost = total_cost - wages_sum - rents_wages_sum
    asset_info['liquid_cost'] = round(liquid_cost, 2)

    buys_wsum = (buys['Quantidade'] * buys['Preço unitário']).sum()
    buys_quantity = buys['Quantidade'].sum()
    buy_avg_price = buys_wsum / buys_quantity if buys_quantity > 0 else 0
    asset_info['buy_avg_price'] = round(buy_avg_price, 2)

    sells_sum = sells['Quantidade'].sum()
    asset_info['sells_sum'] = round(sells_sum, 2)

    position = buys_sum - sells_sum
    asset_info['position'] = position

    asset_info['rented'] = 0
    rented = asset_info['rented']

    position_sum = round(position + rented, 2)
    asset_info['position_sum'] = position_sum

    if last_close_price != None:
        position_total = position_sum * last_close_price
        asset_info['position_total'] = round(position_total, 2)

        rentabiliy = position_total/liquid_cost
        asset_info['rentability'] = round((rentabiliy - 1) * 100, 2)
        

    print(asset_info)

    asset_info['dataframes'] = dataframes
    return asset_info

def analyse_rents(asset_info, dataframes):
    app.logger.debug('Analyzing rents...')

    credit = dataframes['credit']
    sells = dataframes['sells']
    buys = dataframes['buys']

    rents = credit.loc[
        ((credit['Movimentação'] == "Empréstimo"))
        # & ((credit['Quantidade'] > 0))
        # & ((credit['Preço unitário'] == 0))
        # & ((credit['Valor da Operação'] == 0))
    ]

    # dados corrompidos na tabela de rent3, quantidade = 48 onde deveria ser 24
    # bug em abev3, quantidade = 249, varias movimentações nos dias 2022-12-02
    rents = rents.groupby(['Data'], as_index=False).agg({'Quantidade': 'sum', 'Valor da Operação': 'sum'})
    dataframes['rents'] = rents

    print('--- Rents ---')
    print(rents.to_string())

    rents_income_sum = rents['Valor da Operação'].sum()
    asset_info['rents_income_sum'] = rents_income_sum

    rented = 0
    finished_rents = 0
    rents_not_found = 0
    sells_remove_list = []
    buys_remove_list = []
    for _, rent_row in rents.iterrows():
        quantity = rent_row['Quantidade']
        start = rent_row['Data']
        op_value = rent_row['Valor da Operação']

        print(f'\nAnalyzing start = {start} quant = {quantity} value = {op_value}')
        print(f'Rented = {rented}')

        if op_value > 0:
            print(f'Rent payment, skipping...')
            continue

        #print(f'Searching rent {quantity} {start}')
        rent_liquidation = sells.loc[(
            sells['Quantidade'] <= quantity) 
            & (sells['Data'] >= start)
            & (sells['Data'] < start + pd.Timedelta(days=7))
            & (sells['Movimentação'] == "Transferência - Liquidação")
            # & (sells['Preço unitário'] == 0)
            # & (sells['Valor da Operação'] == 0)
        ]
        rent_liquidation_len = len(rent_liquidation)

        if rent_liquidation_len == 0:
            print("Warning! Rent liquidation not found!")
            rents_not_found += 1
            continue
            
        rent_liquidation = rent_liquidation[['Data','Quantidade']]
        print(f'rent_liquidation=\n{rent_liquidation.to_string()}')

        liquidation_sum = 0
        iterations = 0
        rent_liquidation_list = []
        for idx, liquidation_row in rent_liquidation.iterrows():
            liquidation_sum += liquidation_row['Quantidade']
            iterations += 1
            rent_liquidation_list.append(idx)
            if liquidation_sum == quantity:
                print(f'Rent liquidated with {iterations} iterations')
                sells_remove_list += rent_liquidation_list
                break
            elif liquidation_sum > quantity:
                print(f'Warning! rent_sell_sum > quantity')
                break
        
        if liquidation_sum != quantity:
            print(f'Warning! Rent liquidation not found! (fractions)')
            rents_not_found += 1
            continue

        rented += liquidation_sum

        rent_refund = buys.loc[(
            (buys['Quantidade'] == quantity) 
            & (buys['Data'] >= start)
            & (buys['Movimentação'] == "Transferência - Liquidação")
        )]
        rent_refund_len = len(rent_refund)

        rent_refund_list = []
        if rent_refund_len > 0:
            rent_refund = rent_refund[['Data','Quantidade']]
            print(f'rent_refund=\n{rent_refund.to_string()}')    

            print("Exact rent refund found! Getting head...")
            head = rent_refund.iloc[0]
            refund_date = head['Data']

            print(f"Refund date: {refund_date}")
            print(f"Duration: {refund_date - start}")

            rented -= head['Quantidade']
            finished_rents += 1

            rent_refund_list.append(rent_refund.index[0])
            buys_remove_list += rent_refund_list

            continue
        else:
            print("Warning! Exact rent refund not found! Trying fractions...")

        rent_refund_frac = buys.loc[(
            (buys['Quantidade'] < quantity) 
            & (buys['Data'] >= start)
            & (buys['Movimentação'] == "Transferência - Liquidação")
        )]
        rent_refund_frac_len = len(rent_refund_frac)

        if rent_refund_frac_len == 0:
            print("Warning! Fractioned rent refund not found! Still in rent?...")
            continue

        rent_refund_frac = rent_refund_frac[['Data','Quantidade']]
        print(f'rent_refund_frac=\n{rent_refund_frac.to_string()}')

        refund_sum = 0
        iterations = 0
        for idx, refund_row in rent_refund_frac.iterrows():
            refund_sum += refund_row['Quantidade']
            iterations += 1

            rent_refund_list.append(idx)

            if refund_sum == quantity:
                print(f'Rent refunded with {iterations} iterations')
                refund_date = refund_row['Data']

                print(f"Refund date: {refund_date}")
                print(f"Duration: {refund_date - start}")

                rented -= quantity
                finished_rents += 1

                buys_remove_list += rent_refund_list

                sells
                break
            elif refund_sum > quantity:
                print(f'Warning! rent_sell_sum > quantity')
                break
                
        if refund_sum != quantity:
            print("Warning! Fractioned rent refund not found! Still in rent?...")

    asset_info['rented'] = rented
    asset_info['finished_rents'] = finished_rents
    asset_info['sells_remove_list'] = sells_remove_list
    asset_info['buys_remove_list'] = buys_remove_list

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

@app.route('/view/<asset>', methods=['GET'])
def view_asset(asset=None):
    asset_info = view_asset_request(request, asset)

    dataframes = asset_info['dataframes']
    wages = dataframes['wages']
    all_events = dataframes['movimentation']
    all_negotiation = dataframes['negotiation']
    buys_events = dataframes['buys']
    sells_events = dataframes['sells']
    # negotiation_buys = dataframes['negotiation_buys']
    # negotiation_sells = dataframes['negotiation_sells']
    return render_template(
        'view_asset.html', info=asset_info, 
        buys_events=[buys_events[['Data','Movimentação','Quantidade','Preço unitário', 'Valor da Operação']].to_html(classes='pandas-dataframe')],
        sells_events=[sells_events[['Data','Movimentação','Quantidade','Preço unitário', 'Valor da Operação']].to_html(classes='pandas-dataframe')],
        wages_events=[wages[['Data', 'Valor da Operação', 'Movimentação']].to_html(classes='pandas-dataframe')],

        # negotiation_buys=[negotiation_buys[['Data do Negócio','Quantidade','Preço', 'Valor']].to_html(classes='pandas-dataframe')],
        # negotiation_sells=[negotiation_sells[['Data do Negócio','Quantidade','Preço', 'Valor']].to_html(classes='pandas-dataframe')]

        all_negotiation=[all_negotiation[['Data do Negócio','Tipo de Movimentação','Quantidade','Preço','Valor']].to_html()],
        all_events=[all_events[['Data','Entrada/Saída','Movimentação', 'Quantidade', 
                                'Preço unitário', 'Valor da Operação']].to_html(classes='pandas-dataframe')]
    )

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

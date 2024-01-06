from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import os
import logging

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///wallet.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] (%(filename)s:%(funcName)s():%(lineno)d) %(message)s'
)

class Investment(db.Model):
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
        return f'<Investment {self.id}>'

# ENTRADA_SAIDA = 'Entrada/Saída'    
# DATA = 'Data'
# MOVIMENTACAO = 'Movimentação'
# PRODUTO = 'Produto'
# INSTITUICAO = 'Instituição'
# QUANTIDADE = 'Quantidade'
# PRECO_UNITARIO = 'Preço unitário'
# VALOR_OPERACAO = 'Valor da Operação'

def process_file(file_path):
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

    return df

def insert_data_into_db(df):
    app.logger.info('Inserting data into database...')

    for _, row in df.iterrows():
        # Verifica se a entrada já existe
        if not Investment.query.filter_by(entrada_saida=row['Entrada/Saída'], data=row['Data'], movimentacao=row['Movimentação'],
                                          produto=row['Produto'], instituicao=row['Instituição'], quantidade=row['Quantidade']).first():
            new_entry = Investment(
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

def query_to_dataframe(result):
    df = pd.DataFrame([(d.entrada_saida, d.data, d.movimentacao, d.produto, 
                        d.instituicao, d.quantidade, d.preco_unitario, d.valor_operacao) for d in result], 
                      columns=['Entrada/Saída', 'Data', 'Movimentação', 'Produto',
                               'Instituição', 'Quantidade', 'Preço unitário', 'Valor da Operação'])
    return df

def view_request(request):
    app.logger.info('Precessing view request.')

    df = pd.DataFrame()
    query = Investment.query.order_by(Investment.data.asc())

    if request.method == 'POST':
        filters = request.form.to_dict()
        for key, value in filters.items():
            if value:
                column = getattr(Investment, key, None)
                if column is not None:
                    if isinstance(column.type, db.Float):
                        # Filtragem para campos numéricos
                        query = query.filter(column == float(value))
                    else:
                        # Filtragem para campos textuais e de data
                        query = query.filter(column.like(f'%{value}%'))

    result = query.all()
    df = query_to_dataframe(result)
    if len(df) == 0:
        return df
    
    df['Produto_Parsed'] = df['Produto'].str.extract(r'^([A-Z0-9]{4}|Tesouro Selic [0-9]+)', expand=False)
    df['Produto_Parsed'].fillna('', inplace=True)
    print(df['Produto_Parsed'].value_counts())
    #print(df['Produto'].value_counts())

    df['Ticker'] = df['Produto'].str.extract(r'^([A-Z0-9]{4}[0-9]{1,2}|Tesouro Selic [0-9]+)', expand=False)
    df['Ticker'].fillna('', inplace=True)

    grouped = df[['Entrada/Saída', 'Movimentação']].groupby(['Entrada/Saída'])
    print(grouped.value_counts())

    return df

def view_asset_request(request, asset):
    app.logger.info(f'Processing view asset request for "{asset}".')

    asset_info = {}
    dataframes = {}

    asset_info['name'] = asset
    asset_info['ticker'] = asset

    query = Investment.query.filter(Investment.produto.like(f'%{asset}%')).order_by(Investment.data.asc())
    result = query.all()
    df = query_to_dataframe(result)
    if len(df) == 0:
        return asset_info
    
    df['Data'] = pd.to_datetime(df['Data'])
    dataframes['all'] = df

    grouped = df[['Entrada/Saída', 'Movimentação']].groupby(['Entrada/Saída'])
    print(grouped.value_counts())

    credit = df.loc[df['Entrada/Saída'] == "Credito"]
    debit = df.loc[df['Entrada/Saída'] == "Debito"]

    buys = credit.loc[
        (
            (credit['Movimentação'] == "Compra")
            | (credit['Movimentação'] == "Transferência - Liquidação")
            # | (credit['Movimentação'] == "Transferência") 
            | (credit['Movimentação'] == "Desdobro") 
            # | (credit['Movimentação'] == "Recibo de Subscrição")
            | (credit['Movimentação'] == "Bonificação em Ativos")
            | (credit['Movimentação'] == "Atualização")
        )
    ]
    buys_sum = buys['Quantidade'].sum()
    first_buy = buys.iloc[0]['Data']
    age = pd.to_datetime("today") - first_buy

    asset_info['buys_sum'] = buys_sum
    asset_info['first_buy'] = first_buy.strftime("%Y-%m-%d")
    asset_info['age'] = age.days

    sells = debit.loc[
        (
            (debit['Movimentação'] == "Venda")
            | (debit['Movimentação'] == "Transferência - Liquidação")
            # | (credit['Movimentação'] == "Transferência")
        )
    ]
    sells_sum = sells['Quantidade'].sum()
    position = buys_sum - sells_sum

    asset_info['sells_sum'] = sells_sum
    asset_info['position'] = position

    incomes = credit.loc[
        ((credit['Movimentação'] == "Dividendo") 
         | (credit['Movimentação'] == "Juros Sobre Capital Próprio") 
         | (credit['Movimentação'] == "Reembolso") 
         | (credit['Movimentação'] == "Rendimento")
         | (credit['Movimentação'] == "Leilão de Fração"))
    ]
    incomes_sum = incomes['Valor da Operação'].sum()

    dataframes['incomes'] = incomes
    asset_info['incomes_sum'] = incomes_sum

    rents = credit.loc[
        ((credit['Movimentação'] == "Empréstimo"))
        # & ((credit['Quantidade'] > 0))
        # & ((credit['Preço unitário'] == 0))
        & ((credit['Valor da Operação'] == 0))
    ]

    rents_income = credit.loc[
        ((credit['Movimentação'] == "Empréstimo"))
        # & ((credit['Quantidade'] > 0))
        # & ((credit['Preço unitário'] == 0))
        & ((credit['Valor da Operação'] > 0))
    ]
    # print(rents_payments.to_string())
    rents_income_sum = rents_income['Valor da Operação'].sum()

    asset_info['rents_income_sum'] = rents_income_sum

    app.logger.debug('Analyzing rents...')
    rented = 0
    finished_rents = 0
    for _, row in rents.iterrows():
        quantity = row['Quantidade']
        start = row['Data']

        #print(f'Searching rent {quantity} {start}')
        rent_sell = sells.loc[(sells['Quantidade'] == quantity) & (sells['Data'] == start)]
        rent_sell_len = len(rent_sell)
        if rent_sell_len > 0:
            if rent_sell_len > 1:
                print("Warning! More than 1 rent_sell found for the same date and quantity.")
            # print(rent_sell.to_string())
            rent_buy = buys.loc[(buys['Quantidade'] == quantity) & (buys['Data'] >= start)]
            rent_buy_len = len(rent_buy)
            if rent_buy_len > 0:
                end = rent_buy.iloc[0]['Data']
                print(f'Rent of {quantity} started on {start} and ended on {end}. Duration: {end - start}')
                finished_rents += 1
            else:
                print(f'Rent of {quantity} started on {start} and is not finished yet. Duration: {pd.to_datetime("today") - start}')
                rented += quantity

    asset_info['rented'] = rented
    asset_info['finished_rents'] = finished_rents
    asset_info['position_sum'] = position + rented

    print('--- Buys ---')
    print(buys.to_string())
    print('--- Sells ---')
    print(sells.to_string())
    print('--- Incomes ---')
    print(incomes.to_string())
    print('--- Rents ---')
    print(rents.to_string())
    print(asset_info)

    asset_info['dataframes'] = dataframes

    return asset_info

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        file = request.files['file']
        if file:
            filepath = os.path.join('uploads', file.filename)
            file.save(filepath)
            app.logger.debug(f'File {file.filename} saved at {filepath}.')

            df = process_file(filepath)
            insert_data_into_db(df)

            return redirect(url_for('view_table'))
        else:
            app.logger.debug('No file provided for upload.')

    return render_template('index.html', message='')

@app.route('/view', methods=['GET', 'POST'])
def view_table():
    df = view_request(request)
    return render_template('view_table.html', tables=[df.to_html(classes='pandas-dataframe')])

@app.route('/view/<asset>', methods=['GET'])
def view_asset(asset=None):
    asset_info = view_asset_request(request, asset)
    dataframes = asset_info['dataframes']
    incomes_df = dataframes['incomes']
    return render_template('view_asset.html', info=asset_info, income_events=[incomes_df.to_html(classes='pandas-dataframe')])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

from app import app, db
from flask import abort, flash
import pandas as pd
import re

# ENTRADA_SAIDA = 'Entrada/Saída'    
# DATA = 'Data'
# MOVIMENTACAO = 'Movimentação'
# PRODUTO = 'Produto'
# INSTITUICAO = 'Instituição'
# QUANTIDADE = 'Quantidade'
# PRECO_UNITARIO = 'Preço unitário'
# VALOR_OPERACAO = 'Valor da Operação'

class B3_Movimentation(db.Model):
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

def process_b3_movimentation(df):
    app.logger.info(f'Processing B3 Movimentation...')

    df['Data'] = pd.to_datetime(df['Data'], format='%d/%m/%Y').dt.strftime('%Y-%m-%d')
    df['Preço unitário'] = pd.to_numeric(df['Preço unitário'], errors='coerce').fillna(0.0)
    df['Valor da Operação'] = pd.to_numeric(df['Valor da Operação'], errors='coerce').fillna(0.0)
    df['Quantidade'] = pd.to_numeric(df['Quantidade'], errors='coerce').fillna(0.0)
    df['Produto'] = df['Produto'].str.strip()

    app.logger.info('Inserting data into database...')
    duplicates = 0
    added = 0
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
            added += 1
        else:
            duplicates += 1
    db.session.commit()

    flash(f'Rows Added: {added}')
    flash(f'Duplicated rows discarded: {duplicates}')

    return df

def b3_movimentation_sql_to_df(result):
    df = pd.DataFrame([(d.entrada_saida, d.data, d.movimentacao, d.produto, 
                        d.instituicao, d.quantidade, d.preco_unitario, d.valor_operacao) for d in result], 
                      columns=['Entrada/Saída', 'Data', 'Movimentação', 'Produto',
                               'Instituição', 'Quantidade', 'Preço unitário', 'Valor da Operação'])
    df['Data'] = pd.to_datetime(df['Data'])

    df = df.rename(columns={
        'Data': 'Date',
        'Quantidade': 'Quantity',
        'Movimentação': 'Movimentation',
        'Preço unitário': 'Price',
        'Valor da Operação': 'Total'
    })

    return df

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

def process_b3_negotiation(df):
    app.logger.info(f'Processing B3 Negotiation...')
    
    df['Data do Negócio'] = pd.to_datetime(df['Data do Negócio'], format='%d/%m/%Y').dt.strftime('%Y-%m-%d')
    df['Quantidade'] = pd.to_numeric(df['Quantidade'], errors='coerce').fillna(0.0)
    df['Preço'] = pd.to_numeric(df['Preço'], errors='coerce').fillna(0.0)
    df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0.0)

    app.logger.info('Inserting data into database...')
    duplicates = 0
    added = 0
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
            added += 1
        else:
            duplicates += 1
    db.session.commit()

    flash(f'Rows Added: {added}')
    flash(f'Duplicated rows discarded: {duplicates}')

    return df

def b3_negotiation_sql_to_df(result):
    df = pd.DataFrame([(d.data, d.tipo, d.mercado, d.prazo, 
                        d.instituicao, d.codigo, d.quantidade, d.preco,
                        d.valor) for d in result], 
                      columns=['Data do Negócio', 'Tipo de Movimentação', 'Mercado', 'Prazo/Vencimento',
                               'Instituição', 'Código de Negociação', 'Quantidade', 'Preço',
                               'Valor'])
    df['Data do Negócio'] = pd.to_datetime(df['Data do Negócio'])

    df = df.rename(columns={
        'Data do Negócio': 'Date',
        'Quantidade': 'Quantity',
        'Tipo de Movimentação': 'Movimentation',
        'Preço': 'Price',
        'Valor': 'Total'
    })

    return df

class Avenue_Extract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String)
    hora = db.Column(db.String)
    liquidacao = db.Column(db.String)
    descricao = db.Column(db.String)
    valor = db.Column(db.Float)
    saldo = db.Column(db.Float)

    entrada_saida = db.Column(db.String)
    produto = db.Column(db.String)
    movimentacao = db.Column(db.String)
    quantidade = db.Column(db.Float)
    preco_unitario = db.Column(db.Float)

    def __repr__(self):
        return f'<Avenue_Extract {self.id}>'

def extract_fill(df):
    def parse_entrada_saida(x):
        if re.match(r'Câmbio Instantâneo|Câmbio Padrão|Compra|Dividendos|Estorno', x):
            return 'Credito'
        else:
            return 'Debito'
    df['Entrada/Saída'] = df['Descrição'].apply(parse_entrada_saida)

    def parse_produto(x):
        match = re.search(r'(Compra de [0-9.]+|Dividendos|Corretagem) ([A-Z]{1,4})', x)
        if match:
            return match.group(2)
        else:
            return ''
    df['Produto'] = df['Descrição'].apply(parse_produto)

    def parse_movimentacao(x):
        match = re.search(r'Câmbio|Compra|Impostos|Dividendos|Corretagem', x)
        if match:
            return match.group(0)
        else:
            return '???'
    df['Movimentação'] = df['Descrição'].apply(parse_movimentacao)

    def parse_quantidade(x):
        match = re.search(r'Compra de ([0-9.]+)', x)
        if match:
            return float(match.group(1))
        else:
            return None
    df['Quantidade'] = df['Descrição'].apply(parse_quantidade)

    def parse_preco_unitario(x):
        match = re.search(r'\$ ?([0-9.]+)', x)
        if match:
            return float(match.group(1))
        else:
            return None
    df['Preço unitário'] = df['Descrição'].apply(parse_preco_unitario)

    return df

def process_avenue_extract(df):
    app.logger.info(f'Processing Avenue Extract file...')

    df['Data'] = pd.to_datetime(df['Data'], format='%d/%m/%Y').dt.strftime('%Y-%m-%d')
    df['Liquidação'] = pd.to_datetime(df['Liquidação'], format='%d/%m/%Y').dt.strftime('%Y-%m-%d')
    df['Valor (U$)'] = pd.to_numeric(df['Valor (U$)'], errors='coerce').fillna(0.0)
    df['Saldo da conta (U$)'] = pd.to_numeric(df['Saldo da conta (U$)'], errors='coerce').fillna(0.0)

    df = extract_fill(df)

    app.logger.info('Inserting data into database...')
    duplicates = 0
    added = 0
    for _, row in df.iterrows():
        # Verifica se a entrada já existe
        if not Avenue_Extract.query.filter_by(
            data=row['Data'],                                  
            hora=row['Hora'],
            liquidacao=row['Liquidação'],
            descricao=row['Descrição'],
            valor=row['Valor (U$)'],
            saldo=row['Saldo da conta (U$)'],

            entrada_saida=row['Entrada/Saída'],
            produto=row['Produto'],
            movimentacao=row['Movimentação'],
            quantidade=row['Quantidade'],
            preco_unitario=row['Preço unitário']
        ).first():
            new_entry = Avenue_Extract(
                data=row['Data'],
                hora=row['Hora'],
                liquidacao=row['Liquidação'],
                descricao=row['Descrição'],
                valor=row['Valor (U$)'],
                saldo=row['Saldo da conta (U$)'],

                entrada_saida=row['Entrada/Saída'],
                produto=row['Produto'],
                movimentacao=row['Movimentação'],
                quantidade=row['Quantidade'],
                preco_unitario=row['Preço unitário']
            )
            db.session.add(new_entry)
            added += 1
        else:
            duplicates += 1
    db.session.commit()

    flash(f'Rows Added: {added}')
    flash(f'Duplicated rows discarded: {duplicates}')

    return df

def avenue_extract_sql_to_df(result):
    df = pd.DataFrame([(d.data, d.hora, d.liquidacao, d.descricao, 
                        d.valor, d.saldo,
                        d.entrada_saida, d.produto, d.movimentacao, d.quantidade, d.preco_unitario) for d in result], 
                      columns=['Data', 'Hora', 'Liquidação', 'Descrição',
                               'Valor (U$)', 'Saldo da conta (U$)',
                               'Entrada/Saída', 'Produto', 'Movimentação', 'Quantidade', 'Preço unitário'])
    df['Data'] = pd.to_datetime(df['Data'])
    df['Liquidação'] = pd.to_datetime(df['Liquidação'])

    df = df.rename(columns={
        'Data': 'Date',
        'Quantidade': 'Quantity',
        'Movimentação': 'Movimentation',
        'Preço unitário': 'Price',
        'Valor (U$)': 'Total'
    })

    return df

class Generic_Extract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String)
    asset = db.Column(db.String)
    movimentation = db.Column(db.String)
    quantity = db.Column(db.Float)
    price = db.Column(db.Float)
    total = db.Column(db.Float)

    def __repr__(self):
        return f'<Generic_Extract {self.id}>'

def process_generic_extract(df):
    app.logger.info(f'Processing Generic Extract file...')

    df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d').dt.strftime('%Y-%m-%d')
    df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0.0)
    df['Price'] = pd.to_numeric(df['Price'], errors='coerce').fillna(0.0)
    df['Total'] = pd.to_numeric(df['Total'], errors='coerce').fillna(0.0)
    df['Movimentation'] = df['Movimentation'].fillna('')
    
    print(df.to_string())

    app.logger.info('Inserting data into database...')
    duplicates = 0
    added = 0
    for _, row in df.iterrows():
        # Verifica se a entrada já existe
        if not Generic_Extract.query.filter_by(
            date=row['Date'],
            asset=row['Asset'],
            movimentation=row['Movimentation'],
            quantity=row['Quantity'],
            price=row['Price'],
            total=row['Total']
        ).first():
            new_entry = Generic_Extract(
                date=row['Date'],
                asset=row['Asset'],
                movimentation=row['Movimentation'],
                quantity=row['Quantity'],
                price=row['Price'],
                total=row['Total']
            )
            db.session.add(new_entry)
            added += 1
        else:
            duplicates += 1
    db.session.commit()

    flash(f'Rows Added: {added}')
    flash(f'Duplicated rows discarded: {duplicates}')

    return df

def generic_extract_sql_to_df(result):
    df = pd.DataFrame([(d.date, d.asset, d.movimentation, d.quantity, 
                        d.price, d.total) for d in result], 
                      columns=['Date', 'Asset', 'Movimentation', 'Quantity',
                               'Price', 'Total'])
    df['Date'] = pd.to_datetime(df['Date'])

    def fill_movimentation(row):
        if row['Movimentation'] == '':
            return 'Buy' if row['Total'] >= 0 else 'Sell'
        else:
            return row['Movimentation']
    df['Movimentation'] = df.apply(fill_movimentation, axis=1)

    return df


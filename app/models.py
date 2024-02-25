from app import db
from app.utils.parsing import parse_b3_ticker
import pandas as pd

class B3Movimentation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    origin_id = db.Column(db.String)

    entrada_saida = db.Column(db.String)
    data = db.Column(db.String)
    movimentacao = db.Column(db.String)
    produto = db.Column(db.String)
    instituicao = db.Column(db.String)
    quantidade = db.Column(db.Float)
    preco_unitario = db.Column(db.Float)
    valor_operacao = db.Column(db.Float)

    def __repr__(self):
        return f'<B3Movimentation {self.id}>'

def b3_movimentation_sql_to_df(result):
    df = pd.DataFrame([(d.entrada_saida, d.data, d.movimentacao, d.produto,
                        d.instituicao, d.quantidade, d.preco_unitario,
                        d.valor_operacao) for d in result],
                      columns=['Entrada/Saída', 'Data', 'Movimentação', 'Produto',
                               'Instituição', 'Quantidade', 'Preço unitário',
                               'Valor da Operação'])
    df['Data'] = pd.to_datetime(df['Data'])

    df = df.rename(columns={
        'Data': 'Date',
        'Quantidade': 'Quantity',
        'Movimentação': 'Movimentation',
        'Preço unitário': 'Price',
        'Valor da Operação': 'Total'
    })

    df['Asset'] = parse_b3_ticker(df['Produto'])

    return df

class B3Negotiation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    origin_id = db.Column(db.String)

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
        return f'<B3Negotiation {self.id}>'

def b3_negotiation_sql_to_df(result):
    df = pd.DataFrame([(d.data, d.tipo, d.mercado, d.prazo,
                        d.instituicao, d.codigo, d.quantidade, d.preco,
                        d.valor) for d in result],
                        columns=[
                            'Data do Negócio', 'Tipo de Movimentação', 'Mercado',
                            'Prazo/Vencimento', 'Instituição', 'Código de Negociação',
                            'Quantidade', 'Preço', 'Valor'
                        ])
    df['Data do Negócio'] = pd.to_datetime(df['Data do Negócio'])
    df['Asset'] = parse_b3_ticker(df['Código de Negociação'])

    df = df.rename(columns={
        'Data do Negócio': 'Date',
        'Quantidade': 'Quantity',
        'Tipo de Movimentação': 'Movimentation',
        'Preço': 'Price',
        'Valor': 'Total'
    })

    return df

class AvenueExtract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    origin_id = db.Column(db.String)

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
        return f'<AvenueExtract {self.id}>'

def avenue_extract_sql_to_df(result):
    df = pd.DataFrame([(
        d.data, d.hora, d.liquidacao, d.descricao,
        d.valor, d.saldo, d.entrada_saida, d.produto,
        d.movimentacao, d.quantidade, d.preco_unitario
    ) for d in result],
    columns=[
        'Data', 'Hora', 'Liquidação', 'Descrição',
        'Valor (U$)', 'Saldo da conta (U$)',
        'Entrada/Saída', 'Produto', 'Movimentação', 'Quantidade',
        'Preço unitário'
    ])
    df['Data'] = pd.to_datetime(df['Data'])
    df['Liquidação'] = pd.to_datetime(df['Liquidação'])
    df['Asset'] = df['Produto']

    df = df.rename(columns={
        'Data': 'Date',
        'Quantidade': 'Quantity',
        'Movimentação': 'Movimentation',
        'Preço unitário': 'Price',
        'Valor (U$)': 'Total'
    })

    return df

class GenericExtract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    origin_id = db.Column(db.String)

    date = db.Column(db.String)
    asset = db.Column(db.String)
    movimentation = db.Column(db.String)
    quantity = db.Column(db.Float)
    price = db.Column(db.Float)
    total = db.Column(db.Float)
    # TODO currency support

    def __repr__(self):
        return f'<GenericExtract {self.id}>'

def generic_extract_sql_to_df(result):
    df = pd.DataFrame([(d.date, d.asset, d.movimentation, d.quantity,
                        d.price, d.total) for d in result],
                      columns=['Date', 'Asset', 'Movimentation', 'Quantity',
                               'Price', 'Total'])
    df['Date'] = pd.to_datetime(df['Date'])

    def fill_movimentation(row):
        if row['Movimentation'] == '':
            return 'Buy' if row['Total'] >= 0 else 'Sell'
        return row['Movimentation']
    df['Movimentation'] = df.apply(fill_movimentation, axis=1)

    return df

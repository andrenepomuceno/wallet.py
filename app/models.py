from app import app, db
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

def fill_table(df):
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

def process_avenue_extract(file_path):
    app.logger.info(f'Processing Avenue Extract file: {file_path}')

    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)

    df['Data'] = pd.to_datetime(df['Data'], format='%d/%m/%Y').dt.strftime('%Y-%m-%d')
    df['Liquidação'] = pd.to_datetime(df['Liquidação'], format='%d/%m/%Y').dt.strftime('%Y-%m-%d')
    df['Valor (U$)'] = pd.to_numeric(df['Valor (U$)'], errors='coerce').fillna(0.0)
    df['Saldo da conta (U$)'] = pd.to_numeric(df['Saldo da conta (U$)'], errors='coerce').fillna(0.0)

    df = fill_table(df)

    app.logger.info('Inserting data into database...')
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
    db.session.commit()

    return df


from app import app, db
from app.models import Avenue_Extract, B3_Movimentation, B3_Negotiation, Generic_Extract
from app.utils.parsing import parse_b3_ticker
from flask import flash
import pandas as pd
import re
import hashlib

def gen_hash(filepath):
    file = open(filepath, 'rb')
    sha256 = hashlib.sha256()
    while True:
        chunk = file.read(1024)
        if not chunk:
            break
        sha256.update(chunk)
    return sha256.hexdigest()

def import_b3_movimentation(df, filepath):
    app.logger.info(f'Processing B3 Movimentation...')

    df['Data'] = pd.to_datetime(df['Data'], format='%d/%m/%Y').dt.strftime('%Y-%m-%d')
    df['Preço unitário'] = pd.to_numeric(df['Preço unitário'], errors='coerce').fillna(0.0)
    df['Valor da Operação'] = pd.to_numeric(df['Valor da Operação'], errors='coerce').fillna(0.0)
    df['Quantidade'] = pd.to_numeric(df['Quantidade'], errors='coerce').fillna(0.0)
    df['Produto'] = df['Produto'].str.strip()

    app.logger.info('Inserting data into database...')
    duplicates = 0
    added = 0

    file_hash = gen_hash(filepath)

    for index, row in df.iterrows():
        # Verifica se a entrada já existe
        # TODO gerar uma assinatura para cada linha importada, levando em consideração o index da tabela de origem. Na tabela de origem podem existir transações válidas idênticas que são consideradas como duplicatas

        originId = f'{filepath}:{file_hash}:{index}'

        if not B3_Movimentation.query.filter_by(originId=originId, entrada_saida=row['Entrada/Saída'], data=row['Data'], movimentacao=row['Movimentação'],
                                          produto=row['Produto'], instituicao=row['Instituição'], quantidade=row['Quantidade']).first():
            new_entry = B3_Movimentation(
                originId=originId,
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

def import_b3_negotiation(df, filepath):
    app.logger.info(f'Processing B3 Negotiation...')
    
    df['Data do Negócio'] = pd.to_datetime(df['Data do Negócio'], format='%d/%m/%Y').dt.strftime('%Y-%m-%d')
    df['Quantidade'] = pd.to_numeric(df['Quantidade'], errors='coerce').fillna(0.0)
    df['Preço'] = pd.to_numeric(df['Preço'], errors='coerce').fillna(0.0)
    df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0.0)

    app.logger.info('Inserting data into database...')
    duplicates = 0
    added = 0
    file_hash = gen_hash(filepath)
    for index, row in df.iterrows():
        originId = f'{filepath}:{file_hash}:{index}'
        if not B3_Negotiation.query.filter_by(
            originId=originId,
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
                originId=originId,
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
        match = re.search(r'Câmbio|Compra|Impostos|Dividendos|Corretagem|Desdobramento', x)
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

def import_avenue_extract(df, filepath):
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

def import_generic_extract(df, filepath):
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
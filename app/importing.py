import re
import hashlib
from flask import flash
import pandas as pd
from app import app, db
from app.models import AvenueExtract, B3Movimentation, B3Negotiation, GenericExtract
from app.utils.memocache import invalidate_processing_cache


def gen_hash(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as file:
        for chunk in iter(lambda: file.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def _coerce_numeric(df, columns):
    for col in columns:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)


def _coerce_date(df, column, fmt):
    df[column] = pd.to_datetime(df[column], format=fmt).dt.strftime('%Y-%m-%d')


def _bulk_insert_with_dedup(model, df, filepath, row_to_kwargs):
    """Generic dedup-aware bulk insert.

    Iterates `df`, builds a unique `origin_id` per row from filepath+sha256+index,
    skips rows whose `origin_id` already exists, otherwise calls
    `row_to_kwargs(row)` and inserts the resulting kwargs into `model`.
    Flashes a summary and commits once at the end.
    """
    app.logger.info('Inserting data into %s...', model.__name__)
    file_hash = gen_hash(filepath)
    added = 0
    duplicates = 0

    existing = {
        oid for (oid,) in db.session.query(model.origin_id).filter(
            model.origin_id.like(f'{filepath}:{file_hash}:%')
        ).all()
    }

    for index, row in df.iterrows():
        origin_id = f'{filepath}:{file_hash}:{index}'
        if origin_id in existing:
            duplicates += 1
            continue
        kwargs = row_to_kwargs(row)
        kwargs['origin_id'] = origin_id
        db.session.add(model(**kwargs))
        added += 1

    db.session.commit()
    if added > 0:
        invalidate_processing_cache()
    flash(f'Rows Added: {added}')
    flash(f'Duplicated rows discarded: {duplicates}')


def import_b3_movimentation(df, filepath):
    app.logger.info('Processing B3 Movimentation...')
    _coerce_date(df, 'Data', '%d/%m/%Y')
    _coerce_numeric(df, ['Preço unitário', 'Valor da Operação', 'Quantidade'])
    df['Produto'] = df['Produto'].str.strip()

    _bulk_insert_with_dedup(B3Movimentation, df, filepath, lambda row: dict(
        entrada_saida=row['Entrada/Saída'],
        data=row['Data'],
        movimentacao=row['Movimentação'],
        produto=row['Produto'],
        instituicao=row['Instituição'],
        quantidade=row['Quantidade'],
        preco_unitario=row['Preço unitário'],
        valor_operacao=row['Valor da Operação'],
    ))
    return df


def import_b3_negotiation(df, filepath):
    app.logger.info('Processing B3 Negotiation...')
    _coerce_date(df, 'Data do Negócio', '%d/%m/%Y')
    _coerce_numeric(df, ['Quantidade', 'Preço', 'Valor'])

    _bulk_insert_with_dedup(B3Negotiation, df, filepath, lambda row: dict(
        data=row['Data do Negócio'],
        tipo=row['Tipo de Movimentação'],
        mercado=row['Mercado'],
        prazo=row['Prazo/Vencimento'],
        instituicao=row['Instituição'],
        codigo=row['Código de Negociação'],
        quantidade=row['Quantidade'],
        preco=row['Preço'],
        valor=row['Valor'],
    ))
    return df


def _safe_str(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ''
    return str(x)


def extract_fill(df):
    df['Descrição'] = df['Descrição'].apply(_safe_str)

    def parse_entrada_saida(x):
        if re.match(r'Câmbio|Compra|Dividendos|Estorno', x):
            return 'Credito'
        return 'Debito'
    df['Entrada/Saída'] = df['Descrição'].apply(parse_entrada_saida)

    def parse_produto(x):
        # Try patterns with quantity first: "Venda de 0,77 ASML", "Compra de 5 NVDA"
        match = re.search(r'(Compra|Venda) de [0-9.,]+ ([A-Z]{1,5})', x)
        if match:
            return match.group(2)
        # Then try without quantity: "Dividendos de MSFT", "Imposto sobre dividendo de MSFT"
        match = re.search(r'(sobre dividendo de|de) ([A-Z]{1,5})', x)
        if match:
            return match.group(2)
        # Old format: "Dividendos MSFT. ***..."
        match = re.search(r'(Dividendos|Corretagem) ([A-Z]{1,4})', x)
        if match:
            return match.group(2)
        return ''
    df['Produto'] = df['Descrição'].apply(parse_produto)

    def parse_movimentacao(x):
        if re.search(r'Imposto sobre dividendo', x):
            return 'Impostos'
        if re.search(r'corretagem', x, re.IGNORECASE):
            return 'Corretagem'
        match = re.search(r'Câmbio|Compra|Venda|Impostos|Dividendos|Corretagem|Desdobramento', x)
        if match:
            return match.group(0)
        return '???'
    df['Movimentação'] = df['Descrição'].apply(parse_movimentacao)

    def parse_quantidade(x):
        match = re.search(r'(Compra de|Venda de) ([0-9.,]+)', x)
        if match:
            return float(match.group(2).replace(',', '.'))
        return None
    df['Quantidade'] = df['Descrição'].apply(parse_quantidade)

    def parse_preco_unitario(x):
        match = re.search(r'\$[\s\xa0]?([0-9.,]+)', x)
        if match:
            return float(match.group(1).replace(',', '.'))
        return None
    df['Preço unitário'] = df['Descrição'].apply(parse_preco_unitario)

    return df


def import_avenue_extract(df, filepath):
    app.logger.info('Processing Avenue Extract file...')

    if 'Data transação' in df.columns:
        app.logger.info('Detected new Avenue format')
        df = df.rename(columns={
            'Data transação': 'Data',
            'Data liquidação': 'Liquidação',
            'Valor': 'Valor (U$)',
            'Saldo': 'Saldo da conta (U$)',
        })
        df['Hora'] = ''
    else:
        app.logger.info('Detected old Avenue format')

    _coerce_date(df, 'Data', '%d/%m/%Y')
    _coerce_date(df, 'Liquidação', '%d/%m/%Y')
    _coerce_numeric(df, ['Valor (U$)', 'Saldo da conta (U$)'])

    df = extract_fill(df)

    _bulk_insert_with_dedup(AvenueExtract, df, filepath, lambda row: dict(
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
        preco_unitario=row['Preço unitário'],
    ))
    return df


def import_generic_extract(df, filepath):
    app.logger.info('Processing Generic Extract file...')
    _coerce_date(df, 'Date', '%Y-%m-%d')
    _coerce_numeric(df, ['Quantity', 'Price', 'Total'])
    df['Movimentation'] = df['Movimentation'].fillna('')

    _bulk_insert_with_dedup(GenericExtract, df, filepath, lambda row: dict(
        date=row['Date'],
        asset=row['Asset'],
        movimentation=row['Movimentation'],
        quantity=row['Quantity'],
        price=row['Price'],
        total=row['Total'],
    ))
    return df

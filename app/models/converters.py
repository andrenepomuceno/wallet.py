"""Adapters that turn ORM result lists into normalized DataFrames."""
import pandas as pd

from app.utils.parsing import parse_b3_ticker


# ---------------------------------------------------------------------------
# Unified Transaction → DataFrame
# ---------------------------------------------------------------------------

# Standard processing columns (used downstream by processing/assets.py).
STD_COLUMNS = [
    'Date', 'Asset', 'Movimentation', 'Quantity', 'Price', 'Total',
    'Category', 'Direction', 'Source', 'RecordType', 'Produto', 'Currency',
    # Avenue-only extras kept for backward compatibility with templates.
    'Hora', 'Liquidação', 'Descrição', 'Saldo da conta (U$)', 'Valor (U$)',
    'Entrada/Saída',
    # B3-negotiation extras
    'Mercado', 'Prazo/Vencimento', 'Instituição', 'Código de Negociação',
]


def transactions_sql_to_df(result):
    """Convert a list of `Transaction` rows into the standard DataFrame.

    Columns include both the canonical names (`Date`, `Movimentation`,
    `Category`, ...) and a handful of legacy aliases (`Produto`,
    `Entrada/Saída`, `Valor (U$)`, ...) so existing templates and
    classifiers keep working unchanged.
    """
    if not result:
        return pd.DataFrame(columns=STD_COLUMNS)

    rows = []
    for t in result:
        meta = t.meta or {}
        rows.append({
            'Date': t.date,
            'Asset': t.asset or '',
            'Movimentation': t.raw_label or '',
            'Quantity': t.quantity if t.quantity is not None else 0.0,
            'Price': t.price if t.price is not None else 0.0,
            'Total': t.total if t.total is not None else 0.0,
            'Category': t.category,
            'Direction': t.direction,
            'Source': t.source,
            'RecordType': t.record_type,
            'Produto': t.product or t.asset or '',
            'Currency': t.currency,
            'Hora': t.time,
            'Liquidação': t.settlement_date,
            'Descrição': t.description,
            'Saldo da conta (U$)': t.balance if t.balance is not None else 0.0,
            'Valor (U$)': t.total if t.total is not None else 0.0,
            'Entrada/Saída': t.direction,
            'Mercado': meta.get('mercado'),
            'Prazo/Vencimento': meta.get('prazo'),
            'Instituição': t.institution,
            'Código de Negociação': t.product if t.record_type == 'negotiation' else None,
        })

    df = pd.DataFrame(rows)
    df['Date'] = pd.to_datetime(df['Date'])
    if 'Liquidação' in df.columns:
        df['Liquidação'] = pd.to_datetime(df['Liquidação'], errors='coerce')
    return df


# ---------------------------------------------------------------------------
# Legacy converters (still used by tests and one-shot migration code).
# Will be removed once Phase 5 deletes the legacy ORM models.
# ---------------------------------------------------------------------------


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


def avenue_extract_sql_to_df(result) -> pd.DataFrame:
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


def generic_extract_sql_to_df(result):
    df = pd.DataFrame([(d.date, d.asset, d.movimentation, d.quantity,
                        d.price, d.total) for d in result],
                      columns=['Date', 'Asset', 'Movimentation', 'Quantity',
                               'Price', 'Total'])
    df['Date'] = pd.to_datetime(df['Date'])

    if len(df) > 0:
        def fill_movimentation(row):
            if row['Movimentation'] == '' or pd.isna(row['Movimentation']):
                return 'Buy' if row['Total'] >= 0 else 'Sell'
            return row['Movimentation']
        df['Movimentation'] = df.apply(fill_movimentation, axis=1)

    return df

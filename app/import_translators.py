"""CSV row → Transaction kwargs translators (one per source).

Each function returns a dict suitable for `Transaction(**kwargs)`. The
caller is responsible for stamping `origin_id`.
"""
import pandas as pd

from app.models import category_mapping
from app.models.category_mapping import classify
from app.utils.parsing import parse_b3_ticker


def _scalar(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return v


def _b3_ticker_from_product(product):
    """Run the same regex parse used by the legacy converter on a single str."""
    s = pd.Series([product or ''])
    return parse_b3_ticker(s).iloc[0]


def b3_movimentation_row(row):
    direction = _scalar(row.get('Entrada/Saída'))
    raw_label = _scalar(row.get('Movimentação')) or ''
    product = _scalar(row.get('Produto')) or ''
    category = classify('b3', 'movimentation', raw_label, direction)
    return dict(
        source='b3',
        record_type='movimentation',
        date=_scalar(row.get('Data')),
        asset=_b3_ticker_from_product(product),
        product=product,
        institution=_scalar(row.get('Instituição')),
        raw_label=raw_label,
        category=category,
        direction=direction,
        quantity=row.get('Quantidade') or 0.0,
        price=row.get('Preço unitário') or 0.0,
        total=row.get('Valor da Operação') or 0.0,
        currency='BRL',
    )


def b3_negotiation_row(row):
    raw_label = _scalar(row.get('Tipo de Movimentação')) or ''
    code = _scalar(row.get('Código de Negociação')) or ''
    category = classify('b3', 'negotiation', raw_label)
    direction = 'Credito' if category == category_mapping.BUY else 'Debito'
    return dict(
        source='b3',
        record_type='negotiation',
        date=_scalar(row.get('Data do Negócio')),
        asset=_b3_ticker_from_product(code),
        product=code,
        institution=_scalar(row.get('Instituição')),
        raw_label=raw_label,
        category=category,
        direction=direction,
        quantity=row.get('Quantidade') or 0.0,
        price=row.get('Preço') or 0.0,
        total=row.get('Valor') or 0.0,
        currency='BRL',
        meta={
            'mercado': _scalar(row.get('Mercado')),
            'prazo': _scalar(row.get('Prazo/Vencimento')),
        },
    )


def avenue_extract_row(row):
    direction = _scalar(row.get('Entrada/Saída'))
    raw_label = _scalar(row.get('Movimentação')) or ''
    produto = _scalar(row.get('Produto')) or ''
    category = classify('avenue', 'extract', raw_label, direction)
    return dict(
        source='avenue',
        record_type='extract',
        date=_scalar(row.get('Data')),
        settlement_date=_scalar(row.get('Liquidação')),
        time=_scalar(row.get('Hora')),
        asset=produto,
        product=produto,
        raw_label=raw_label,
        category=category,
        direction=direction,
        quantity=row.get('Quantidade') if pd.notna(row.get('Quantidade')) else None,
        price=row.get('Preço unitário') if pd.notna(row.get('Preço unitário')) else None,
        total=row.get('Valor (U$)') or 0.0,
        balance=row.get('Saldo da conta (U$)') or 0.0,
        currency='USD',
        description=_scalar(row.get('Descrição')),
    )


def generic_extract_row(row):
    raw_label = _scalar(row.get('Movimentation')) or ''
    total = row.get('Total') or 0.0
    category = classify('generic', 'extract', raw_label, total=total)
    direction = 'Credito' if (total or 0.0) >= 0 else 'Debito'
    asset = _scalar(row.get('Asset')) or ''
    # Backfill raw_label from category when CSV left it blank — keeps UI sane.
    if not raw_label:
        raw_label = {
            category_mapping.BUY: 'Buy',
            category_mapping.SELL: 'Sell',
        }.get(category, '')
    return dict(
        source='generic',
        record_type='extract',
        date=_scalar(row.get('Date')),
        asset=asset,
        product=asset,
        raw_label=raw_label,
        category=category,
        direction=direction,
        quantity=row.get('Quantity') or 0.0,
        price=row.get('Price') or 0.0,
        total=total,
        currency='BRL',
    )

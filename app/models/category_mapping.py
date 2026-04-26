"""Canonical category mapping.

Maps the raw movimentation labels from each source CSV to a canonical
category enum used by the processing layer. The original label stays in
`Transaction.raw_label` for auditing / UI display.
"""
import logging

# Canonical categories
BUY = 'BUY'
SELL = 'SELL'
DIVIDEND = 'DIVIDEND'
INTEREST = 'INTEREST'      # Juros sobre Capital Próprio
TAX = 'TAX'
FEE = 'FEE'                # Corretagem
RENT_WAGE = 'RENT_WAGE'    # Empréstimo (credit)
SPLIT = 'SPLIT'            # Desdobro / Desdobramento
BONUS = 'BONUS'            # Bonificação em Ativos
REIMBURSE = 'REIMBURSE'
REDEMPTION = 'REDEMPTION'  # Resgate
AUCTION = 'AUCTION'        # Leilão de Fração
TRANSFER = 'TRANSFER'      # Câmbio / movimentações de caixa Avenue
OTHER = 'OTHER'

ALL_CATEGORIES = {
    BUY, SELL, DIVIDEND, INTEREST, TAX, FEE, RENT_WAGE, SPLIT, BONUS,
    REIMBURSE, REDEMPTION, AUCTION, TRANSFER, OTHER,
}

# (source, record_type, raw_label, direction) -> category
# direction is 'credit' | 'debit' | None (None = ignore direction)
_B3_MOV_CREDIT = {
    'Compra': BUY,
    'Desdobro': SPLIT,
    'Bonificação em Ativos': BONUS,
    'Dividendo': DIVIDEND,
    'Juros Sobre Capital Próprio': INTEREST,
    'Reembolso': REIMBURSE,
    'Rendimento': DIVIDEND,
    'Leilão de Fração': AUCTION,
    'Resgate': REDEMPTION,
    'Empréstimo': RENT_WAGE,
}

_B3_MOV_DEBIT = {
    'Venda': SELL,
    'Cobrança de Taxa Semestral': TAX,
    'Empréstimo': RENT_WAGE,  # debit side of stock lending
}

_B3_NEG = {
    'Compra': BUY,
    'Venda': SELL,
}

_AVENUE_CREDIT = {
    'Compra': BUY,         # historical: some Avenue rows use credit for buy
    'Desdobramento': SPLIT,
    'Dividendos': DIVIDEND,
    'Câmbio': TRANSFER,
    'Estorno': TRANSFER,
}

_AVENUE_DEBIT = {
    'Venda': SELL,
    'Compra': BUY,
    'Impostos': TAX,
    'Corretagem': FEE,
    'Câmbio': TRANSFER,
}

_GENERIC = {
    'Buy': BUY,
    'Sell': SELL,
    'Wages': DIVIDEND,
    'Taxes': TAX,
    # Tolerate Portuguese in generic too
    'Compra': BUY,
    'Venda': SELL,
    'Dividendo': DIVIDEND,
    'Dividendos': DIVIDEND,
    'Impostos': TAX,
}


def classify(source, record_type, raw_label, direction=None, total=None):
    """Return canonical category for a transaction row.

    Falls back to OTHER (with a warning log) if the label is unknown.
    """
    label = (raw_label or '').strip()

    if source == 'b3' and record_type == 'movimentation':
        if direction == 'Credito':
            cat = _B3_MOV_CREDIT.get(label)
        elif direction == 'Debito':
            cat = _B3_MOV_DEBIT.get(label)
        else:
            cat = _B3_MOV_CREDIT.get(label) or _B3_MOV_DEBIT.get(label)
    elif source == 'b3' and record_type == 'negotiation':
        cat = _B3_NEG.get(label)
    elif source == 'avenue':
        if direction == 'Credito':
            cat = _AVENUE_CREDIT.get(label)
        elif direction == 'Debito':
            cat = _AVENUE_DEBIT.get(label)
        else:
            cat = _AVENUE_CREDIT.get(label) or _AVENUE_DEBIT.get(label)
    elif source == 'generic':
        cat = _GENERIC.get(label)
        if cat is None and total is not None:
            try:
                cat = BUY if float(total) >= 0 else SELL
            except (TypeError, ValueError):
                cat = None
    else:
        cat = None

    if cat is None:
        logging.getLogger(__name__).warning(
            'Unknown raw_label: source=%s record_type=%s label=%r direction=%s',
            source, record_type, label, direction,
        )
        return OTHER
    return cat

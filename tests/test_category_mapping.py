"""Tests for the canonical category mapping."""
from app.models import category_mapping as cat
from app.models.category_mapping import classify


def test_b3_movimentation_credit_labels():
    assert classify('b3', 'movimentation', 'Compra', 'Credito') == cat.BUY
    assert classify('b3', 'movimentation', 'Desdobro', 'Credito') == cat.SPLIT
    assert classify('b3', 'movimentation', 'Bonificação em Ativos', 'Credito') == cat.BONUS
    assert classify('b3', 'movimentation', 'Dividendo', 'Credito') == cat.DIVIDEND
    assert classify('b3', 'movimentation', 'Juros Sobre Capital Próprio', 'Credito') == cat.INTEREST
    assert classify('b3', 'movimentation', 'Reembolso', 'Credito') == cat.REIMBURSE
    assert classify('b3', 'movimentation', 'Rendimento', 'Credito') == cat.DIVIDEND
    assert classify('b3', 'movimentation', 'Leilão de Fração', 'Credito') == cat.AUCTION
    assert classify('b3', 'movimentation', 'Resgate', 'Credito') == cat.REDEMPTION
    assert classify('b3', 'movimentation', 'Empréstimo', 'Credito') == cat.RENT_WAGE


def test_b3_movimentation_debit_labels():
    assert classify('b3', 'movimentation', 'Venda', 'Debito') == cat.SELL
    assert classify('b3', 'movimentation', 'Cobrança de Taxa Semestral', 'Debito') == cat.TAX


def test_b3_negotiation_labels():
    assert classify('b3', 'negotiation', 'Compra') == cat.BUY
    assert classify('b3', 'negotiation', 'Venda') == cat.SELL


def test_avenue_labels():
    assert classify('avenue', 'extract', 'Compra', 'Credito') == cat.BUY
    assert classify('avenue', 'extract', 'Desdobramento', 'Credito') == cat.SPLIT
    assert classify('avenue', 'extract', 'Dividendos', 'Credito') == cat.DIVIDEND
    assert classify('avenue', 'extract', 'Venda', 'Debito') == cat.SELL
    assert classify('avenue', 'extract', 'Impostos', 'Debito') == cat.TAX
    assert classify('avenue', 'extract', 'Corretagem', 'Debito') == cat.FEE


def test_generic_labels():
    assert classify('generic', 'extract', 'Buy') == cat.BUY
    assert classify('generic', 'extract', 'Sell') == cat.SELL
    assert classify('generic', 'extract', 'Wages') == cat.DIVIDEND
    assert classify('generic', 'extract', 'Taxes') == cat.TAX


def test_generic_blank_label_inferred_from_total_sign():
    assert classify('generic', 'extract', '', total=10.0) == cat.BUY
    assert classify('generic', 'extract', '', total=-5.0) == cat.SELL


def test_unknown_label_falls_back_to_other():
    assert classify('b3', 'movimentation', 'NovoLabelDesconhecido', 'Credito') == cat.OTHER
    assert classify('avenue', 'extract', 'Algo Inesperado', 'Debito') == cat.OTHER
    assert classify('mystery', 'extract', 'foo') == cat.OTHER

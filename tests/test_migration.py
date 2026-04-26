"""Tests for the one-shot legacy → Transaction migration."""
import pytest

from app import db
from app.migrate_to_transaction import migrate_legacy_to_transaction
from app.models import (
    AvenueExtract, B3Movimentation, B3Negotiation, GenericExtract, Transaction,
)


pytestmark = pytest.mark.usefixtures("request_ctx")


def test_migration_no_legacy_rows_is_noop(db_session):
    summary = migrate_legacy_to_transaction(drop_legacy=False)
    # Tables exist (created by db.create_all) but are empty → no rows added
    if summary:
        for added, _skipped in summary.values():
            assert added == 0
    assert Transaction.query.count() == 0


def test_migration_copies_b3_movimentation(db_session):
    db.session.add(B3Movimentation(
        origin_id='legacy:1', entrada_saida='Credito', data='2024-01-15',
        movimentacao='Compra', produto='PETR4 - PETROBRAS',
        instituicao='X', quantidade=100, preco_unitario=10.0,
        valor_operacao=1000.0,
    ))
    db.session.commit()

    summary = migrate_legacy_to_transaction(drop_legacy=False)

    assert summary['b3_movimentation'][0] == 1
    rows = Transaction.query.filter_by(source='b3', record_type='movimentation').all()
    assert len(rows) == 1
    t = rows[0]
    assert t.asset == 'PETR4'
    assert t.category == 'BUY'
    assert t.raw_label == 'Compra'
    assert t.direction == 'Credito'
    assert t.currency == 'BRL'
    assert t.origin_id == 'legacy:1:mov'


def test_migration_copies_all_sources(db_session):
    db.session.add(B3Movimentation(
        origin_id='m1', entrada_saida='Credito', data='2024-01-01',
        movimentacao='Compra', produto='ITUB4 - ITAU', instituicao='X',
        quantidade=10, preco_unitario=20.0, valor_operacao=200.0,
    ))
    db.session.add(B3Negotiation(
        origin_id='n1', data='2024-01-02', tipo='Venda', mercado='Vista',
        prazo='-', instituicao='X', codigo='ITUB4',
        quantidade=5, preco=21.0, valor=105.0,
    ))
    db.session.add(AvenueExtract(
        origin_id='a1', data='2024-02-01', hora='', liquidacao='2024-02-03',
        descricao='Compra de 1 NVDA a $ 100,00 cada',
        valor=-100.0, saldo=0.0, entrada_saida='Credito',
        produto='NVDA', movimentacao='Compra',
        quantidade=1, preco_unitario=100.0,
    ))
    db.session.add(GenericExtract(
        origin_id='g1', date='2024-03-01', asset='AAA',
        movimentation='Buy', quantity=2, price=3.0, total=6.0,
    ))
    db.session.commit()

    summary = migrate_legacy_to_transaction(drop_legacy=False)

    assert summary['b3_movimentation'] == (1, 0)
    assert summary['b3_negotiation'] == (1, 0)
    assert summary['avenue_extract'] == (1, 0)
    assert summary['generic_extract'] == (1, 0)
    assert Transaction.query.count() == 4

    # No origin_id collisions across sources
    oids = [t.origin_id for t in Transaction.query.all()]
    assert len(oids) == len(set(oids))


def test_migration_is_idempotent(db_session):
    db.session.add(GenericExtract(
        origin_id='g1', date='2024-03-01', asset='AAA',
        movimentation='Buy', quantity=2, price=3.0, total=6.0,
    ))
    db.session.commit()

    s1 = migrate_legacy_to_transaction(drop_legacy=False)
    s2 = migrate_legacy_to_transaction(drop_legacy=False)

    assert s1['generic_extract'] == (1, 0)
    assert s2['generic_extract'] == (0, 1)  # second pass: already migrated
    assert Transaction.query.count() == 1

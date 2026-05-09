import pytest
import pandas as pd
from app.models import (
    B3Movimentation, B3Negotiation, AvenueExtract, GenericExtract, ApiConfig,
    b3_movimentation_sql_to_df, b3_negotiation_sql_to_df,
    avenue_extract_sql_to_df, generic_extract_sql_to_df,
    get_api_key,
)


def test_empty_sql_to_df():
    assert b3_movimentation_sql_to_df([]).empty
    assert b3_negotiation_sql_to_df([]).empty
    assert avenue_extract_sql_to_df([]).empty
    # Generic must not crash on empty
    df = generic_extract_sql_to_df([])
    assert df.empty


def test_b3_movimentation_round_trip(db_session):
    from app import db
    row = B3Movimentation(
        origin_id='t1', entrada_saida='Credito', data='2024-01-15',
        movimentacao='Compra', produto='PETR4 - PETROLEO',
        instituicao='Inst', quantidade=100, preco_unitario=10.0,
        valor_operacao=1000.0,
    )
    db.session.add(row)
    db.session.commit()
    df = b3_movimentation_sql_to_df(B3Movimentation.query.all())
    assert len(df) == 1
    assert df.iloc[0]['Asset'] == 'PETR4'
    assert df.iloc[0]['Quantity'] == 100
    assert df.iloc[0]['Total'] == 1000.0


def test_b3_negotiation_round_trip(db_session):
    from app import db
    row = B3Negotiation(
        origin_id='t1', data='2024-02-10', tipo='Compra', mercado='Vista',
        prazo='-', instituicao='X', codigo='HGLG11', quantidade=10,
        preco=150.0, valor=1500.0,
    )
    db.session.add(row)
    db.session.commit()
    df = b3_negotiation_sql_to_df(B3Negotiation.query.all())
    assert df.iloc[0]['Asset'] == 'HGLG11'
    assert df.iloc[0]['Movimentation'] == 'Compra'


def test_avenue_extract_round_trip(db_session):
    from app import db
    row = AvenueExtract(
        origin_id='t1', data='2024-03-01', hora='10:00', liquidacao='2024-03-03',
        descricao='Compra de 5 NVDA a $ 200,00 cada', valor=-1000.0, saldo=0.0,
        entrada_saida='Debito', produto='NVDA', movimentacao='Compra',
        quantidade=5, preco_unitario=200.0,
    )
    db.session.add(row)
    db.session.commit()
    df = avenue_extract_sql_to_df(AvenueExtract.query.all())
    assert df.iloc[0]['Asset'] == 'NVDA'


def test_generic_extract_fills_movimentation(db_session):
    from app import db
    db.session.add(GenericExtract(
        origin_id='t1', date='2024-01-01', asset='AAA',
        movimentation='', quantity=10, price=5.0, total=50.0,
    ))
    db.session.add(GenericExtract(
        origin_id='t2', date='2024-01-02', asset='AAA',
        movimentation='', quantity=2, price=6.0, total=-12.0,
    ))
    db.session.commit()
    df = generic_extract_sql_to_df(GenericExtract.query.order_by(GenericExtract.date).all())
    assert df.iloc[0]['Movimentation'] == 'Buy'
    assert df.iloc[1]['Movimentation'] == 'Sell'


def test_api_config_get_set(db_session):
    from app import db
    assert get_api_key('gemini') is None
    db.session.add(ApiConfig(provider='gemini', api_key='sk-test'))
    db.session.commit()
    assert get_api_key('gemini') == 'sk-test'


# ---------------------------------------------------------------------------
# PortfolioTarget model
# ---------------------------------------------------------------------------

def test_portfolio_target_create(db_session):
    from app import db
    from app.models import PortfolioTarget
    db.session.add(PortfolioTarget(asset_class='Stocks', target_weight=60.0))
    db.session.add(PortfolioTarget(asset_class='FIIs', target_weight=40.0))
    db.session.commit()

    rows = PortfolioTarget.query.all()
    assert len(rows) == 2
    stocks = PortfolioTarget.query.filter_by(asset_class='Stocks').first()
    assert stocks.target_weight == 60.0
    assert stocks.enabled is True


def test_portfolio_target_unique_asset_class(db_session):
    """Inserting two rows with the same asset_class must raise an IntegrityError."""
    from app import db
    from app.models import PortfolioTarget
    from sqlalchemy.exc import IntegrityError
    db.session.add(PortfolioTarget(asset_class='Stocks', target_weight=50.0))
    db.session.commit()
    db.session.add(PortfolioTarget(asset_class='Stocks', target_weight=70.0))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_save_targets_upsert(db_session):
    """save_targets should insert new and update existing rows."""
    from app.processing.rebalance import save_targets
    from app.models import PortfolioTarget
    save_targets({'Stocks': 70.0, 'FIIs': 30.0})
    assert PortfolioTarget.query.filter_by(asset_class='Stocks').first().target_weight == 70.0

    save_targets({'Stocks': 60.0, 'FIIs': 40.0})
    assert PortfolioTarget.query.filter_by(asset_class='Stocks').first().target_weight == 60.0
    assert PortfolioTarget.query.count() == 2


def test_load_targets_only_enabled(db_session):
    """load_targets must return only enabled=True rows."""
    from app import db
    from app.models import PortfolioTarget
    from app.processing.rebalance import load_targets
    db.session.add(PortfolioTarget(asset_class='Bonds', target_weight=20.0, enabled=True))
    db.session.add(PortfolioTarget(asset_class='Crypto', target_weight=5.0, enabled=False))
    db.session.commit()
    targets = load_targets()
    assert 'Bonds' in targets
    assert 'Crypto' not in targets

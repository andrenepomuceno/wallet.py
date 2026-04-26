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

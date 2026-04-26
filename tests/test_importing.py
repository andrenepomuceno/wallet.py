import os
import tempfile
import pandas as pd
import pytest

from app.importing import (
    gen_hash,
    extract_fill,
    import_b3_movimentation,
    import_b3_negotiation,
    import_avenue_extract,
    import_generic_extract,
)
from app.models import Transaction


pytestmark = pytest.mark.usefixtures("request_ctx")


@pytest.fixture
def tmp_csv():
    fd, path = tempfile.mkstemp(suffix='.csv')
    os.close(fd)
    yield path
    try:
        os.remove(path)
    except OSError:
        pass


def test_gen_hash_stable(tmp_csv):
    with open(tmp_csv, 'w') as f:
        f.write('hello world')
    h1 = gen_hash(tmp_csv)
    h2 = gen_hash(tmp_csv)
    assert h1 == h2
    assert len(h1) == 64


def test_extract_fill_handles_nan_and_formats():
    df = pd.DataFrame({
        'Descrição': [
            'Compra de 5 NVDA a $\xa0209,00 cada',
            'Venda de 0,77 ASML a $ 600,00 cada',
            'Dividendos de MSFT',
            'Imposto sobre dividendo de MSFT',
            'Cobrança de taxa de corretagem',
            None,  # NaN-ish entry must not crash
            float('nan'),
        ]
    })
    out = extract_fill(df)
    assert out.loc[0, 'Movimentação'] == 'Compra'
    assert out.loc[0, 'Produto'] == 'NVDA'
    assert out.loc[0, 'Quantidade'] == 5.0
    assert out.loc[0, 'Preço unitário'] == 209.0

    assert out.loc[1, 'Movimentação'] == 'Venda'
    assert out.loc[1, 'Produto'] == 'ASML'
    assert out.loc[1, 'Quantidade'] == 0.77

    assert out.loc[2, 'Movimentação'] == 'Dividendos'
    assert out.loc[2, 'Produto'] == 'MSFT'
    assert out.loc[2, 'Entrada/Saída'] == 'Credito'

    assert out.loc[3, 'Movimentação'] == 'Impostos'
    assert out.loc[3, 'Produto'] == 'MSFT'
    assert out.loc[3, 'Entrada/Saída'] == 'Debito'

    assert out.loc[4, 'Movimentação'] == 'Corretagem'

    # NaN rows should produce empty/None safely
    assert out.loc[5, 'Movimentação'] == '???'
    assert out.loc[6, 'Movimentação'] == '???'


def _write_csv(path, df):
    df.to_csv(path, index=False)


def test_import_b3_movimentation(db_session, tmp_csv):
    df = pd.DataFrame([{
        'Entrada/Saída': 'Credito', 'Data': '15/01/2024',
        'Movimentação': 'Compra', 'Produto': 'PETR4 - PETROBRAS',
        'Instituição': 'X', 'Quantidade': 100,
        'Preço unitário': 10.0, 'Valor da Operação': 1000.0,
    }])
    _write_csv(tmp_csv, df)
    df_loaded = pd.read_csv(tmp_csv)
    import_b3_movimentation(df_loaded, tmp_csv)
    rows = Transaction.query.filter_by(source='b3', record_type='movimentation').all()
    assert len(rows) == 1
    assert rows[0].asset == 'PETR4'
    assert rows[0].category == 'BUY'
    # Re-import same file: dedup
    df_loaded2 = pd.read_csv(tmp_csv)
    import_b3_movimentation(df_loaded2, tmp_csv)
    assert Transaction.query.filter_by(source='b3', record_type='movimentation').count() == 1


def test_import_b3_negotiation(db_session, tmp_csv):
    df = pd.DataFrame([{
        'Data do Negócio': '20/02/2024', 'Tipo de Movimentação': 'Compra',
        'Mercado': 'Vista', 'Prazo/Vencimento': '-', 'Instituição': 'X',
        'Código de Negociação': 'HGLG11', 'Quantidade': 10,
        'Preço': 150.0, 'Valor': 1500.0,
    }])
    _write_csv(tmp_csv, df)
    import_b3_negotiation(pd.read_csv(tmp_csv), tmp_csv)
    rows = Transaction.query.filter_by(source='b3', record_type='negotiation').all()
    assert len(rows) == 1
    assert rows[0].asset == 'HGLG11'
    assert rows[0].category == 'BUY'


def test_import_avenue_extract_old_format(db_session, tmp_csv):
    df = pd.DataFrame([{
        'Data': '01/03/2024', 'Hora': '10:00:00', 'Liquidação': '03/03/2024',
        'Descrição': 'Compra de 5 NVDA a $ 200.00 cada',
        'Valor (U$)': -1000.0, 'Saldo da conta (U$)': 0.0,
    }])
    _write_csv(tmp_csv, df)
    import_avenue_extract(pd.read_csv(tmp_csv), tmp_csv)
    rows = Transaction.query.filter_by(source='avenue').all()
    assert len(rows) == 1
    assert rows[0].asset == 'NVDA'
    assert rows[0].raw_label == 'Compra'
    assert rows[0].category == 'BUY'


def test_import_avenue_extract_new_format(db_session, tmp_csv):
    df = pd.DataFrame([{
        'Data transação': '02/03/2024', 'Data liquidação': '04/03/2024',
        'Descrição': 'Compra de 3 AAPL a $ 150,00 cada',
        'Valor': -450.0, 'Saldo': 100.0,
    }])
    _write_csv(tmp_csv, df)
    import_avenue_extract(pd.read_csv(tmp_csv), tmp_csv)
    rows = Transaction.query.filter_by(source='avenue').all()
    assert len(rows) == 1
    assert rows[0].asset == 'AAPL'


def test_import_generic_extract(db_session, tmp_csv):
    df = pd.DataFrame([{
        'Date': '2024-01-01', 'Asset': 'AAA', 'Movimentation': 'Buy',
        'Quantity': 10, 'Price': 5.0, 'Total': 50.0,
    }])
    _write_csv(tmp_csv, df)
    import_generic_extract(pd.read_csv(tmp_csv), tmp_csv)
    rows = Transaction.query.filter_by(source='generic').all()
    assert len(rows) == 1
    assert rows[0].asset == 'AAA'
    assert rows[0].category == 'BUY'

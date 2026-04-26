import pandas as pd
import pytest
from app.utils.parsing import (
    is_valid_b3_ticker,
    is_b3_stock_ticker,
    is_b3_fii_ticker,
    parse_b3_product,
    parse_b3_ticker,
    brl_to_float,
)


@pytest.mark.parametrize("ticker,expected", [
    ("PETR4", True),
    ("VALE3", True),
    ("ITUB4", True),
    ("BBAS3", True),
    ("MGLU3", True),
    ("HGLG11", False),  # FII, not stock
    ("BTC", False),
    ("AAPL", False),
    ("PETR", False),
    ("petr4", False),
])
def test_is_b3_stock_ticker(ticker, expected):
    assert is_b3_stock_ticker(ticker) is expected


@pytest.mark.parametrize("ticker,expected", [
    ("HGLG11", True),
    ("MXRF11", True),
    ("KNRI11", True),
    ("PETR4", False),
    ("BTC", False),
])
def test_is_b3_fii_ticker(ticker, expected):
    assert is_b3_fii_ticker(ticker) is expected


def test_is_valid_b3_ticker():
    assert is_valid_b3_ticker("PETR4")
    assert is_valid_b3_ticker("HGLG11")
    assert not is_valid_b3_ticker("AAPL")


def test_parse_b3_product_and_ticker():
    s = pd.Series([
        "PETR4 - PETROLEO BRASILEIRO",
        "HGLG11 - CSHG LOGISTICA",
        "Tesouro Selic 2029",
    ])
    products = parse_b3_product(s).tolist()
    tickers = parse_b3_ticker(s).tolist()
    assert products[0] == "PETR"
    assert tickers[0] == "PETR4"
    assert tickers[1] == "HGLG11"
    # Free-form names pass through
    assert "Tesouro" in tickers[2]


@pytest.mark.parametrize("raw,expected", [
    ("R$ 10,50", 10.50),
    ("R$ 1.234,56", 1234.56),
    ("R$ 100", 100.0),
    ("10.5", 10.5),
    ("invalid", None),
    (None, None),
    (12.34, 12.34),
])
def test_brl_to_float(raw, expected):
    assert brl_to_float(raw) == expected

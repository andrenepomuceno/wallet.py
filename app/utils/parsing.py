import re

def is_valid_b3_ticker(ticker):
    return is_b3_stock_ticker(ticker) or is_b3_fii_ticker(ticker)

def is_b3_stock_ticker(ticker):
    pattern = r'[A-Z0-9]{4}(3|4)$'
    if re.match(pattern, ticker):
        return True
    return False

def is_b3_fii_ticker(ticker):
    pattern = r'[A-Z0-9]{4}11$'
    if re.match(pattern, ticker):
        return True
    return False

def parse_b3_product(column):
    result = column.str.extract(r'^([A-Z0-9]{4}|[a-zA-Z0-9 .]+)', expand=False)
    result.fillna('', inplace=True)
    return result

def parse_b3_ticker(column):
    result = column.str.extract(r'^([A-Z0-9]{4}[0-9]{1,2}|[a-zA-Z0-9 .]+)', expand=False)
    result.fillna('', inplace=True)
    return result

def brl_to_float(preco_str):
    preco_str = preco_str.replace("R$", "").strip()
    preco_str = preco_str.replace(".", "").replace(",", ".")
    try:
        return float(preco_str)
    except ValueError:
        return None

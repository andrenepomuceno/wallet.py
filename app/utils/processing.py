import pandas as pd
import yfinance_cache as yf
import requests
from lxml import html
import re

from app import app, db
from app.models import B3_Movimentation, B3_Negotiation, Avenue_Extract

scrap_dict = {
    # "Tesouro Selic 2024": {
    #     'url': 'https://taxas-tesouro.com/resgatar/tesouro-selic-2024/',
    #     'xpath': '//*[@id="gatsby-focus-wrapper"]/div/div[2]/main/div[1]/div/div[1]/div[4]/div[2]/span'
    # },
    # "Tesouro Selic 2025": {
    #     'url': 'https://taxas-tesouro.com/resgatar/tesouro-selic-2025/',
    #     'xpath': '//*[@id="gatsby-focus-wrapper"]/div/div[2]/main/div[1]/div/div[1]/div[4]/div[2]/span'
    # },
    # "Tesouro Selic 2027": {
    #     'url': 'https://taxas-tesouro.com/resgatar/tesouro-selic-2027/',
    #     'xpath': '//*[@id="gatsby-focus-wrapper"]/div/div[2]/main/div[1]/div/div[1]/div[4]/div[2]/span'
    # },
    "Tesouro Selic 2029": {
        'url': 'https://taxas-tesouro.com/resgatar/tesouro-selic-2029/',
        'xpath': '//*[@id="gatsby-focus-wrapper"]/div/div[2]/main/div[1]/div/div[1]/div[4]/div[2]/span'
    }
}

def is_valid_ticker(ticker):
    pattern = r'[A-Z0-9]{4}(3|4|11)$'
    if re.match(pattern, ticker):
        return True
    else:
        return False

def scrape_data(url, xpath):
    try:
        response = requests.get(url)
        response.raise_for_status()
        tree = html.fromstring(response.content)
        elements = tree.xpath(xpath)
        return [element.text_content().strip() for element in elements]
    except requests.RequestException as e:
        return [f"Erro ao acessar a URL: {e}"]
    except Exception as e:
        return [f"Erro ao realizar o scraping: {e}"]

def b3_movimentation_sql_to_df(result):
    df = pd.DataFrame([(d.entrada_saida, d.data, d.movimentacao, d.produto, 
                        d.instituicao, d.quantidade, d.preco_unitario, d.valor_operacao) for d in result], 
                      columns=['Entrada/Saída', 'Data', 'Movimentação', 'Produto',
                               'Instituição', 'Quantidade', 'Preço unitário', 'Valor da Operação'])
    df['Data'] = pd.to_datetime(df['Data'])
    return df

def b3_negotiation_sql_to_df(result):
    df = pd.DataFrame([(d.data, d.tipo, d.mercado, d.prazo, 
                        d.instituicao, d.codigo, d.quantidade, d.preco,
                        d.valor) for d in result], 
                      columns=['Data do Negócio', 'Tipo de Movimentação', 'Mercado', 'Prazo/Vencimento',
                               'Instituição', 'Código de Negociação', 'Quantidade', 'Preço',
                               'Valor'])
    df['Data do Negócio'] = pd.to_datetime(df['Data do Negócio'])
    return df

def avenue_extract_sql_to_df(result):
    df = pd.DataFrame([(d.data, d.hora, d.liquidacao, d.descricao, 
                        d.valor, d.saldo,
                        d.entrada_saida, d.produto, d.movimentacao, d.quantidade, d.preco_unitario) for d in result], 
                      columns=['Data', 'Hora', 'Liquidação', 'Descrição',
                               'Valor (U$)', 'Saldo da conta (U$)',
                               'Entrada/Saída', 'Produto', 'Movimentação', 'Quantidade', 'Preço unitário'])
    df['Data'] = pd.to_datetime(df['Data'])
    df['Liquidação'] = pd.to_datetime(df['Liquidação'])
    return df

def view_movimentation_request(request):
    app.logger.info('view_movimentation_request')

    df = pd.DataFrame()
    query = B3_Movimentation.query.order_by(B3_Movimentation.data.asc())

    if request.method == 'POST':
        filters = request.form.to_dict()
        for key, value in filters.items():
            if value:
                column = getattr(B3_Movimentation, key, None)
                if column is not None:
                    if isinstance(column.type, db.Float):
                        # Filtragem para campos numéricos
                        query = query.filter(column == float(value))
                    else:
                        # Filtragem para campos textuais e de data
                        query = query.filter(column.like(f'%{value}%'))

    result = query.all()
    df = b3_movimentation_sql_to_df(result)
    if len(df) == 0:
        return df
    
    df['Produto_Parsed'] = parse_produto(df['Produto'])
    print(df['Produto_Parsed'].value_counts())
    #print(df['Produto'].value_counts())

    df['Ticker'] = parse_ticker(df['Produto'])

    grouped = df[['Entrada/Saída', 'Movimentação']].groupby(['Entrada/Saída'])
    print(grouped.value_counts())

    # print(df['Movimentação'].value_counts())

    return df

def view_negotiation_request(request):
    app.logger.info('view_negotiation_request')

    query = B3_Negotiation.query.order_by(B3_Negotiation.data.asc())
    result = query.all()
    df = b3_negotiation_sql_to_df(result)
    return df

def parse_produto(column):
    result = column.str.extract(r'^([A-Z0-9]{4}|[a-zA-Z0-9 .]+)', expand=False)
    result.fillna('', inplace=True)
    return result

def parse_ticker(column):
    result = column.str.extract(r'^([A-Z0-9]{4}[0-9]{1,2}|[a-zA-Z0-9 .]+)', expand=False)
    result.fillna('', inplace=True)
    return result

def price_to_float(preco_str):
    preco_str = preco_str.replace("R$", "").strip()
    preco_str = preco_str.replace(".", "").replace(",", ".")
    try:
        return float(preco_str)
    except ValueError:
        return None
    
def consolidate_buysell(movimentation, negotiation, tipo):
    columns = ["Data", "Movimentação", "Quantidade", "Preço unitário", "Valor da Operação", "Produto"]
    df1 = movimentation[columns]

    df2 = negotiation.copy()
    df2.rename(columns={"Data do Negócio": "Data", "Preço": "Preço unitário", "Valor": "Valor da Operação", "Código de Negociação": "Produto"}, inplace=True)
    df2["Movimentação"] = tipo
    df2 = df2[columns]

    df_merged = pd.concat([df1, df2], ignore_index=True)
    df_merged.sort_values(by='Data', inplace=True)

    return df_merged

def view_asset_request(request, asset):
    app.logger.info(f'Processing view asset request for "{asset}".')

    asset_info = {}
    dataframes = {}

    asset_info['name'] = asset
    asset_info['currency'] = 'BRL'

    first_buy = None
    age = None

    query = B3_Movimentation.query.filter(B3_Movimentation.produto.like(f'%{asset}%')).order_by(B3_Movimentation.data.asc())
    result = query.all()
    movimentation = b3_movimentation_sql_to_df(result)
    if len(movimentation) == 0:
        app.logger.warning(f'Movimentation data not found for {asset}')
        return asset_info
    
    dataframes['movimentation'] = movimentation

    movimentation['Ticker'] = parse_ticker(movimentation['Produto'])
    ticker = movimentation['Ticker'].value_counts().index[0]
    asset_info['ticker'] = ticker

    credit = movimentation.loc[movimentation['Entrada/Saída'] == "Credito"]
    debit = movimentation.loc[movimentation['Entrada/Saída'] == "Debito"]

    buys = credit.loc[
        (
            (credit['Movimentação'] == "Compra")
            | (credit['Movimentação'] == "Desdobro") 
            | (credit['Movimentação'] == "Bonificação em Ativos")
            | (credit['Movimentação'] == "Atualização")
        )
    ]
    dataframes['buys'] = buys
    if len(buys) > 0:
        first_buy = buys.iloc[0]['Data']
        age = pd.to_datetime("today") - first_buy

    sells = debit.loc[
        (
            (debit['Movimentação'] == "Venda")
        )
    ]
    dataframes['sells'] = sells

    taxes = debit.loc[
        ((debit['Movimentação'] == "Cobrança de Taxa Semestral"))
    ]
    taxes_sum = taxes['Valor da Operação'].sum()
    asset_info['taxes_sum'] = round(taxes_sum, 2)

    wages = credit.loc[
        ((credit['Movimentação'] == "Dividendo") 
         | (credit['Movimentação'] == "Juros Sobre Capital Próprio") 
         | (credit['Movimentação'] == "Reembolso") 
         | (credit['Movimentação'] == "Rendimento")
         | (credit['Movimentação'] == "Leilão de Fração"))
    ]
    wages_sum = wages['Valor da Operação'].sum()

    dataframes['wages'] = wages
    asset_info['wages_sum'] = round(wages_sum, 2)

    rents_wage = credit.loc[(
        (credit['Movimentação'] == "Empréstimo")
        & (credit['Valor da Operação'] > 0)
    )]
    rents_wages_sum = rents_wage['Valor da Operação'].sum()
    asset_info['rents_wage_sum'] = round(rents_wages_sum, 2)

    query = B3_Negotiation.query.filter(B3_Negotiation.codigo.like(f'%{ticker}%')).order_by(B3_Negotiation.data.asc())
    result = query.all()
    negotiation = b3_negotiation_sql_to_df(result)
    last_close_price = None
    if len(negotiation) > 0:
        dataframes['negotiation'] = negotiation

        negotiation_buys = negotiation.loc[
            (
                (negotiation['Tipo de Movimentação'] == "Compra")
            )
        ]
        dataframes['negotitation_buys'] = negotiation_buys

        if len(negotiation_buys) > 0:
            first_buy = negotiation_buys.iloc[0]['Data do Negócio']
            age = pd.to_datetime("today") - first_buy

        negotiation_sells = negotiation.loc[
            (
                (negotiation['Tipo de Movimentação'] == "Venda")
            )
        ]
        dataframes['negotitation_sells'] = negotiation_sells

        buys = consolidate_buysell(buys, negotiation_buys, 'Compra')
        dataframes['buys'] = buys
        sells = consolidate_buysell(sells, negotiation_sells, 'Venda')
        dataframes['sells'] = sells

    else:
        app.logger.warning(f'Warning! Negotiation data not found for {asset}!')
        dataframes['negotiation'] = pd.DataFrame(columns=['Data do Negócio', 'Tipo de Movimentação', 'Mercado', 'Prazo/Vencimento',
                                                          'Instituição', 'Código de Negociação', 'Quantidade', 'Preço','Valor'])
        # return asset_info

    buys_quantity_sum = buys['Quantidade'].sum()
    asset_info['buys_quantity_sum'] = buys_quantity_sum

    sells_sum = sells['Quantidade'].sum()
    asset_info['sells_sum'] = round(sells_sum, 2)

    position = buys_quantity_sum - sells_sum
    asset_info['position'] = position

    if first_buy is not None:
        asset_info['first_buy'] = first_buy.strftime("%Y-%m-%d")

    if age is not None:
        asset_info['age'] = age.days

    buys_value_sum = buys['Valor da Operação'].sum()
    asset_info['buys_value_sum'] = round(buys_value_sum, 2)

    sells_value_sum = sells['Valor da Operação'].sum()
    asset_info['sells_value_sum'] = sells_value_sum

    total_cost = buys_value_sum - sells_value_sum
    asset_info['total_cost'] = round(total_cost, 2)

    liquid_cost = total_cost - wages_sum - rents_wages_sum + taxes_sum
    asset_info['liquid_cost'] = round(liquid_cost, 2)

    buys_wsum = (buys['Quantidade'] * buys['Preço unitário']).sum()
    buys_quantity = buys['Quantidade'].sum()
    buy_avg_price = buys_wsum / buys_quantity if buys_quantity > 0 else 0
    asset_info['buy_avg_price'] = round(buy_avg_price, 2)

    buys_wsum2 = buys['Valor da Operação'].sum()
    buy_avg_price2 = buys_wsum2 / buys_quantity if buys_quantity > 0 else 0
    asset_info['buy_avg_price2'] = round(buy_avg_price2, 2)
    if asset_info['buy_avg_price'] != asset_info['buy_avg_price2']:
        app.logger.warning("Warning! buys_wsum inconsistency!")

    asset_info['rented'] = 0
    rented = asset_info['rented']

    position_sum = round(position + rented, 2)
    asset_info['position_sum'] = position_sum

    if position > 0:
        if is_valid_ticker(ticker) and (ticker != 'VVAR3'):
            # maybe check if position > 0
            try:
                stock = yf.Ticker(ticker + ".SA")
                hist = stock.history(period="1d")
                if not hist.empty:
                    last_close_price = hist['Close'].iloc[-1]
                    asset_info['last_close_price'] = round(last_close_price, 2)

                currency = stock.info['currency']
                asset_info['currency'] = currency
            except:
                pass
        elif ticker in scrap_dict:
            app.logger.info(f'Scraping data for {ticker}')
            scrap_info = scrap_dict[ticker]
            if 'cache' in scrap_info:
                last_close_price = scrap_info['cache']
            else:
                scraped = scrape_data(scrap_info['url'], scrap_info['xpath'])
                last_close_price = price_to_float(scraped[0])
                scrap_info['cache'] = last_close_price
            asset_info['last_close_price'] = round(last_close_price, 2)

    if last_close_price != None and position_sum > 0:
        position_total = position_sum * last_close_price
        asset_info['position_total'] = round(position_total, 2)

        rentabiliy = position_total/liquid_cost
        rentabiliy = round((rentabiliy - 1) * 100, 2)
        asset_info['rentability'] = rentabiliy

        if age is not None:
            by_year = round(rentabiliy/(age.days/365), 2)
            asset_info['rentability_by_year'] = by_year
    
    else:
        asset_info['position_total'] = 0
        asset_info['rentability'] = -100
        asset_info['rentability_by_year'] = -100

    app.logger.debug(asset_info)

    asset_info['dataframes'] = dataframes
    return asset_info

def view_consolidate_request(request):
    app.logger.info(f'view_consolidate_request')

    ret = {}
    
    query = B3_Movimentation.query
    result = query.all()
    movimentation = b3_movimentation_sql_to_df(result)
    if len(movimentation) == 0:
        return ret
    
    movimentation['Produto_Parsed'] = parse_produto(movimentation['Produto'])
    movimentation['Ticker'] = parse_ticker(movimentation['Produto'])

    b3_consolidate = pd.DataFrame()
    products = movimentation['Ticker'].value_counts().to_frame()
    for index, product in products.iterrows():
        asset_info = view_asset_request(request, product.name)
        new_row = pd.DataFrame([asset_info])
        b3_consolidate = pd.concat([b3_consolidate, new_row], ignore_index=True)

    b3_consolidate['url'] = b3_consolidate['name'].apply(lambda x: f"<a href='/view/{x}'>{x}</a>")

    query = Avenue_Extract.query
    result = query.all()
    movimentation = avenue_extract_sql_to_df(result)
    if len(movimentation) == 0:
        return ret

    avenue_consolidate = pd.DataFrame()
    products = movimentation['Produto'].value_counts().to_frame()
    print(products)
    for index, product in products.iterrows():
        if product.name == '':
            continue

        asset_info = view_extract_asset_request(request, product.name)
        new_row = pd.DataFrame([asset_info])
        avenue_consolidate = pd.concat([avenue_consolidate, new_row], ignore_index=True)

    avenue_consolidate['url'] = avenue_consolidate['name'].apply(lambda x: f"<a href='/extract/{x}'>{x}</a>")

    # print(pd.DataFrame(asset_list))
    # print(movimentation['Ticker'].value_counts())

    consolidate = pd.concat([b3_consolidate, avenue_consolidate])
    consolidate = consolidate[['name','url','ticker','currency','last_close_price',
                               'position_sum','position_total','buy_avg_price',
                               'total_cost','wages_sum','rents_wage_sum','liquid_cost',
                               'rentability','rentability_by_year','age','taxes_sum']]

        
    df = consolidate.loc[consolidate['position_sum'] > 0]
    df = df.sort_values(by='rentability', ascending=False)
    df['age'] = round(df['age']/365, 2)
    ret['consolidate'] = df

    old = consolidate.loc[consolidate['position_sum'] <= 0]
    old = old.sort_values(by='liquid_cost', ascending=True)
    ret['old'] = old
    
    consolidate_brl = consolidate.loc[consolidate['currency'] == 'BRL']
    ret['total_cost_sum'] = round(consolidate_brl['total_cost'].sum(), 2)
    ret['total_wages_sum'] = round(consolidate_brl['wages_sum'].sum(), 2)
    ret['total_rents_wage_sum'] = round(consolidate_brl['rents_wage_sum'].sum(), 2)
    ret['position_total_sum'] = round(consolidate_brl['position_total'].sum(), 2)
    ret['taxes_sum'] = round(consolidate_brl['taxes_sum'].sum(), 2)

    consolidate_usd = consolidate.loc[consolidate['currency'] == 'USD']
    ret['total_cost_sum_usd'] = round(consolidate_usd['total_cost'].sum(), 2)
    ret['total_wages_sum_usd'] = round(consolidate_usd['wages_sum'].sum(), 2)
    ret['total_rents_wage_sum_usd'] = round(consolidate_usd['rents_wage_sum'].sum(), 2)
    ret['position_total_sum_usd'] = round(consolidate_usd['position_total'].sum(), 2)
    ret['taxes_sum_usd'] = round(consolidate_usd['taxes_sum'].sum(), 2)

    return ret

def view_extract_request(request):
    app.logger.info(f'view_extract_request')

    query = Avenue_Extract.query.order_by(Avenue_Extract.data.asc())
    result = query.all()
    extract = avenue_extract_sql_to_df(result)

    return extract

def view_extract_asset_request(request, asset):
    app.logger.info(f'Processing view_extract_asset_request for "{asset}".')

    asset_info = {}
    dataframes = {}

    asset_info['name'] = asset
    asset_info['currency'] = 'USD'

    first_buy = None
    age = None
    last_close_price = None

    query = Avenue_Extract.query.filter(Avenue_Extract.produto.like(f'%{asset}%')).order_by(Avenue_Extract.data.asc())
    result = query.all()
    extract = avenue_extract_sql_to_df(result)
    if len(extract) == 0:
        app.logger.warning(f'Extract data not found for {asset}')
        return asset_info
    
    extract['Valor da Operação'] = abs(extract['Valor (U$)'])
    
    dataframes['movimentation'] = extract

    ticker = extract['Produto'].value_counts().index[0]
    asset_info['ticker'] = ticker

    credit = extract.loc[extract['Entrada/Saída'] == "Credito"]
    debit = extract.loc[extract['Entrada/Saída'] == "Debito"]

    buys = credit.loc[
        (
            (credit['Movimentação'] == "Compra")
            | (credit['Movimentação'] == "Desdobramento")
        )
    ]
    dataframes['buys'] = buys
    if len(buys) > 0:
        first_buy = buys.iloc[0]['Data']
        age = pd.to_datetime("today") - first_buy

    sells = debit.loc[
        (
            (debit['Movimentação'] == "Venda")
        )
    ]
    dataframes['sells'] = sells

    taxes = debit.loc[
        (debit['Movimentação'] == "Impostos")
        | (debit['Movimentação'] == "Corretagem")
    ]
    taxes_sum = taxes['Valor da Operação'].sum()
    asset_info['taxes_sum'] = round(taxes_sum, 2)

    wages = credit.loc[
        (credit['Movimentação'] == "Dividendos")
    ]
    wages_sum = wages['Valor da Operação'].sum()

    dataframes['wages'] = wages
    asset_info['wages_sum'] = round(wages_sum, 2)

    rents_wages_sum = 0
    asset_info['rents_wage_sum'] = round(rents_wages_sum, 2)

    buys_quantity_sum = buys['Quantidade'].sum()
    asset_info['buys_quantity_sum'] = buys_quantity_sum

    sells_sum = sells['Quantidade'].sum()
    asset_info['sells_sum'] = round(sells_sum, 2)

    position = buys_quantity_sum - sells_sum
    asset_info['position'] = position

    if first_buy is not None:
        asset_info['first_buy'] = first_buy.strftime("%Y-%m-%d")

    if age is not None:
        asset_info['age'] = age.days

    buys_value_sum = buys['Valor da Operação'].sum()
    asset_info['buys_value_sum'] = round(buys_value_sum, 2)

    sells_value_sum = sells['Valor da Operação'].sum()
    asset_info['sells_value_sum'] = sells_value_sum

    total_cost = buys_value_sum - sells_value_sum
    asset_info['total_cost'] = round(total_cost, 2)

    liquid_cost = total_cost - wages_sum - rents_wages_sum + taxes_sum
    asset_info['liquid_cost'] = round(liquid_cost, 2)

    buys_wsum = (buys['Quantidade'] * buys['Preço unitário']).sum()
    buys_quantity = buys['Quantidade'].sum()
    buy_avg_price = buys_wsum / buys_quantity if buys_quantity > 0 else 0
    asset_info['buy_avg_price'] = round(buy_avg_price, 2)

    buys_wsum2 = buys['Valor da Operação'].sum()
    buy_avg_price2 = buys_wsum2 / buys_quantity if buys_quantity > 0 else 0
    asset_info['buy_avg_price2'] = round(buy_avg_price2, 2)
    if asset_info['buy_avg_price'] != asset_info['buy_avg_price2']:
        app.logger.warning("Warning! buys_wsum inconsistency!")

    asset_info['rented'] = 0
    rented = asset_info['rented']

    position_sum = round(position + rented, 2)
    asset_info['position_sum'] = position_sum

    if position > 0:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            if not hist.empty:
                last_close_price = hist['Close'].iloc[-1]
                asset_info['last_close_price'] = round(last_close_price, 2)

            currency = stock.info['currency']
            asset_info['currency'] = currency
        except:
            pass

    if last_close_price != None and position_sum > 0:
        position_total = position_sum * last_close_price
        asset_info['position_total'] = round(position_total, 2)

        rentabiliy = position_total/liquid_cost
        rentabiliy = round((rentabiliy - 1) * 100, 2)
        asset_info['rentability'] = rentabiliy

        if age is not None:
            by_year = round(rentabiliy/(age.days/365), 2)
            asset_info['rentability_by_year'] = by_year
    
    else:
        asset_info['position_total'] = 0
        asset_info['rentability'] = -100
        asset_info['rentability_by_year'] = -100

    app.logger.debug(asset_info)

    asset_info['dataframes'] = dataframes
    return asset_info
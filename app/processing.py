import pandas as pd
# import yfinance_cache as yf
import yfinance as yf
import requests
import requests_cache
from lxml import html
import re

from app import app, db
from app.models import B3_Movimentation, B3_Negotiation, Avenue_Extract, Generic_Extract, b3_movimentation_sql_to_df, b3_negotiation_sql_to_df, avenue_extract_sql_to_df, generic_extract_sql_to_df
from app.utils.parsing import is_valid_b3_ticker, parse_b3_product, parse_b3_ticker, brl_to_float

scrape_dict = {
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
        'xpath': '//*[@id="gatsby-focus-wrapper"]/div/div[2]/main/div[1]/div/div[1]/div[4]/div[2]/span',
    }
}

request_cache = requests_cache.CachedSession('request_cache', expire_after=6*60*60)

def scrape_data(url, xpath):
    try:
        response = request_cache.get(url)
        response.raise_for_status()
        tree = html.fromstring(response.content)
        elements = tree.xpath(xpath)
        return [element.text_content().strip() for element in elements]
    except requests.RequestException as e:
        return [f"Erro ao acessar a URL: {e}"]
    except Exception as e:
        return [f"Erro ao realizar o scraping: {e}"]

def usd_exchange_rate(currency = 'BRL'):
    app.logger.info('usd_exchange_rate')
    url = 'https://api.exchangerate-api.com/v4/latest/USD'
    try:
        response = request_cache.get(url)
        data = response.json()
        rate = data['rates'][currency]
        return rate
    except Exception as e:
        return f"Error getting exchange rate quotation: {e}"

def process_b3_movimentation_request(request):
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
    
    df['Produto_Parsed'] = parse_b3_product(df['Produto'])
    print(df['Produto_Parsed'].value_counts())
    #print(df['Produto'].value_counts())

    df['Ticker'] = parse_b3_ticker(df['Produto'])

    grouped = df[['Entrada/Saída', 'Movimentação']].groupby(['Entrada/Saída'])
    print(grouped.value_counts())

    # print(df['Movimentação'].value_counts())

    return df

def process_b3_negotiation_request(request):
    app.logger.info('view_negotiation_request')

    query = B3_Negotiation.query.order_by(B3_Negotiation.data.asc())
    result = query.all()
    df = b3_negotiation_sql_to_df(result)
    return df
    
def merge_movimentation_negotiation(movimentationDf, negotiationDf, movimentationType):
    columns = ["Data", "Movimentação", "Quantidade", "Preço unitário", "Valor da Operação", "Produto"]
    df1 = movimentationDf[columns]

    df2 = negotiationDf.copy()
    df2.rename(columns={"Data do Negócio": "Data", "Preço": "Preço unitário", "Valor": "Valor da Operação", "Código de Negociação": "Produto"}, inplace=True)
    df2["Movimentação"] = movimentationType
    df2 = df2[columns]

    df_merged = pd.concat([df1, df2], ignore_index=True)
    df_merged.sort_values(by='Data', inplace=True)

    return df_merged

def process_b3_dataframes(asset, ticker, buys, sells, taxes, wages, rents_wage, asset_info):
    asset_info['name'] = asset
    currency = 'BRL'
    first_buy = None
    age = None
    last_close_price = 0

    asset_info['ticker'] = ticker

    if len(buys) > 0:
        first_buy = buys.iloc[0]['Data']
        age = pd.to_datetime("today") - first_buy

    taxes_sum = taxes['Valor da Operação'].sum()
    asset_info['taxes_sum'] = round(taxes_sum, 2)

    wages_sum = wages['Valor da Operação'].sum()
    asset_info['wages_sum'] = round(wages_sum, 2)

    rents_wages_sum = rents_wage['Valor da Operação'].sum()
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

    long_name = ''
    asset_class = ''
    if position > 0:
        if is_valid_b3_ticker(ticker) and (ticker != 'VVAR3'):
            try:
                # stock = yf.Ticker(ticker + ".SA")
                stock = yf.Ticker(ticker + ".SA", session=request_cache)
                long_name = stock.info['longName']
                last_close_price = stock.info['previousClose']
                currency = stock.info['currency']
                asset_class = 'Ação'
            except:
                pass

        elif ticker in scrape_dict:
            app.logger.info(f'Scraping data for {ticker}')
            scrap_info = scrape_dict[ticker]
            scraped = scrape_data(scrap_info['url'], scrap_info['xpath'])
            last_close_price = brl_to_float(scraped[0])
            asset_class = 'Renda Fixa'

    asset_info['last_close_price'] = round(last_close_price, 2)
    asset_info['currency'] = currency
    asset_info['long_name'] = long_name
    asset_info['asset_class'] = asset_class

    position_total = 0
    rentabiliy = -100
    price_gain = -100
    by_year = None
    if last_close_price != None and position_sum > 0:
        position_total = position_sum * last_close_price
        rentabiliy = 100 * (position_total/liquid_cost - 1)
        price_gain = 100 * (last_close_price/buy_avg_price - 1)
        if age is not None:
            by_year = round(rentabiliy/(age.days/365), 2)
            
    
    asset_info['position_total'] = round(position_total, 2)
    asset_info['rentability'] = round(rentabiliy, 2)
    asset_info['price_gain'] = round(price_gain, 2)
    asset_info['rentability_by_year'] = by_year

    app.logger.debug(asset_info)

def process_b3_asset_request(request, asset):
    app.logger.info(f'Processing view asset request for "{asset}".')

    asset_info = { 'valid': False }
    dataframes = {}

    query = B3_Movimentation.query.filter(B3_Movimentation.produto.like(f'%{asset}%')).order_by(B3_Movimentation.data.asc())
    result = query.all()
    movimentation_df = b3_movimentation_sql_to_df(result)
    if len(movimentation_df) == 0:
        app.logger.warning(f'Movimentation data not found for {asset}')
        return asset_info
    
    dataframes['movimentation'] = movimentation_df

    movimentation_df['Ticker'] = parse_b3_ticker(movimentation_df['Produto'])
    ticker = movimentation_df['Ticker'].value_counts().index[0]

    credit = movimentation_df.loc[movimentation_df['Entrada/Saída'] == "Credito"]
    debit = movimentation_df.loc[movimentation_df['Entrada/Saída'] == "Debito"]

    buys = credit.loc[
        (
            (credit['Movimentação'] == "Compra")
            | (credit['Movimentação'] == "Desdobro") 
            | (credit['Movimentação'] == "Bonificação em Ativos")
            | (credit['Movimentação'] == "Atualização")
        )
    ]

    sells = debit.loc[
        (
            (debit['Movimentação'] == "Venda")
        )
    ]

    # TODO process negotiation first 
    query = B3_Negotiation.query.filter(B3_Negotiation.codigo.like(f'%{ticker}%')).order_by(B3_Negotiation.data.asc())
    result = query.all()
    negotiation = b3_negotiation_sql_to_df(result)
    if len(negotiation) > 0:
        dataframes['negotiation'] = negotiation

        negotiation_buys = negotiation.loc[
            (
                (negotiation['Tipo de Movimentação'] == "Compra")
            )
        ]
        # dataframes['negotitation_buys'] = negotiation_buys

        negotiation_sells = negotiation.loc[
            (
                (negotiation['Tipo de Movimentação'] == "Venda")
            )
        ]
        # dataframes['negotitation_sells'] = negotiation_sells

        buys = merge_movimentation_negotiation(buys, negotiation_buys, 'Compra')
        sells = merge_movimentation_negotiation(sells, negotiation_sells, 'Venda')
    else:
        app.logger.warning(f'Warning! Negotiation data not found for {asset}!')
        dataframes['negotiation'] = pd.DataFrame(columns=['Data do Negócio', 'Tipo de Movimentação', 'Mercado', 'Prazo/Vencimento',
                                                          'Instituição', 'Código de Negociação', 'Quantidade', 'Preço','Valor'])
        # return asset_info

    dataframes['buys'] = buys
    dataframes['sells'] = sells

    taxes = debit.loc[
        ((debit['Movimentação'] == "Cobrança de Taxa Semestral"))
    ]
    dataframes['taxes'] = taxes

    wages = credit.loc[
        ((credit['Movimentação'] == "Dividendo") 
         | (credit['Movimentação'] == "Juros Sobre Capital Próprio") 
         | (credit['Movimentação'] == "Reembolso") 
         | (credit['Movimentação'] == "Rendimento")
         | (credit['Movimentação'] == "Leilão de Fração"))
    ]
    dataframes['wages'] = wages

    rents_wage = credit.loc[(
        (credit['Movimentação'] == "Empréstimo")
        & (credit['Valor da Operação'] > 0)
    )]

    asset_info['dataframes'] = dataframes

    process_b3_dataframes(asset, ticker, buys, sells, taxes, wages, rents_wage, asset_info)

    asset_info['valid'] = True
    
    return asset_info

def process_avenue_extract_request(request):
    app.logger.info(f'view_extract_request')

    query = Avenue_Extract.query.order_by(Avenue_Extract.data.asc())
    result = query.all()
    extract = avenue_extract_sql_to_df(result)

    return extract

def process_avenue_asset_request(request, asset):
    app.logger.info(f'Processing view_extract_asset_request for "{asset}".')

    asset_info = {}
    dataframes = {}

    asset_info['valid'] = False
    asset_info['name'] = asset
    
    currency = 'USD'
    first_buy = None
    age = None
    last_close_price = 0

    query = Avenue_Extract.query.filter(Avenue_Extract.produto.like(f'%{asset}%')).order_by(Avenue_Extract.data.asc())
    result = query.all()
    extract_df = avenue_extract_sql_to_df(result)
    if len(extract_df) == 0:
        app.logger.warning(f'Extract data not found for {asset}')
        return asset_info
    
    extract_df['Valor da Operação'] = abs(extract_df['Valor (U$)'])
    
    dataframes['movimentation'] = extract_df

    ticker = extract_df['Produto'].value_counts().index[0]
    asset_info['ticker'] = ticker

    credit = extract_df.loc[extract_df['Entrada/Saída'] == "Credito"]
    debit = extract_df.loc[extract_df['Entrada/Saída'] == "Debito"]

    buys = credit.loc[
        (
            (credit['Movimentação'] == "Compra")
            | (credit['Movimentação'] == "Desdobramento")
        )
    ]
    dataframes['buys'] = buys

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
    dataframes['taxes'] = taxes

    wages = credit.loc[
        (credit['Movimentação'] == "Dividendos")
    ]
    dataframes['wages'] = wages

    if len(buys) > 0:
        first_buy = buys.iloc[0]['Data']
        age = pd.to_datetime("today") - first_buy

    taxes_sum = taxes['Valor da Operação'].sum()
    asset_info['taxes_sum'] = round(taxes_sum, 2)

    wages_sum = wages['Valor da Operação'].sum()
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

    long_name = ''
    asset_class = ''
    if position > 0:
        try:
            stock = yf.Ticker(ticker, session=request_cache)
            last_close_price = stock.info['previousClose']
            currency = stock.info['currency']
            long_name = stock.info['longName']
            asset_class = 'Stock'
        except:
            pass

    asset_info['last_close_price'] = round(last_close_price, 2)
    asset_info['currency'] = currency
    asset_info['long_name'] = long_name
    asset_info['asset_class'] = asset_class

    position_total = 0
    rentabiliy = -100
    price_gain = -100
    by_year = None
    if last_close_price != None and position_sum > 0:
        position_total = position_sum * last_close_price
        rentabiliy = 100 * (position_total/liquid_cost - 1)
        price_gain = 100 * (last_close_price/buy_avg_price - 1)
        if age is not None:
            by_year = round(rentabiliy/(age.days/365), 2)
            
    
    asset_info['position_total'] = round(position_total, 2)
    asset_info['rentability'] = round(rentabiliy, 2)
    asset_info['price_gain'] = round(price_gain, 2)
    asset_info['rentability_by_year'] = by_year

    app.logger.debug(asset_info)

    asset_info['dataframes'] = dataframes
    asset_info['valid'] = True
    return asset_info

def process_generic_extract_request(request):
    app.logger.info(f'view_generic_extract')

    query = Generic_Extract.query.order_by(Generic_Extract.date.asc())
    result = query.all()
    extract = generic_extract_sql_to_df(result)

    return extract

def process_generic_asset_request(request, asset):
    app.logger.info(f'Processing view_generic_asset_request for "{asset}".')

    asset_info = {}
    dataframes = {}

    asset_info['valid'] = False
    asset_info['name'] = asset
    
    currency = 'BRL'
    first_buy = None
    age = None
    last_close_price = 0

    query = Generic_Extract.query.filter(Generic_Extract.asset.like(f'%{asset}%')).order_by(Generic_Extract.date.asc())
    result = query.all()
    extract_df = generic_extract_sql_to_df(result)
    if len(extract_df) == 0:
        app.logger.warning(f'Extract data not found for {asset}')
        return asset_info
    
    dataframes['movimentation'] = extract_df

    ticker = extract_df['Asset'].value_counts().index[0]
    asset_info['ticker'] = ticker

    buys = extract_df.loc[
        (
            (extract_df['Movimentation'] == "Buy")
        )
    ]
    dataframes['buys'] = buys

    sells = extract_df.loc[
        (
            (extract_df['Movimentation'] == "Sell")
        )
    ]
    dataframes['sells'] = sells
    
    taxes = extract_df.loc[
        (extract_df['Movimentation'] == "Taxes")
    ]
    dataframes['taxes'] = taxes

    wages = extract_df.loc[
        (extract_df['Movimentation'] == "Wages")
    ]
    dataframes['wages'] = wages

    if len(buys) > 0:
        first_buy = buys.iloc[0]['Date']
        age = pd.to_datetime("today") - first_buy

    taxes_sum = abs(taxes['Total'].sum())
    asset_info['taxes_sum'] = round(taxes_sum, 2)

    wages_sum = abs(wages['Total'].sum())
    asset_info['wages_sum'] = round(wages_sum, 2)

    rents_wages_sum = 0
    asset_info['rents_wage_sum'] = round(rents_wages_sum, 2)

    buys_quantity_sum = buys['Quantity'].sum()
    asset_info['buys_quantity_sum'] = buys_quantity_sum

    sells_sum = abs(sells['Quantity'].sum())
    asset_info['sells_sum'] = round(sells_sum, 2)

    position = buys_quantity_sum - sells_sum
    asset_info['position'] = position

    if first_buy is not None:
        asset_info['first_buy'] = first_buy.strftime("%Y-%m-%d")

    if age is not None:
        asset_info['age'] = age.days

    buys_value_sum = buys['Total'].sum()
    asset_info['buys_value_sum'] = round(buys_value_sum, 2)

    sells_value_sum = abs(sells['Total'].sum())
    asset_info['sells_value_sum'] = sells_value_sum

    total_cost = buys_value_sum - sells_value_sum
    asset_info['total_cost'] = round(total_cost, 2)

    liquid_cost = total_cost - wages_sum - rents_wages_sum + taxes_sum
    asset_info['liquid_cost'] = round(liquid_cost, 2)

    buys_wsum = (buys['Quantity'] * buys['Price']).sum()
    buys_quantity = buys['Quantity'].sum()
    buy_avg_price = buys_wsum / buys_quantity if buys_quantity > 0 else 0
    asset_info['buy_avg_price'] = round(buy_avg_price, 2)

    buys_wsum2 = buys['Total'].sum()
    buy_avg_price2 = buys_wsum2 / buys_quantity if buys_quantity > 0 else 0
    asset_info['buy_avg_price2'] = round(buy_avg_price2, 2)
    if asset_info['buy_avg_price'] != asset_info['buy_avg_price2']:
        app.logger.warning("Warning! buys_wsum inconsistency!")

    asset_info['rented'] = 0
    rented = asset_info['rented']

    position_sum = round(position + rented, 4)
    asset_info['position_sum'] = position_sum

    long_name = ''
    asset_class = ''
    # if position > 0:
    app.logger.info('Trying to get online asset data...')
    # try:
    if re.match(r'^(BTC|ETH)$', ticker):
        app.logger.debug('Cripto data!')
        stock = yf.Ticker(ticker + "-USD", session=request_cache)
        info = stock.info
        last_close_price = info['previousClose']
        long_name = info['name']
        rate = usd_exchange_rate('BRL')
        last_close_price = rate * last_close_price
        asset_class = 'Cripto'

    elif re.match(r'.*\.SA', ticker):
        stock = yf.Ticker(ticker, session=request_cache)
        info = stock.info
        last_close_price = info['previousClose']
        long_name = info['longName']
        asset_class = 'Ação'

    elif ticker in scrape_dict:
        app.logger.info(f'Scraping data for {ticker}')
        scrap_info = scrape_dict[ticker]
        scraped = scrape_data(scrap_info['url'], scrap_info['xpath'])
        last_close_price = scraped[0]

    else:
        try:
            stock = yf.Ticker(ticker, session=request_cache)
            info = stock.info
            last_close_price = info['previousClose']
            long_name = info['longName']
            currency = info['currency']
        except:
            app.logger.info('Ticker not supported!')
            last_close_price = buy_avg_price
        
        # except:
        #     app.logger.error('Failed to get online asset data!')
        #     pass

    asset_info['last_close_price'] = round(last_close_price, 2)
    asset_info['currency'] = currency
    asset_info['long_name'] = long_name
    asset_info['asset_class'] = asset_class

    position_total = 0
    rentabiliy = -100
    price_gain = -100
    by_year = None
    if last_close_price != None and position_sum > 0:
        position_total = position_sum * last_close_price
        rentabiliy = 100 * (position_total/liquid_cost - 1)
        price_gain = 100 * (last_close_price/buy_avg_price - 1)
        if age is not None:
            by_year = round(rentabiliy/(age.days/365), 2)
    
    asset_info['position_total'] = round(position_total, 2)
    asset_info['rentability'] = round(rentabiliy, 2)
    asset_info['price_gain'] = round(price_gain, 2)
    asset_info['rentability_by_year'] = by_year

    asset_info['valid'] = True
    app.logger.debug(asset_info)

    asset_info['dataframes'] = dataframes
    return asset_info

def process_consolidate_request(request):
    app.logger.info(f'view_consolidate_request')

    ret = {}
    ret['valid'] = False
    
    query = B3_Movimentation.query
    result = query.all()
    movimentation = b3_movimentation_sql_to_df(result)
    b3_consolidate = pd.DataFrame()
    if len(movimentation) > 0:
        movimentation['Produto_Parsed'] = parse_b3_product(movimentation['Produto'])
        movimentation['Ticker'] = parse_b3_ticker(movimentation['Produto'])

        products = movimentation['Ticker'].value_counts().to_frame()
        for index, product in products.iterrows():
            asset_info = process_b3_asset_request(request, product.name)
            new_row = pd.DataFrame([asset_info])
            b3_consolidate = pd.concat([b3_consolidate, new_row], ignore_index=True)

        b3_consolidate['url'] = b3_consolidate['name'].apply(lambda x: f"<a href='/view/{x}'>{x}</a>")

    query = Avenue_Extract.query
    result = query.all()
    movimentation = avenue_extract_sql_to_df(result)
    avenue_consolidate = pd.DataFrame()
    if len(movimentation) > 0:
        products = movimentation['Produto'].value_counts().to_frame()
        print(products)
        for index, product in products.iterrows():
            if product.name == '':
                continue

            asset_info = process_avenue_asset_request(request, product.name)
            new_row = pd.DataFrame([asset_info])
            avenue_consolidate = pd.concat([avenue_consolidate, new_row], ignore_index=True)

        avenue_consolidate['url'] = avenue_consolidate['name'].apply(lambda x: f"<a href='/extract/{x}'>{x}</a>")

    query = Generic_Extract.query
    result = query.all()
    movimentation = generic_extract_sql_to_df(result)
    generic_consolidate = pd.DataFrame()
    if len(movimentation) > 0:
        products = movimentation['Asset'].value_counts().to_frame()
        print(products)
        for index, product in products.iterrows():
            if product.name == '':
                continue

            asset_info = process_generic_asset_request(request, product.name)
            new_row = pd.DataFrame([asset_info])
            generic_consolidate = pd.concat([generic_consolidate, new_row], ignore_index=True)

        generic_consolidate['url'] = generic_consolidate['name'].apply(lambda x: f"<a href='/generic/{x}'>{x}</a>")

    # print(pd.DataFrame(asset_list))
    # print(movimentation['Ticker'].value_counts())

    consolidate = pd.concat([b3_consolidate, avenue_consolidate, generic_consolidate])
    if len(consolidate) == 0:
        return ret

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
    total_cost = consolidate_brl['total_cost'].sum()
    total_wages = consolidate_brl['wages_sum'].sum()
    total_rents = consolidate_brl['rents_wage_sum'].sum()
    taxes_sum = consolidate_brl['taxes_sum'].sum()
    liquid_cost = consolidate_brl['liquid_cost'].sum()
    total_position = consolidate_brl['position_total'].sum()

    ret['total_cost_sum'] = round(total_cost, 2)
    ret['total_wages_sum'] = round(total_wages, 2)
    ret['total_rents_wage_sum'] = round(total_rents, 2)
    ret['position_total_sum'] = round(total_position, 2)
    ret['taxes_sum'] = round(taxes_sum, 2)
    ret['rentability'] = round(100 * (total_position/total_cost - 1), 2)
    ret['liquid_cost'] = round(liquid_cost, 2)

    consolidate_usd = consolidate.loc[consolidate['currency'] == 'USD']
    total_cost_usd = consolidate_usd['total_cost'].sum()
    liquid_cost_usd = consolidate_usd['liquid_cost'].sum()
    total_position_usd = consolidate_usd['position_total'].sum()
    total_wages_usd = consolidate_usd['rents_wage_sum'].sum()
    taxes_usd = consolidate_usd['taxes_sum'].sum()
    ret['total_cost_sum_usd'] = round(total_cost_usd, 2)
    ret['total_wages_sum_usd'] = round(consolidate_usd['wages_sum'].sum(), 2)
    ret['total_rents_wage_sum_usd'] = round(total_wages_usd, 2)
    ret['position_total_sum_usd'] = round(total_position_usd, 2)
    ret['taxes_sum_usd'] = round(taxes_usd, 2)
    ret['rentability_usd'] = round(100 * (total_position_usd/total_cost_usd - 1), 2)
    ret['liquid_cost_usd'] = round(liquid_cost_usd, 2)

    rate = usd_exchange_rate('BRL')
    ret['usd_brl'] = rate

    ret['total_cost_sum_usd_brl'] = round(rate * total_cost_usd, 2)
    ret['total_wages_sum_usd_brl'] = round(rate * total_wages_usd, 2)
    ret['total_rents_wage_sum_usd_brl'] = round(rate * total_wages_usd, 2)
    ret['position_total_sum_usd_brl'] = round(rate * total_position_usd, 2)
    ret['taxes_sum_usd_brl'] = round(rate * taxes_usd, 2)

    total_cost_brl = total_cost + total_cost_usd * rate
    total_position_brl = total_position + total_position_usd * rate
    rentability_brl = 100 * (total_position_brl/total_cost_brl - 1)
    ret['total_cost_brl'] = round(total_cost_brl, 2)
    ret['total_position_brl'] = round(total_position_brl, 2)
    ret['rentability_brl'] = round(rentability_brl, 2)

    ret['valid'] = True

    return ret

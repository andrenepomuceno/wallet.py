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
        'class': 'RENDA FIXA'
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
    
    df['Asset'] = parse_b3_product(df['Produto'])
    print(df['Asset'].value_counts())
    #print(df['Produto'].value_counts())

    df['Ticker'] = parse_b3_ticker(df['Produto'])

    grouped = df[['Entrada/Saída', 'Movimentation']].groupby(['Entrada/Saída'])
    print(grouped.value_counts())

    # print(df['Movimentation'].value_counts())

    return df

def process_b3_negotiation_request(request):
    app.logger.info('view_negotiation_request')

    query = B3_Negotiation.query.order_by(B3_Negotiation.data.asc())
    result = query.all()
    df = b3_negotiation_sql_to_df(result)
    return df
    
def merge_movimentation_negotiation(movimentationDf, negotiationDf, movimentationType):
    columns = ['Date', 'Movimentation', 'Quantity', 'Price', 'Total', "Produto"]
    df1 = movimentationDf[columns]

    df2 = negotiationDf.copy()
    df2.rename(columns={'Date': 'Date', "Preço": 'Price', "Valor": 'Total', "Código de Negociação": "Produto"}, inplace=True)
    df2['Movimentation'] = movimentationType
    df2 = df2[columns]

    df_merged = pd.concat([df1, df2], ignore_index=True)
    df_merged.sort_values(by='Date', inplace=True)

    return df_merged

def consolidate_asset_info(ticker, buys, sells, taxes, wages, rent_wages, asset_info):
    currency = 'BRL'
    first_buy = None
    age_years = None
    last_close_price = 0
    long_name = ''
    asset_class = ''
    last_sell = pd.to_datetime("today")

    buy_quantity = buys['Quantity'].sum()
    sell_quantity = sells['Quantity'].sum()
    position = round(buy_quantity - sell_quantity, 8) # avoid machine precision errors on zero

    if len(buys) > 0:
        first_buy = buys.iloc[0]['Date']
        if position <= 0 and len(sells) > 0:
            last_sell = sells.iloc[-1]['Date']
        age_years = last_sell - first_buy
        age_years = age_years.days/365

    cost = (buys['Quantity'] * buys['Price']).sum()
    avg_price = cost / buy_quantity if buy_quantity > 0 else 0

    wages_sum = wages['Total'].sum()
    if rent_wages is not None:
        rent_wages_sum = rent_wages['Total'].sum()
    else:
        rent_wages_sum = 0
    taxes_sum = taxes['Total'].sum()

    liquid_cost = cost - wages_sum - rent_wages_sum + taxes_sum

    sells_sum = abs(sells['Total'].sum())

    realized_gain = 0
    for index, row in sells.iterrows():
        date = row['Date']
        quantity = abs(row['Quantity'])
        price = row['Price']

        buys_before_sell = buys.loc[buys['Date'] <= date]
        last_buy_quantity = buys_before_sell['Quantity'].sum()
        last_cost = (buys_before_sell['Quantity'] * buys_before_sell['Price']).sum()
        last_avg_price = last_cost / last_buy_quantity if last_buy_quantity > 0 else 0
        realized = (price - last_avg_price) * quantity

        print(f'realized = {realized}')

        realized_gain += realized

    if position > 0:
        try:
            if is_valid_b3_ticker(ticker) and (ticker != 'VVAR3'):
                stock = yf.Ticker(ticker + ".SA", session=request_cache)
                long_name = stock.info['longName']
                last_close_price = stock.info['previousClose']
                currency = stock.info['currency']
                asset_class = stock.info['quoteType']

            elif re.match(r'^(BTC|ETH)$', ticker):
                app.logger.debug('Cripto data!')
                stock = yf.Ticker(ticker + "-USD", session=request_cache)
                info = stock.info
                last_close_price = info['previousClose']
                long_name = info['name']
                rate = usd_exchange_rate('BRL')
                last_close_price = rate * last_close_price
                asset_class = stock.info['quoteType']

            elif ticker in scrape_dict:
                app.logger.info(f'Scraping data for {ticker}')
                scrap_info = scrape_dict[ticker]
                scraped = scrape_data(scrap_info['url'], scrap_info['xpath'])
                last_close_price = brl_to_float(scraped[0])
                asset_class = scrap_info['class']

            else:
                stock = yf.Ticker(ticker, session=request_cache)
                last_close_price = stock.info['previousClose']
                currency = stock.info['currency']
                long_name = stock.info['longName']
                asset_class = stock.info['quoteType']

        except Exception as e:
                    app.logger.warning(f'Exception: {e}')
                    pass

    not_realized_gain = (last_close_price - avg_price) * position

    capital_gain = realized_gain + not_realized_gain + wages_sum + rent_wages_sum

    rentability = capital_gain/liquid_cost

    anualized_rentability = 0
    if age_years is not None and age_years > 0:
        anualized_rentability = (1 + rentability)**(1/age_years) - 1

    rented = 0 # TODO
    position = round(position + rented, 2)

    buys_value_sum = buys['Total'].sum()

    position_total = 0
    price_gain = -100
    if last_close_price != None and position > 0:
        position_total = position * last_close_price
        price_gain = 100 * (last_close_price/avg_price - 1)
    
    asset_info['buy_quantity'] = round(buy_quantity, 2)
    asset_info['sell_quantity'] = round(sell_quantity, 2)
    asset_info['position'] = round(position, 2)

    asset_info['cost'] = round(cost, 2)
    asset_info['avg_price'] = round(avg_price, 2)

    asset_info['taxes_sum'] = round(taxes_sum, 2)
    asset_info['wages_sum'] = round(wages_sum, 2)
    asset_info['rent_wages_sum'] = round(rent_wages_sum, 2)

    asset_info['liquid_cost'] = round(liquid_cost, 2)

    asset_info['sells_value_sum'] = sells_sum

    asset_info['realized_gain'] = round(realized_gain, 2)
    asset_info['not_realized_gain'] = round(not_realized_gain, 2)
    asset_info['capital_gain'] = round(capital_gain, 2)

    asset_info['rentability'] = round(100 * rentability, 2)
    asset_info['anualized_rentability'] = round(100 * anualized_rentability, 2)

    if first_buy is not None:
        asset_info['first_buy'] = first_buy.strftime("%Y-%m-%d")

    if last_sell is not None:
        asset_info['last_sell'] = last_sell.strftime("%Y-%m-%d")

    if age_years is not None:
        asset_info['age_years'] = age_years
        asset_info['age'] = round(age_years * 365)
    
    asset_info['buys_value_sum'] = round(buys_value_sum, 2)

    asset_info['rented'] = rented
    
    asset_info['last_close_price'] = round(last_close_price, 2)
    asset_info['currency'] = currency
    asset_info['long_name'] = long_name
    asset_info['asset_class'] = asset_class

    asset_info['position_total'] = round(position_total, 2)
    
    asset_info['price_gain'] = round(price_gain, 2)
    asset_info['rentability_by_year'] = round(100 * anualized_rentability, 2)

    app.logger.debug(asset_info)

def process_b3_asset_request(request, asset):
    app.logger.info(f'Processing view asset request for "{asset}".')

    asset_info = { 'valid': False, 'name': asset }
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
    asset_info['ticker'] = ticker

    credit = movimentation_df.loc[movimentation_df['Entrada/Saída'] == "Credito"]
    debit = movimentation_df.loc[movimentation_df['Entrada/Saída'] == "Debito"]

    buys = credit.loc[
        (
            (credit['Movimentation'] == "Compra")
            | (credit['Movimentation'] == "Desdobro") 
            | (credit['Movimentation'] == "Bonificação em Ativos")
            | (credit['Movimentation'] == "Atualização")
        )
    ]

    sells = debit.loc[
        (
            (debit['Movimentation'] == "Venda")
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
                (negotiation['Movimentation'] == "Compra")
            )
        ]
        # dataframes['negotitation_buys'] = negotiation_buys

        negotiation_sells = negotiation.loc[
            (
                (negotiation['Movimentation'] == "Venda")
            )
        ]
        # dataframes['negotitation_sells'] = negotiation_sells

        buys = merge_movimentation_negotiation(buys, negotiation_buys, 'Compra')
        sells = merge_movimentation_negotiation(sells, negotiation_sells, 'Venda')
    else:
        app.logger.warning(f'Warning! Negotiation data not found for {asset}!')
        dataframes['negotiation'] = pd.DataFrame(columns=['Date', 'Movimentation', 'Mercado', 'Prazo/Vencimento',
                                                          'Instituição', 'Código de Negociação', 'Quantity', 'Price','Total'])
        # return asset_info

    dataframes['buys'] = buys
    dataframes['sells'] = sells

    taxes = debit.loc[
        ((debit['Movimentation'] == "Cobrança de Taxa Semestral"))
    ]
    dataframes['taxes'] = taxes

    wages = credit.loc[
        ((credit['Movimentation'] == "Dividendo") 
         | (credit['Movimentation'] == "Juros Sobre Capital Próprio") 
         | (credit['Movimentation'] == "Reembolso") 
         | (credit['Movimentation'] == "Rendimento")
         | (credit['Movimentation'] == "Leilão de Fração"))
    ]
    dataframes['wages'] = wages

    rents_wage = credit.loc[(
        (credit['Movimentation'] == "Empréstimo")
        & (credit['Total'] > 0)
    )]
    dataframes['rent_wages'] = rents_wage

    consolidate_asset_info(ticker, buys, sells, taxes, wages, rents_wage, asset_info)
    
    asset_info['dataframes'] = dataframes
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

    query = Avenue_Extract.query.filter(Avenue_Extract.produto.like(f'%{asset}%')).order_by(Avenue_Extract.data.asc())
    result = query.all()
    extract_df = avenue_extract_sql_to_df(result)
    if len(extract_df) == 0:
        app.logger.warning(f'Extract data not found for {asset}')
        return asset_info
    
    extract_df['Total'] = abs(extract_df['Total'])
    
    dataframes['movimentation'] = extract_df

    ticker = extract_df['Produto'].value_counts().index[0]
    asset_info['ticker'] = ticker

    credit = extract_df.loc[extract_df['Entrada/Saída'] == "Credito"]
    debit = extract_df.loc[extract_df['Entrada/Saída'] == "Debito"]

    # print(extract_df.to_string())

    buys = credit.loc[
        (
            (credit['Movimentation'] == "Compra")
            | (credit['Movimentation'] == "Desdobramento")
        )
    ]
    dataframes['buys'] = buys

    sells = debit.loc[
        (
            (debit['Movimentation'] == "Venda")
        )
    ]
    dataframes['sells'] = sells

    taxes = debit.loc[
        (debit['Movimentation'] == "Impostos")
        | (debit['Movimentation'] == "Corretagem")
    ]
    dataframes['taxes'] = taxes

    wages = credit.loc[
        (credit['Movimentation'] == "Dividendos")
    ]
    dataframes['wages'] = wages

    consolidate_asset_info(ticker, buys, sells, taxes, wages, None, asset_info)

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

    consolidate_asset_info(ticker, buys, sells, taxes, wages, None, asset_info)

    asset_info['dataframes'] = dataframes
    asset_info['valid'] = True

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
        movimentation['Asset'] = parse_b3_product(movimentation['Produto'])
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

    consolidate = pd.concat([b3_consolidate, avenue_consolidate, generic_consolidate])
    if len(consolidate) == 0:
        return ret
        
    consolidate = consolidate.sort_values(by='rentability', ascending=False)
    ret['consolidate'] = consolidate

    def consolidate_summary(df, rate = 1):
        ret = {}

        cost = rate * df['cost'].sum()
        wages = rate * df['wages_sum'].sum()
        rents = rate * df['rent_wages_sum'].sum()
        taxes = rate * df['taxes_sum'].sum()
        liquid_cost = rate * df['liquid_cost'].sum()
        position = rate * df['position_total'].sum()
        realized_gain = rate * df['realized_gain'].sum()
        not_realized_gain = rate * df['not_realized_gain'].sum()
        capital_gain = rate * df['capital_gain'].sum()

        ret['cost'] = round(cost, 2)
        ret['wages'] = round(wages, 2)
        ret['rents'] = round(rents, 2)
        ret['position'] = round(position, 2)
        ret['taxes'] = round(taxes, 2)
        ret['liquid_cost'] = round(liquid_cost, 2)
        ret['rentability'] = round(100 * (capital_gain/liquid_cost), 2)
        ret['capital_gain'] = round(capital_gain, 2)
        ret['realized_gain'] = round(realized_gain, 2)
        ret['not_realized_gain'] = round(not_realized_gain, 2)

        return ret

    brl_df = consolidate.loc[consolidate['currency'] == 'BRL']
    brl_ret = consolidate_summary(brl_df)
    ret['BRL'] = brl_ret

    usd_df = consolidate.loc[consolidate['currency'] == 'USD']
    usd_ret = consolidate_summary(usd_df)
    ret['USD'] = usd_ret

    rate = usd_exchange_rate('BRL')
    ret['usd_brl'] = rate

    usd_brl_ret = consolidate_summary(usd_df, rate)
    ret['USD/BRL'] = usd_brl_ret

    ret_total = {}

    cost = brl_ret['cost'] + usd_brl_ret['cost']
    wages = brl_ret['wages'] + usd_brl_ret['wages']
    rents = brl_ret['rents'] + usd_brl_ret['rents']
    position = brl_ret['position'] + usd_brl_ret['position']
    liquid_cost = brl_ret['liquid_cost'] + usd_brl_ret['liquid_cost']
    taxes = brl_ret['taxes'] + usd_brl_ret['taxes']
    liquid_cost = brl_ret['liquid_cost'] + usd_brl_ret['liquid_cost']
    capital_gain = brl_ret['capital_gain'] + usd_brl_ret['capital_gain']
    realized_gain = brl_ret['realized_gain'] + usd_brl_ret['realized_gain']
    not_realized_gain = brl_ret['not_realized_gain'] + usd_brl_ret['not_realized_gain']

    ret_total['cost'] = round(cost, 2)
    ret_total['wages'] = round(wages, 2)
    ret_total['rents'] = round(rents, 2)
    ret_total['position'] = round(position, 2)
    ret_total['taxes'] = round(taxes, 2)
    ret_total['liquid_cost'] = round(liquid_cost, 2)
    ret_total['rentability'] = round(100 * capital_gain/liquid_cost, 2)
    ret_total['capital_gain'] = round(capital_gain, 2)
    ret_total['realized_gain'] = round(realized_gain, 2)
    ret_total['not_realized_gain'] = round(not_realized_gain, 2)

    ret['TOTAL'] = ret_total

    ret['valid'] = True

    return ret

import re
import requests
import requests_cache
import pandas as pd
# import yfinance_cache as yf
import yfinance as yf
from lxml import html

from app import app, db
from app.models import B3Movimentation, B3Negotiation, AvenueExtract, GenericExtract
from app.models import b3_movimentation_sql_to_df, b3_negotiation_sql_to_df
from app.models import avenue_extract_sql_to_df, generic_extract_sql_to_df
from app.utils.parsing import is_b3_fii_ticker, is_b3_stock_ticker, brl_to_float

import plotly.graph_objects as go
import plotly.offline as pyo

scrape_dict = {
    "Tesouro Selic 2029": {
        'url': 'https://taxas-tesouro.com/resgatar/tesouro-selic-2029/',
        'xpath': '//*[@id="gatsby-focus-wrapper"]/div/div[2]/main/div[1]/div/div[1]/div[4]/div[2]/span',
        'class': 'Renda Fixa'
    }
}

request_cache = requests_cache.CachedSession('request_cache', expire_after=6*60*60)

def scrape_data(url, xpath):
    try:
        response = request_cache.get(url)
        response.raise_for_status()
        tree = html.fromstring(response.content)
        elements = tree.xpath(xpath)
        ret = [element.text_content().strip() for element in elements]
        print('Scrap done!')
        return ret
    except requests.RequestException as e:
        print(f"Erro ao acessar a URL: {e}")
    except Exception as e:
        print(f"Erro ao realizar o scraping: {e}")

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
    query = B3Movimentation.query.order_by(B3Movimentation.data.asc())

    if request.method == 'POST':
        filters = request.form.to_dict()
        for key, value in filters.items():
            if value:
                column = getattr(B3Movimentation, key, None)
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

    print(df['Asset'].value_counts())
    #print(df['Produto'].value_counts())

    grouped = df[['Entrada/Saída', 'Movimentation']].groupby(['Entrada/Saída'])
    print(grouped.value_counts())

    # print(df['Movimentation'].value_counts())

    return df

def process_b3_negotiation_request(request):
    app.logger.info('view_negotiation_request')

    query = B3Negotiation.query.order_by(B3Negotiation.data.asc())
    result = query.all()
    df = b3_negotiation_sql_to_df(result)
    return df

def merge_movimentation_negotiation(movimentationDf, negotiationDf, movimentationType):
    if movimentationDf is None or negotiationDf is None:
        return

    columns = ['Date', 'Movimentation', 'Quantity', 'Price', 'Total', "Produto", 'Asset']
    df1 = movimentationDf[columns]

    df2 = negotiationDf.copy()
    df2.rename(columns={
        'Date': 'Date',
        "Preço": 'Price',
        "Valor": 'Total',
        "Código de Negociação":
        "Produto"
    }, inplace=True)
    df2['Movimentation'] = movimentationType
    df2 = df2[columns]

    df_merged = pd.concat([df1, df2], ignore_index=True)
    df_merged.sort_values(by='Date', inplace=True)

    return df_merged

def calc_avg_price(df):
    quantity = df['Quantity'].sum()
    cost = (df['Quantity'] * df['Price']).sum()
    avg_price = cost / quantity if quantity > 0 else 0
    return avg_price

def plot_price_history(asset_info, buys):
    if 'info' not in asset_info:
        return None

    info = asset_info['info']
    if 'symbol' not in info:
        return None

    stock = yf.Ticker(asset_info['info']['symbol'], session=request_cache)
    df = stock.history(start=asset_info['first_buy'], end=asset_info['last_sell'])

    def add_moving_average(ma_size, df, color='green'):
        ma_name="MA" + str(ma_size)
        df[ma_name] = df['Close'].rolling(ma_size).mean()
        return go.Scatter(
            x=df.index,
            y=df[ma_name],
            line=dict(color=color, width=1),
            name=ma_name
        )

    print(buys)

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        showlegend=False,
    ))
    fig.add_trace(add_moving_average(20, df, 'blue'))
    fig.add_trace(add_moving_average(100, df, 'cyan'))
    fig.update_layout()
    fig.update_yaxes(autorange=True, fixedrange=False)

    graph_html = pyo.plot(fig, output_type='div')

    return graph_html

def get_yfinance_data(ticker, asset_info):
    stock = yf.Ticker(ticker, session=request_cache)
    info = stock.info

    # last_close_price = info['previousClose']
    currency = info['currency']
    asset_class = info['quoteType']
    long_name = info['longName']

    data = stock.history(period='1d')
    last_close_price = data['Close'][0]

    asset_info['last_close_price'] = round(last_close_price, 2)
    asset_info['currency'] = currency
    asset_info['long_name'] = long_name
    asset_info['asset_class'] = asset_class
    asset_info['info'] = stock.info

def get_online_info(ticker, asset_info = {}):
    app.logger.info(f'Scraping data for {ticker}')

    ticker_blacklist = ['VVAR3']
    if ticker in ticker_blacklist:
        return asset_info

    try:
        if is_b3_stock_ticker(ticker):
            get_yfinance_data(ticker + ".SA", asset_info)
            asset_info['asset_class'] = 'Equity'

        elif is_b3_fii_ticker(ticker):
            get_yfinance_data(ticker + ".SA", asset_info)
            asset_info['asset_class'] = 'FII'

        elif re.match(r'^(BTC|ETH)$', ticker):
            get_yfinance_data(ticker + "-USD", asset_info)
            rate = usd_exchange_rate('BRL')
            asset_info['last_close_price'] = round(rate * asset_info['last_close_price'], 2)
            asset_info['currency'] = 'BRL'
            asset_info['asset_class'] = 'Cripto'

        elif ticker in scrape_dict:
            scrap_info = scrape_dict[ticker]
            scraped = scrape_data(scrap_info['url'], scrap_info['xpath'])
            asset_info['last_close_price'] = brl_to_float(scraped[0])
            asset_info['asset_class'] = scrap_info['class']

        else:
            get_yfinance_data(ticker, asset_info)

    except Exception as e:
        app.logger.warning(f'Exception: {e}')
        pass

    return asset_info

def consolidate_asset_info(ticker, buys, sells, taxes, wages, rent_wages, asset_info):
    first_buy = None
    age_years = None
    last_close_price = 0
    last_sell = pd.to_datetime("today")

    buy_quantity = buys['Quantity'].sum()
    sell_quantity = abs(sells['Quantity'].sum())
    shares = round(buy_quantity - sell_quantity, 8) # avoid machine precision errors on zero

    if len(buys) > 0:
        first_buy = buys.iloc[0]['Date']
        if shares <= 0 and len(sells) > 0:
            last_sell = sells.iloc[-1]['Date']
        age_years = last_sell - first_buy
        age_years = age_years.days/365

    cost = (buys['Quantity'] * buys['Price']).sum()
    avg_price = calc_avg_price(buys)

    wages_sum = wages['Total'].sum()
    if rent_wages is not None:
        rent_wages_sum = rent_wages['Total'].sum()
    else:
        rent_wages_sum = 0
    taxes_sum = taxes['Total'].sum()

    liquid_cost = cost - wages_sum - rent_wages_sum + taxes_sum

    sells_sum = abs(sells['Total'].sum())

    realized_gain = 0
    sells['Realized Gain'] = 0.0
    for index, row in sells.iterrows():
        date = row['Date']
        quantity = abs(row['Quantity'])
        price = row['Price']

        buys_before_sell = buys.loc[buys['Date'] <= date]
        last_avg_price = calc_avg_price(buys_before_sell)
        realized = (price - last_avg_price) * quantity

        sells.at[index, 'Realized Gain'] = realized

    realized_gain = sells['Realized Gain'].sum()

    asset_info['last_close_price'] = 0
    asset_info['currency'] = 'BRL'
    asset_info['long_name'] = ''
    asset_info['asset_class'] = ''
    asset_info['info'] = {}
    if first_buy is not None:
        asset_info['first_buy'] = first_buy.strftime("%Y-%m-%d")
    if last_sell is not None:
        asset_info['last_sell'] = last_sell.strftime("%Y-%m-%d")
    if shares > 0:
        online_data = get_online_info(ticker, asset_info)
        last_close_price = online_data['last_close_price']

    not_realized_gain = (last_close_price - avg_price) * shares

    capital_gain = realized_gain + not_realized_gain + wages_sum + rent_wages_sum

    rentability = capital_gain/liquid_cost

    anualized_rentability = 0
    if age_years is not None and age_years > 0:
        anualized_rentability = (1 + rentability)**(1/age_years) - 1

    rented = 0 # TODO calc rented shares from b3 movimentation data
    # shares = round(shares + rented, 8)

    buys_value_sum = buys['Total'].sum()

    position_total = 0
    price_gain = -100
    if last_close_price is not None and shares > 0:
        position_total = shares * last_close_price
        price_gain = 100 * (last_close_price/avg_price - 1)

    asset_info['buy_quantity'] = round(buy_quantity, 2)
    asset_info['sell_quantity'] = round(sell_quantity, 2)
    asset_info['position'] = round(shares, 8)

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

    if age_years is not None:
        asset_info['age_years'] = round(age_years, 2)
        asset_info['age'] = round(age_years * 365)

    asset_info['buys_value_sum'] = round(buys_value_sum, 2)

    asset_info['rented'] = rented

    asset_info['position_total'] = round(position_total, 2)

    asset_info['price_gain'] = round(price_gain, 2)
    asset_info['rentability_by_year'] = round(100 * anualized_rentability, 2)

    asset_info['valid'] = True

    # app.logger.debug(print(json.dumps(asset_info, indent = 4)))

    return asset_info

def process_b3_asset_request(request, asset):
    app.logger.info(f'Processing view asset request for "{asset}".')

    columns = ['Date', 'Movimentation', 'Quantity', 'Price', 'Total', "Produto", 'Asset']

    asset_info = { 'valid': False, 'name': asset }
    dataframes = {}

    query = B3Movimentation.query.filter(
        B3Movimentation.produto.like(f'%{asset}%')).order_by(B3Movimentation.data.asc())
    result = query.all()
    movimentation_df = b3_movimentation_sql_to_df(result)
    if len(movimentation_df) > 0:
        ticker = movimentation_df['Asset'].value_counts().index[0]

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
    else:
        app.logger.warning(f'Movimentation data not found for {asset}')
        movimentation_df = pd.DataFrame(columns=columns)
        credit = pd.DataFrame(columns=columns)
        debit = pd.DataFrame(columns=columns)
        buys = pd.DataFrame(columns=columns)
        sells = pd.DataFrame(columns=columns)


    dataframes['movimentation'] = movimentation_df

    query = B3Negotiation.query.filter(
        B3Negotiation.codigo.like(f'%{asset}%')).order_by(B3Negotiation.data.asc())
    result = query.all()
    negotiation = b3_negotiation_sql_to_df(result)
    if len(negotiation) > 0:
        ticker = negotiation['Asset'].value_counts().index[0]

        negotiation_buys = negotiation.loc[
            (
                (negotiation['Movimentation'] == "Compra")
            )
        ]

        negotiation_sells = negotiation.loc[
            (
                (negotiation['Movimentation'] == "Venda")
            )
        ]
    else:
        app.logger.warning(f'Negotiation data not found for {asset}!')
        negotiation = pd.DataFrame(columns=columns)
        negotiation_buys = pd.DataFrame(columns=columns)
        negotiation_sells = pd.DataFrame(columns=columns)

    dataframes['negotiation'] = negotiation
    asset_info['ticker'] = ticker

    buys = merge_movimentation_negotiation(buys, negotiation_buys, 'Compra')
    sells = merge_movimentation_negotiation(sells, negotiation_sells, 'Venda')

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
         | (credit['Movimentation'] == "Resgate")
    ]
    dataframes['wages'] = wages

    rents_wage = credit.loc[(
        (credit['Movimentation'] == "Empréstimo")
        & (credit['Total'] > 0)
    )]
    dataframes['rent_wages'] = rents_wage

    consolidate_asset_info(ticker, buys, sells, taxes, wages, rents_wage, asset_info)

    asset_info['dataframes'] = dataframes

    return asset_info

def process_avenue_extract_request(request):
    app.logger.info('process_avenue_extract_request')

    query = AvenueExtract.query.order_by(AvenueExtract.data.asc())
    result = query.all()
    extract = avenue_extract_sql_to_df(result)

    return extract

def process_avenue_asset_request(request, asset):
    app.logger.info(f'Processing view_extract_asset_request for "{asset}".')

    asset_info = {}
    dataframes = {}

    asset_info['valid'] = False
    asset_info['name'] = asset

    query = AvenueExtract.query.filter(
        AvenueExtract.produto.like(f'%{asset}%')).order_by(AvenueExtract.data.asc())
    result = query.all()
    extract_df = avenue_extract_sql_to_df(result)
    if len(extract_df) == 0:
        app.logger.warning(f'Extract data not found for {asset}')
        return asset_info

    extract_df['Total'] = abs(extract_df['Total'])

    dataframes['movimentation'] = extract_df

    ticker = extract_df['Asset'].value_counts().index[0]
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
    return asset_info

def process_generic_extract_request(request):
    app.logger.info(f'view_generic_extract')

    query = GenericExtract.query.order_by(GenericExtract.date.asc())
    result = query.all()
    extract = generic_extract_sql_to_df(result)

    return extract

def process_generic_asset_request(request, asset):
    app.logger.info(f'Processing view_generic_asset_request for "{asset}".')

    asset_info = {}
    dataframes = {}

    asset_info['valid'] = False
    asset_info['name'] = asset

    query = GenericExtract.query.filter(
        GenericExtract.asset.like(f'%{asset}%')).order_by(GenericExtract.date.asc())
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

    return asset_info

def process_consolidate_request(request):
    app.logger.info('process_consolidate_request')

    ret = {}
    ret['valid'] = False

    def load_products(query, sql_to_df):
        result = query.all()
        df = sql_to_df(result)
        products = pd.DataFrame()
        if len(df) <= 0:
            return products

        products = df['Asset'].unique().tolist()
        return products

    def load_consolidate(products, process, route):
        consolidate = pd.DataFrame()
        if len(products) <= 0:
            return consolidate

        for product in products:
            if product == '':
                continue
            asset_info = process(request, product)
            new_row = pd.DataFrame([asset_info])
            consolidate = pd.concat([consolidate, new_row], ignore_index=True)

        consolidate['url'] = consolidate['name'].apply(
            lambda x: f"<a href='/{route}/{x}' target='_blank'>{x}</a>")

        return consolidate

    products_neg = load_products(B3Negotiation.query, b3_negotiation_sql_to_df)
    products_mov = load_products(B3Movimentation.query, b3_movimentation_sql_to_df)
    b3_products = list(set(products_neg) | set(products_mov))
    b3_consolidate = load_consolidate(b3_products, process_b3_asset_request, 'view/b3')

    avenue_products = load_products(AvenueExtract.query, avenue_extract_sql_to_df)
    avenue_consolidate = load_consolidate(avenue_products,
                                          process_avenue_asset_request, 'view/avenue')

    generic_products = load_products(GenericExtract.query, generic_extract_sql_to_df)
    generic_consolidate = load_consolidate(generic_products,
                                           process_generic_asset_request, 'view/generic')

    consolidate = pd.concat([b3_consolidate, avenue_consolidate, generic_consolidate])
    if len(consolidate) == 0:
        return ret

    consolidate = consolidate.sort_values(by='rentability', ascending=False)
    # ret['consolidate'] = consolidate

    def consolidate_total(df, rate = 1.0, currency='BRL', asset_class=''):
        total = df.select_dtypes(include=['number']).sum() * rate

        total['rentability'] = 100 * (total['capital_gain']/total['liquid_cost'])
        total = total.round(2)

        total['currency'] = currency
        total['asset_class'] = asset_class

        return total

    grouped = consolidate.groupby(['currency','asset_class'])
    consolidate_by_group = pd.DataFrame()
    group_df = []
    for name, group in grouped:
        currency = name[0]
        rate = 1
        asset_class = name[1] if name[1] != '' else 'Sold'

        if currency == 'USD':
            rate = usd_exchange_rate('BRL')
            currency = 'BRL'
            asset_class += ' (USD)'

        group_consolidate = group[['cost', 'wages_sum', 'rent_wages_sum', 'taxes_sum',
                                   'liquid_cost', 'position_total', 'realized_gain',
                                   'not_realized_gain', 'capital_gain']]
        group_consolidate = group_consolidate.rename(columns={
            'wages_sum': 'wages',
            'rent_wages_sum': 'rents',
            'taxes_sum': 'taxes',
            'position_total': 'position'
        })
        group_consolidate = consolidate_total(group_consolidate, rate, currency, asset_class)
        group_df += [{'name': asset_class, 'df': group, 'consolidate': group_consolidate}]

        new_row = pd.DataFrame([group_consolidate])
        consolidate_by_group = pd.concat([consolidate_by_group, new_row], ignore_index=True)

    consolidate_by_group['relative_position'] = round(
        consolidate_by_group['position']/consolidate_by_group['position'].sum() * 100, 2)

    total = consolidate_total(consolidate_by_group, 1, 'BRL', 'Total')
    new_row = pd.DataFrame([total])
    consolidate_by_group = pd.concat([consolidate_by_group, new_row], ignore_index=True)

    consolidate_by_group = consolidate_by_group.sort_values(by='position', ascending=False)
    ret['consolidate_by_group'] = consolidate_by_group

    group_df = sorted(group_df, key=lambda x: x['consolidate']['position'], reverse=True)
    ret['group_df'] = group_df

    ret['usd_brl'] = usd_exchange_rate('BRL')

    ret['valid'] = True

    return ret

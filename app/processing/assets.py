"""Per-asset processing: classify movements, run consolidate_asset_info."""
from datetime import datetime

import pandas as pd

from app import app
from app.models import (
    B3Movimentation, B3Negotiation, AvenueExtract, GenericExtract,
    b3_movimentation_sql_to_df, b3_negotiation_sql_to_df,
    avenue_extract_sql_to_df, generic_extract_sql_to_df,
)
from app.utils.memocache import ttl_memoize

from .extracts import calc_avg_price, merge_movimentation_negotiation


def consolidate_asset_info(dataframes, asset_info, until_date=None, date_close_price=None):
    # Late import so tests patching `app.processing.get_online_info` take effect.
    from app import processing

    ticker = asset_info['ticker']

    if until_date is None:
        until_date = datetime.now()

    buys = dataframes['buys']
    buys = buys.loc[buys['Date'] <= pd.to_datetime(until_date)]

    sells = dataframes['sells'].copy()
    sells = sells.loc[sells['Date'] <= pd.to_datetime(until_date)]

    taxes = dataframes['taxes']
    taxes = taxes.loc[taxes['Date'] <= pd.to_datetime(until_date)]

    wages = dataframes['wages']
    wages = wages.loc[wages['Date'] <= pd.to_datetime(until_date)]

    rent_wages = None
    if 'rent_wages' in dataframes:
        rent_wages = dataframes['rent_wages']

    last_close_price = 0

    buy_quantity = buys['Quantity'].sum()
    sell_quantity = abs(sells['Quantity'].sum())
    shares = round(buy_quantity - sell_quantity, 8)  # avoid machine precision errors on zero

    last_sell = until_date
    if shares <= 0 and len(sells) > 0:
        last_sell = sells.iloc[-1]['Date']

    first_buy = None
    age_years = 0
    if len(buys) > 0:
        first_buy = buys.iloc[0]['Date']
        age_years = last_sell - first_buy
        age_years = age_years.days / 365

    cost = (buys['Quantity'] * buys['Price']).sum()
    avg_price = calc_avg_price(buys)

    wages_sum = wages['Total'].sum()
    rent_wages_sum = 0
    if rent_wages is not None:
        rent_wages_sum = rent_wages['Total'].sum()

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

        sells.loc[index, 'Realized Gain'] = realized

    realized_gain = sells['Realized Gain'].sum()

    asset_info['last_close_price'] = 0
    asset_info.setdefault('last_close_variation', 0)
    asset_info['info'] = {}
    if first_buy is not None:
        asset_info['first_buy'] = first_buy.strftime("%Y-%m-%d")
    if last_sell is not None:
        asset_info['last_sell'] = last_sell.strftime("%Y-%m-%d")
    if shares > 0:
        if date_close_price is not None:
            asset_info['last_close_price'] = date_close_price
        else:
            processing.get_online_info(ticker, asset_info)
    else:
        asset_info['currency'] = 'BRL'
        asset_info['asset_class'] = 'Sold'
    last_close_price = asset_info['last_close_price']

    not_realized_gain = (last_close_price - avg_price) * shares

    capital_gain = realized_gain + not_realized_gain + wages_sum + rent_wages_sum

    rentability = capital_gain / liquid_cost if liquid_cost > 0 else 0

    anualized_rentability = 0
    if age_years is not None and age_years >= 1.0:
        anualized_rentability = (1 + rentability) ** (1 / age_years) - 1

    rented = 0  # TODO calc rented shares from b3 movimentation data

    buys_value_sum = buys['Total'].sum()

    position_total = 0
    price_gain = -100
    if last_close_price is not None and shares > 0:
        position_total = shares * last_close_price
        price_gain = 100 * (last_close_price / avg_price - 1)

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

    dataframes['sells'] = sells

    return asset_info


@ttl_memoize('asset')
def process_b3_asset_request(asset):
    app.logger.info('Processing view asset request for %s.', asset)

    columns = ['Date', 'Movimentation', 'Quantity', 'Price', 'Total', "Produto", 'Asset']

    asset_info = {'valid': False, 'name': asset, 'source': 'b3'}
    dataframes = {}
    ticker = asset  # default fallback if DB has no rows

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
            )
        ]

        sells = debit.loc[
            (
                (debit['Movimentation'] == "Venda")
            )
        ]
    else:
        app.logger.warning('Movimentation data not found for %s', asset)
        movimentation_df = pd.DataFrame(columns=columns)
        credit = pd.DataFrame(columns=columns)
        debit = pd.DataFrame(columns=columns)
        buys = pd.DataFrame(columns=columns)
        sells = pd.DataFrame(columns=columns)

    dataframes['movimentation'] = movimentation_df

    query = B3Negotiation.query.filter(
        B3Negotiation.codigo.like(f'%{asset}%')).order_by(B3Negotiation.data.asc())
    result = query.all()
    negotiation_df = b3_negotiation_sql_to_df(result)
    if len(negotiation_df) > 0:
        ticker = negotiation_df['Asset'].value_counts().index[0]

        negotiation_buys = negotiation_df.loc[
            (
                (negotiation_df['Movimentation'] == "Compra")
            )
        ]

        negotiation_sells = negotiation_df.loc[
            (
                (negotiation_df['Movimentation'] == "Venda")
            )
        ]
    else:
        app.logger.warning('Negotiation data not found for %s!', asset)
        negotiation_df = pd.DataFrame(columns=columns)
        negotiation_buys = pd.DataFrame(columns=columns)
        negotiation_sells = pd.DataFrame(columns=columns)

    dataframes['negotiation'] = negotiation_df
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
         | (credit['Movimentation'] == "Leilão de Fração")
         | (credit['Movimentation'] == "Resgate"))
    ]
    dataframes['wages'] = wages

    rents_wage = credit.loc[(
        (credit['Movimentation'] == "Empréstimo")
        & (credit['Total'] > 0)
    )]
    dataframes['rent_wages'] = rents_wage

    consolidate_asset_info(dataframes, asset_info)

    asset_info['dataframes'] = dataframes

    return asset_info


@ttl_memoize('asset')
def process_avenue_asset_request(asset):
    app.logger.info('Processing view_extract_asset_request for "%s".', asset)

    asset_info = {}
    dataframes = {}

    asset_info['valid'] = False
    asset_info['name'] = asset
    asset_info['source'] = 'avenue'

    query = AvenueExtract.query.filter(
        AvenueExtract.produto.like(f'%{asset}%')).order_by(AvenueExtract.data.asc())
    result = query.all()
    extract_df = avenue_extract_sql_to_df(result)
    if len(extract_df) == 0:
        app.logger.warning('Extract data not found for %s', asset)
        return asset_info

    extract_df['Total'] = abs(extract_df['Total'])

    dataframes['movimentation'] = extract_df

    ticker = extract_df['Asset'].value_counts().index[0]
    asset_info['ticker'] = ticker

    credit = extract_df.loc[extract_df['Entrada/Saída'] == "Credito"]
    debit = extract_df.loc[extract_df['Entrada/Saída'] == "Debito"]

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

    consolidate_asset_info(dataframes, asset_info)
    asset_info['currency'] = 'USD'

    asset_info['dataframes'] = dataframes
    return asset_info


@ttl_memoize('asset')
def process_generic_asset_request(asset):
    app.logger.info('Processing view_generic_asset_request for %s.', asset)

    asset_info = {}
    dataframes = {}

    asset_info['valid'] = False
    asset_info['name'] = asset
    asset_info['source'] = 'generic'

    query = GenericExtract.query.filter(
        GenericExtract.asset.like(f'%{asset}%')).order_by(GenericExtract.date.asc())
    result = query.all()
    extract_df = generic_extract_sql_to_df(result)
    if len(extract_df) == 0:
        app.logger.warning('Extract data not found for %s', asset)
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

    consolidate_asset_info(dataframes, asset_info)

    asset_info['dataframes'] = dataframes

    return asset_info

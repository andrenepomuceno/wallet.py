"""Portfolio-wide consolidation across all sources."""
import pandas as pd

from app import app
from app.models import (
    B3Movimentation, B3Negotiation, AvenueExtract, GenericExtract,
    b3_movimentation_sql_to_df, b3_negotiation_sql_to_df,
    avenue_extract_sql_to_df, generic_extract_sql_to_df,
)
from app.utils.memocache import ttl_memoize
from app.utils.scraping import usd_exchange_rate

from .assets import (
    process_b3_asset_request,
    process_avenue_asset_request,
    process_generic_asset_request,
)


def load_products(query, sql_to_df_func):
    result = query.all()
    df = sql_to_df_func(result)
    if len(df) <= 0:
        return []

    products = df['Asset'].unique().tolist()
    return products


def load_consolidate(asset_list, process_asset_func, source):
    consolidate = pd.DataFrame()
    if len(asset_list) <= 0:
        return consolidate

    for asset in asset_list:
        if asset == '':
            continue
        asset_info = process_asset_func(asset)
        if not asset_info.get('valid'):
            continue
        new_row = pd.DataFrame([asset_info])
        consolidate = pd.concat([consolidate, new_row], ignore_index=True)

    consolidate['url'] = consolidate['name'].apply(
        lambda x: f"<a href='/view/{source}/{x}' target='_blank'>Details</a> <a href='/history/{source}/{x}' target='_blank'>History</a>")

    return consolidate


def consolidate_total(df, rate=1.0, currency='BRL', asset_class=''):
    total = df.select_dtypes(include=['number']).sum() * rate
    liquid = total.get('liquid_cost', 0)
    gain = total.get('capital_gain', 0)
    total['rentability'] = 100 * (gain / liquid) if liquid else 0
    total = total.round(2)

    total['currency'] = currency
    total['asset_class'] = asset_class

    return total


def consolidate_group(consolidate):
    grouped = consolidate.groupby(['currency', 'asset_class'])
    consolidate_by_group = pd.DataFrame()
    group_df = []
    for name, group in grouped:
        currency = name[0]
        rate = 1
        asset_class = name[1]

        if currency == 'USD':
            rate = usd_exchange_rate('BRL') or 1.0
            currency = 'BRL'
            asset_class += ' USD'

        group_consolidate = group[['cost', 'wages_sum', 'rent_wages_sum', 'taxes_sum',
                                   'liquid_cost', 'position_total', 'realized_gain',
                                   'not_realized_gain', 'capital_gain']]
        group_consolidate = group_consolidate.rename(columns={
            'wages_sum': 'wages',
            'rent_wages_sum': 'rents',
            'taxes_sum': 'taxes',
            'position_total': 'position'
        })
        group_total = consolidate_total(group_consolidate, rate, currency, asset_class)
        group_df += [{'name': asset_class, 'df': group, 'consolidate': group_total}]

        new_row = pd.DataFrame([group_total])
        consolidate_by_group = pd.concat([consolidate_by_group, new_row], ignore_index=True)

    pos_sum = consolidate_by_group['position'].sum()
    consolidate_by_group['relative_position'] = round(
        consolidate_by_group['position'] / pos_sum * 100, 2) if pos_sum else 0

    return consolidate_by_group, group_df


@ttl_memoize('consolidate')
def process_consolidate_request():
    app.logger.info('process_consolidate_request')

    ret = {}
    ret['valid'] = False

    products_neg = load_products(B3Negotiation.query, b3_negotiation_sql_to_df)
    products_mov = load_products(B3Movimentation.query, b3_movimentation_sql_to_df)
    b3_products = list(set(products_neg) | set(products_mov))
    b3_consolidate = load_consolidate(b3_products, process_b3_asset_request, 'b3')

    avenue_products = load_products(AvenueExtract.query, avenue_extract_sql_to_df)
    avenue_consolidate = load_consolidate(avenue_products,
                                          process_avenue_asset_request, 'avenue')

    generic_products = load_products(GenericExtract.query, generic_extract_sql_to_df)
    generic_consolidate = load_consolidate(generic_products,
                                           process_generic_asset_request, 'generic')

    consolidate = pd.concat([b3_consolidate, avenue_consolidate, generic_consolidate])
    if len(consolidate) == 0:
        return ret

    consolidate = consolidate.sort_values(by='rentability', ascending=False)

    consolidate_by_group, group_df = consolidate_group(consolidate)

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

"""DB → DataFrame request handlers and shared transforms."""
import pandas as pd

from app import app, db
from app.models import (
    B3Movimentation, B3Negotiation, AvenueExtract, GenericExtract,
    b3_movimentation_sql_to_df, b3_negotiation_sql_to_df,
    avenue_extract_sql_to_df, generic_extract_sql_to_df,
)


def process_b3_movimentation_request(request):
    app.logger.info('process_b3_movimentation_request')

    query = B3Movimentation.query.order_by(B3Movimentation.data.desc())

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
    return df


def process_b3_negotiation_request():
    app.logger.info('process_b3_negotiation_request')

    query = B3Negotiation.query.order_by(B3Negotiation.data.desc())
    result = query.all()
    df = b3_negotiation_sql_to_df(result)
    return df


def process_avenue_extract_request():
    app.logger.info('process_avenue_extract_request')

    query = AvenueExtract.query.order_by(AvenueExtract.data.desc())
    result = query.all()
    extract = avenue_extract_sql_to_df(result)

    return extract


def process_generic_extract_request():
    app.logger.info('process_generic_extract_request')

    query = GenericExtract.query.order_by(GenericExtract.date.desc())
    result = query.all()
    extract = generic_extract_sql_to_df(result)

    return extract


def merge_movimentation_negotiation(movimentation_df, negotiation_df, movimentation_type):
    df_merged = pd.DataFrame()
    if movimentation_df is None or negotiation_df is None:
        return df_merged

    columns = ['Date', 'Movimentation', 'Quantity', 'Price', 'Total', "Produto", 'Asset']

    # Normalize movimentation columns
    df1 = movimentation_df.copy()
    for col in columns:
        if col not in df1.columns:
            if col == 'Produto' and 'Asset' in df1.columns:
                df1['Produto'] = df1['Asset']
            else:
                df1[col] = None
    df1 = df1[columns]

    # Normalize negotiation columns (may come from different mappers naming)
    df2 = negotiation_df.copy()
    rename_map = {
        "Preço": 'Price',
        "Valor": 'Total',
        "Código de Negociação": "Produto",
    }
    df2.rename(columns={k: v for k, v in rename_map.items() if k in df2.columns}, inplace=True)
    if 'Produto' not in df2.columns and 'Asset' in df2.columns:
        df2['Produto'] = df2['Asset']
    df2['Movimentation'] = movimentation_type
    for col in columns:
        if col not in df2.columns:
            df2[col] = None
    df2 = df2[columns]

    frames = [d for d in (df1, df2) if not d.empty]
    if not frames:
        return pd.DataFrame(columns=columns)
    df_merged = pd.concat(frames, ignore_index=True)
    df_merged.sort_values(by='Date', inplace=True)

    return df_merged


def calc_avg_price(df):
    quantity = df['Quantity'].sum()
    cost = (df['Quantity'] * df['Price']).sum()
    avg_price = cost / quantity if quantity > 0 else 0
    return avg_price

"""Portfolio consolidate + sold-positions views."""
from flask import flash, jsonify, redirect, render_template, url_for

from app import app
from app.processing import process_consolidate_request
from app.utils.serper import analyze_consolidate_performance_with_gemini

_BY_GROUP_COLUMNS = ['asset_class', 'currency', 'position', 'rentability',
                     'cost', 'liquid_cost', 'wages', 'rents',
                     'taxes', 'capital_gain', 'realized_gain', 'not_realized_gain',
                     'relative_position']

_BY_GROUP_RENAMES = {
    'asset_class': 'Class',
    'currency': 'Currency',
    'position': 'Position',
    'cost': 'Cost',
    'wages': 'Wages',
    'rents': 'Rent Wages',
    'taxes': 'Taxes',
    'liquid_cost': 'Liquid Cost',
    'realized_gain': 'Realized Gain',
    'not_realized_gain': ' Not Realized Gain',
    'capital_gain': 'Capital Gain',
    'rentability': 'Rentability',
    'relative_position': 'Rel. Position',
}

_GROUP_DF_COLUMNS = [
    'name', 'url', 'currency', 'last_close_price', 'last_close_variation',
    'position', 'position_total', 'avg_price',
    'cost', 'wages_sum', 'rent_wages_sum', 'taxes_sum', 'liquid_cost', 'realized_gain',
    'not_realized_gain', 'capital_gain', 'rentability',
    'rentability_by_year', 'age_years',
]

_GROUP_DF_RENAMES = {
    'name': 'Name',
    'url': 'Links',
    'history_url': 'History',
    'currency': 'Currency',
    'last_close_price': 'Close Price',
    'last_close_variation': '1D Variation',
    'position': "Shares",
    'position_total': 'Position',
    'avg_price': 'Avg Price',
    'cost': 'Cost',
    'wages_sum': 'Wages',
    'rent_wages_sum': 'Rent Wages',
    'taxes_sum': 'Taxes',
    'liquid_cost': 'Liquid Cost',
    'realized_gain': 'Realized Gain',
    'not_realized_gain': ' Not Realized Gain',
    'capital_gain': 'Capital Gain',
    'rentability': 'Rentability',
    'rentability_by_year': 'Rentability/year',
    'age_years': 'Age',
}


def _is_sold_group(group):
    name = (group.get('name') or '').strip()
    return name == 'Sold' or name.startswith('Sold ')


def _format_group_df(group_df):
    for group in group_df:
        df = group['df']
        df = df[_GROUP_DF_COLUMNS]
        df = df.rename(columns=_GROUP_DF_RENAMES)
        group['df'] = df
    return group_df


def _format_by_group(by_group):
    by_group = by_group[_BY_GROUP_COLUMNS]
    return by_group.rename(columns=_BY_GROUP_RENAMES)


@app.route('/consolidate', methods=['GET', 'POST'])
def view_consolidate():
    info = process_consolidate_request()

    if not info['valid']:
        flash('Data not found! Please upload something.')
        return redirect(url_for('home'))

    by_group = info['consolidate_by_group']
    group_df = info['group_df']

    active_groups = [g for g in group_df if not _is_sold_group(g)]
    sold_classes = {g['name'] for g in group_df if _is_sold_group(g)}
    if sold_classes and 'asset_class' in by_group.columns:
        by_group = by_group[~by_group['asset_class'].isin(sold_classes)]

    by_group = _format_by_group(by_group)
    group_df = _format_group_df(active_groups)

    return render_template('view_consolidate.html', html_title='Consolidate', info=info,
                           by_group=by_group,
                           group_df=group_df)


@app.route('/sold', methods=['GET'])
def view_sold():
    info = process_consolidate_request()

    if not info['valid']:
        flash('Data not found! Please upload something.')
        return redirect(url_for('home'))

    sold_groups = [g for g in info['group_df'] if _is_sold_group(g)]
    if not sold_groups:
        flash('No sold positions found.')
        return redirect(url_for('view_consolidate'))

    by_group = info['consolidate_by_group']
    sold_classes = {g['name'] for g in sold_groups}
    if 'asset_class' in by_group.columns:
        by_group = by_group[by_group['asset_class'].isin(sold_classes)]
    by_group = _format_by_group(by_group)
    group_df = _format_group_df(sold_groups)

    return render_template('view_consolidate.html', html_title='Sold Positions', info=info,
                           by_group=by_group,
                           group_df=group_df)


@app.route('/api/consolidate/analysis', methods=['GET'])
def api_consolidate_analysis():
    info = process_consolidate_request()

    if not info['valid']:
        return jsonify({'analysis_requested': True, 'analysis': None}), 404

    analysis = analyze_consolidate_performance_with_gemini(info)
    return jsonify({'analysis_requested': True, 'analysis': analysis})

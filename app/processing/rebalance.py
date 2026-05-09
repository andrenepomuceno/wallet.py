"""Portfolio rebalancing: compare ideal (target) vs actual (current) allocations.

All current-portfolio figures are derived exclusively from
`process_consolidate_request()` — this module never re-queries transactions
directly so numbers are always consistent with the Consolidate page.
"""
import pandas as pd

from app import app
from app.models import PortfolioTarget

# Deviation smaller than this threshold (BRL) is treated as HOLD to avoid
# noise from micro-imbalances.
_MIN_DEVIATION_BRL = 10.0

# Minimum delta per individual asset suggestion (BRL).
_MIN_ASSET_DELTA_BRL = 5.0


# ---------------------------------------------------------------------------
# Target weights helpers
# ---------------------------------------------------------------------------

def load_targets():
    """Return {asset_class: target_weight} for all enabled targets."""
    rows = PortfolioTarget.query.filter_by(enabled=True).all()
    return {r.asset_class: r.target_weight for r in rows}


def save_targets(weights: dict):
    """Upsert `weights` (asset_class → float) into `PortfolioTarget`.

    Existing rows not present in `weights` are left unchanged.
    """
    from datetime import datetime
    for asset_class, weight in weights.items():
        row = PortfolioTarget.query.filter_by(asset_class=asset_class).first()
        if row is None:
            row = PortfolioTarget(asset_class=asset_class, target_weight=weight)
            from app import db
            db.session.add(row)
        else:
            row.target_weight = weight
            row.updated_at = datetime.utcnow()
    from app import db
    db.session.commit()


# ---------------------------------------------------------------------------
# Core comparison logic
# ---------------------------------------------------------------------------

def _classes_from_consolidate(info):
    """Return a list of active (non-Sold, non-Total) asset-class rows from
    consolidate_by_group as a plain list of dicts."""
    by_group = info.get('consolidate_by_group')
    if by_group is None or len(by_group) == 0:
        return []
    rows = []
    for _, row in by_group.iterrows():
        cls = str(row.get('asset_class', '')).strip()
        if not cls or cls == 'Total' or cls.startswith('Sold'):
            continue
        rows.append(row.to_dict())
    return rows


def _total_portfolio_brl(class_rows):
    return sum(r.get('position', 0.0) for r in class_rows)


def compute_class_comparison(info, targets: dict) -> pd.DataFrame:
    """Build a DataFrame with one row per active asset class containing:

    asset_class, current_value_brl, current_weight_pct,
    target_weight_pct, deviation_pct, target_value_brl,
    deviation_value_brl, action
    """
    class_rows = _classes_from_consolidate(info)
    total_brl = _total_portfolio_brl(class_rows)

    records = []
    for row in class_rows:
        cls = row['asset_class']
        current_value = float(row.get('position', 0.0))
        current_weight = float(row.get('relative_position', 0.0))
        target_weight = float(targets.get(cls, 0.0))
        target_value = total_brl * target_weight / 100.0
        deviation_pct = round(target_weight - current_weight, 4)
        deviation_value = round(target_value - current_value, 2)

        if abs(deviation_value) < _MIN_DEVIATION_BRL:
            action = 'HOLD'
        elif deviation_value > 0:
            action = 'BUY'
        else:
            action = 'SELL'

        records.append({
            'asset_class': cls,
            'current_value_brl': round(current_value, 2),
            'current_weight_pct': round(current_weight, 2),
            'target_weight_pct': round(target_weight, 2),
            'deviation_pct': deviation_pct,
            'target_value_brl': round(target_value, 2),
            'deviation_value_brl': deviation_value,
            'action': action,
        })

    # Flag classes that have a target but no current position
    for cls, weight in targets.items():
        if weight > 0 and not any(r['asset_class'] == cls for r in records):
            records.append({
                'asset_class': cls,
                'current_value_brl': 0.0,
                'current_weight_pct': 0.0,
                'target_weight_pct': round(float(weight), 2),
                'deviation_pct': round(float(weight), 4),
                'target_value_brl': round(total_brl * float(weight) / 100.0, 2),
                'deviation_value_brl': round(total_brl * float(weight) / 100.0, 2),
                'action': 'BUY',
            })

    df = pd.DataFrame(records) if records else pd.DataFrame(columns=[
        'asset_class', 'current_value_brl', 'current_weight_pct',
        'target_weight_pct', 'deviation_pct', 'target_value_brl',
        'deviation_value_brl', 'action',
    ])
    if len(df) > 0:
        df = df.sort_values('deviation_value_brl', ascending=False)
    return df


def compute_asset_suggestions(info, class_df: pd.DataFrame) -> pd.DataFrame:
    """Generate per-asset buy/sell suggestions proportional to each asset's
    current share of its class total position.

    For classes where the action is BUY and no current position exists, falls
    back to equal distribution across the assets of that class found in
    group_df.
    """
    group_df = info.get('group_df', [])
    # Build {asset_class → list of asset rows}
    class_to_assets: dict[str, list] = {}
    for group in group_df:
        name = (group.get('name') or '').strip()
        if name == 'Total' or name.startswith('Sold'):
            continue
        assets = group.get('df')
        if assets is None or len(assets) == 0:
            continue
        class_to_assets[name] = assets.to_dict('records')

    records = []
    for _, crow in class_df.iterrows():
        cls = crow['asset_class']
        delta = crow['deviation_value_brl']
        action = crow['action']
        if action == 'HOLD':
            continue

        assets = class_to_assets.get(cls, [])
        if not assets:
            continue

        class_total = sum(float(a.get('position_total', 0.0) or 0.0) for a in assets)

        for asset in assets:
            asset_name = asset.get('name', '')
            position_total = float(asset.get('position_total', 0.0) or 0.0)
            price = float(asset.get('last_close_price', 0.0) or 0.0)

            if class_total > 0:
                weight_in_class = position_total / class_total
            else:
                # No current position: distribute equally
                weight_in_class = 1.0 / len(assets)

            asset_delta_brl = round(delta * weight_in_class, 2)
            if abs(asset_delta_brl) < _MIN_ASSET_DELTA_BRL:
                continue

            if price > 0:
                estimated_qty = round(abs(asset_delta_brl) / price, 8)
            else:
                estimated_qty = None

            records.append({
                'asset': asset_name,
                'asset_class': cls,
                'current_value_brl': round(position_total, 2),
                'delta_brl': asset_delta_brl,
                'action': action,
                'last_close_price': round(price, 4) if price else None,
                'estimated_qty': estimated_qty,
            })

    df = pd.DataFrame(records) if records else pd.DataFrame(columns=[
        'asset', 'asset_class', 'current_value_brl',
        'delta_brl', 'action', 'last_close_price', 'estimated_qty',
    ])
    if len(df) > 0:
        df = df.sort_values('delta_brl', ascending=False)
    return df


def compute_summary(class_df: pd.DataFrame, total_brl: float, targets: dict) -> dict:
    """Return a summary dict with portfolio-level KPIs for the comparison."""
    if len(class_df) == 0:
        return {
            'total_portfolio_brl': 0.0,
            'turnover_brl': 0.0,
            'alignment_score': 0.0,
            'classes_out_of_target': 0,
            'most_overweight': None,
            'most_underweight': None,
            'targets_defined': len(targets) > 0,
        }

    abs_dev = class_df['deviation_value_brl'].abs()
    turnover_brl = round(abs_dev.sum() / 2, 2)

    # Alignment score: 100 minus half the sum of absolute deviations in p.p.
    abs_pct_dev = class_df['deviation_pct'].abs()
    alignment_score = round(max(0.0, 100.0 - abs_pct_dev.sum() / 2), 1)

    out_of_target = int((class_df['action'] != 'HOLD').sum())

    over_row = class_df.loc[class_df['deviation_pct'].idxmin()] if len(class_df) > 0 else None
    under_row = class_df.loc[class_df['deviation_pct'].idxmax()] if len(class_df) > 0 else None

    return {
        'total_portfolio_brl': round(total_brl, 2),
        'turnover_brl': turnover_brl,
        'alignment_score': alignment_score,
        'classes_out_of_target': out_of_target,
        'most_overweight': over_row['asset_class'] if over_row is not None and over_row['deviation_pct'] < 0 else None,
        'most_underweight': under_row['asset_class'] if under_row is not None and under_row['deviation_pct'] > 0 else None,
        'targets_defined': len(targets) > 0,
    }


# ---------------------------------------------------------------------------
# Main entry point consumed by the route
# ---------------------------------------------------------------------------

def process_rebalance_request(info=None):
    """Build rebalance comparison data from consolidated portfolio info.

    `info` should be the return value of `process_consolidate_request()`.
    If None or invalid, returns {'valid': False}.
    """
    app.logger.info('process_rebalance_request')

    ret = {'valid': False}

    if info is None or not info.get('valid'):
        return ret

    targets = load_targets()
    class_rows = _classes_from_consolidate(info)
    total_brl = _total_portfolio_brl(class_rows)

    class_df = compute_class_comparison(info, targets)
    asset_df = compute_asset_suggestions(info, class_df)
    summary = compute_summary(class_df, total_brl, targets)

    # Human-readable column names for template rendering
    class_display = class_df.rename(columns={
        'asset_class': 'Class',
        'current_value_brl': 'Current (BRL)',
        'current_weight_pct': 'Current (%)',
        'target_weight_pct': 'Target (%)',
        'deviation_pct': 'Deviation (p.p.)',
        'target_value_brl': 'Target (BRL)',
        'deviation_value_brl': 'Deviation (BRL)',
        'action': 'Action',
    })

    asset_display = asset_df.rename(columns={
        'asset': 'Asset',
        'asset_class': 'Class',
        'current_value_brl': 'Current (BRL)',
        'delta_brl': 'Delta (BRL)',
        'action': 'Action',
        'last_close_price': 'Price',
        'estimated_qty': 'Est. Qty',
    })

    ret.update({
        'valid': True,
        'class_df': class_display,
        'asset_df': asset_display,
        'summary': summary,
        'targets': targets,
        'usd_brl': info.get('usd_brl'),
    })
    return ret

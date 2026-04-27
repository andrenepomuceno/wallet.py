"""Public API for the processing package.

Re-exports the same names previously defined in `app/processing.py` so
existing imports (`from app.processing import ...`) and `unittest.mock.patch`
targets (`'app.processing.get_online_info'`) keep working.
"""
from .prices import (
    scrape_dict,
    _extract_json_object,
    guess_yfinance_ticker_with_gemini,
    get_online_info,
)
from .extracts import (
    process_b3_movimentation_request,
    process_b3_negotiation_request,
    process_avenue_extract_request,
    process_generic_extract_request,
    process_all_transactions_request,
    merge_movimentation_negotiation,
    calc_avg_price,
)
from .assets import (
    consolidate_asset_info,
    process_b3_asset_request,
    process_avenue_asset_request,
    process_generic_asset_request,
)
from .consolidate import (
    load_products,
    load_consolidate,
    consolidate_total,
    consolidate_group,
    process_consolidate_request,
)
from .history import (
    plot_price_history,
    adjust_for_splits,
    plot_history,
    process_history,
)

__all__ = [
    # prices
    'scrape_dict', '_extract_json_object', 'guess_yfinance_ticker_with_gemini',
    'get_online_info',
    # extracts
    'process_b3_movimentation_request', 'process_b3_negotiation_request',
    'process_avenue_extract_request', 'process_generic_extract_request',
    'merge_movimentation_negotiation', 'calc_avg_price',
    # assets
    'consolidate_asset_info', 'process_b3_asset_request',
    'process_avenue_asset_request', 'process_generic_asset_request',
    # consolidate
    'load_products', 'load_consolidate', 'consolidate_total',
    'consolidate_group', 'process_consolidate_request',
    # history
    'plot_price_history', 'adjust_for_splits', 'plot_history', 'process_history',
]

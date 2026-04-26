"""Routes package — importing this module registers all view functions on `app`."""
# Import order: helpers register Jinja filters; route modules attach @app.route handlers.
from . import _helpers  # noqa: F401
from . import upload  # noqa: F401
from . import transactions  # noqa: F401
from . import admin  # noqa: F401
from . import asset  # noqa: F401
from . import consolidate  # noqa: F401

# Re-exports for backwards compatibility with code that imports symbols from
# `app.routes` directly (e.g. `from app.routes import format_money`) or patches
# them in tests (e.g. `@patch('app.routes.process_history')`).
from ._helpers import format_money  # noqa: F401
from .asset import process_history  # noqa: F401

#!/usr/bin/python3

from app import app, db
from app.models import seed_default_cache_config
from app.migrate_to_transaction import migrate_legacy_to_transaction
from app.utils.scraping import rebuild_request_cache

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        migrate_legacy_to_transaction()
        seed_default_cache_config()
        rebuild_request_cache()
    app.run(debug=True, port=5100)

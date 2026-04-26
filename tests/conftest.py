"""Shared pytest fixtures.

The repo-root conftest.py sets WALLET_DATABASE_URI to a temp file before
the `app` package is imported, so importing it here is safe.
"""
import pytest


@pytest.fixture(scope='session')
def app():
    from app import app as flask_app, db
    flask_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
    )
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def db_session(app):
    from app import db
    yield db.session
    db.session.rollback()
    for table in reversed(db.metadata.sorted_tables):
        db.session.execute(table.delete())
    db.session.commit()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def request_ctx(app):
    """Push a request context so flash() works inside service-layer tests."""
    with app.test_request_context():
        yield

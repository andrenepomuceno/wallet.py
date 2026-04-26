"""Set test environment BEFORE the app package is imported."""
import os
import tempfile

_FD, _DB_PATH = tempfile.mkstemp(suffix='.db', prefix='wallet_test_')
os.close(_FD)
os.environ['WALLET_DATABASE_URI'] = f'sqlite:///{_DB_PATH}'
os.environ['WALLET_TESTING'] = '1'


def pytest_sessionfinish(session, exitstatus):
    try:
        os.remove(_DB_PATH)
    except OSError:
        pass

from unittest.mock import patch, MagicMock
import pytest

from app import db
from app.models import ApiConfig
from app.utils import serper


pytestmark = pytest.mark.usefixtures("request_ctx")


def test_search_news_no_key(db_session):
    assert serper.search_news('AAPL') == []


def test_search_news_success(db_session):
    db.session.add(ApiConfig(provider='serper', api_key='sk-test'))
    db.session.commit()

    fake_payload = {'news': [
        {'title': 'A', 'link': 'http://x', 'snippet': 's', 'source': 'src',
         'date': '1d ago'},
    ]}
    with patch('app.utils.serper.requests.post') as mock_post:
        mock_post.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value=fake_payload),
        )
        out = serper.search_news('AAPL', num=5)

    assert len(out) == 1
    assert out[0]['title'] == 'A'
    # Verify request shape
    args, kwargs = mock_post.call_args
    assert kwargs['headers']['X-API-KEY'] == 'sk-test'
    assert kwargs['json'] == {'q': 'AAPL', 'num': 5}


def test_search_news_failure(db_session):
    db.session.add(ApiConfig(provider='serper', api_key='sk-test'))
    db.session.commit()
    with patch('app.utils.serper.requests.post', side_effect=Exception('boom')):
        assert serper.search_news('AAPL') == []


def test_search_news_missing_news_key(db_session):
    db.session.add(ApiConfig(provider='serper', api_key='sk-test'))
    db.session.commit()
    with patch('app.utils.serper.requests.post') as mock_post:
        mock_post.return_value = MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={}),
        )
        assert serper.search_news('AAPL') == []

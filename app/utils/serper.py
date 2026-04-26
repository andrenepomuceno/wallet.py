"""Serper.dev API integration for news search."""
import requests
from app import app
from app.models import get_api_key


SERPER_NEWS_ENDPOINT = 'https://google.serper.dev/news'


def search_news(query, num=10):
    """Fetch recent news articles for `query` from serper.dev.

    Returns a list of dicts with keys: title, link, snippet, source, date,
    imageUrl (when available). Returns [] if no API key is configured or the
    request fails.
    """
    api_key = get_api_key('serper')
    if not api_key:
        app.logger.debug('serper: no API key configured')
        return []

    try:
        response = requests.post(
            SERPER_NEWS_ENDPOINT,
            headers={'X-API-KEY': api_key, 'Content-Type': 'application/json'},
            json={'q': query, 'num': num},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        app.logger.warning('serper.search_news failed for %r: %s', query, e)
        return []

    return data.get('news', []) or []

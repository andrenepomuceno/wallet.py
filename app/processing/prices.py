"""Price resolution: yfinance + custom scraping + Gemini ticker fallback."""
import json
import re

import requests
from flask import flash

from app import app
from app.models import get_api_key
from app.utils.parsing import is_b3_fii_ticker, is_b3_stock_ticker, brl_to_float
from app.utils.scraping import scrape_data, usd_exchange_rate, get_yfinance_data


scrape_dict = {
    "Tesouro Selic 2029": {
        'url': 'https://taxas-tesouro.com/resgatar/tesouro-selic-2029/',
        'xpath': '/html/body/div/div/div/div[2]/main/div[1]/div/div[1]/div[4]/div[2]/span',
        'class': 'Renda Fixa',
        'currency': 'BRL',
    },
    "Tesouro Selic 2031": {
        'url': 'https://taxas-tesouro.com/resgatar/tesouro-selic-2031/',
        'xpath': '/html/body/div/div/div/div[2]/main/div[1]/div/div[1]/div[4]/div[2]/span',
        'class': 'Renda Fixa',
        'currency': 'BRL',
    }
}

GEMINI_MODEL_CANDIDATES = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-2.0-flash']


def _post_gemini_generate_content(api_key, payload):
    for model in GEMINI_MODEL_CANDIDATES:
        endpoint = (
            'https://generativelanguage.googleapis.com/v1beta/models/'
            f'{model}:generateContent?key={api_key}'
        )
        try:
            response = requests.post(endpoint, json=payload, timeout=12)
            if response.status_code == 404:
                continue
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            status_code = getattr(getattr(e, 'response', None), 'status_code', None)
            if status_code == 404:
                continue
            app.logger.warning('Gemini request failed (status=%s)', status_code)
            return None
        except Exception as e:
            app.logger.warning('Gemini request failed (%s)', type(e).__name__)
            return None

    app.logger.warning('No compatible Gemini model available')
    return None


def _extract_json_object(raw_text):
    if raw_text is None:
        return None

    text = raw_text.strip()
    fence_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, flags=re.DOTALL)
    if fence_match:
        return fence_match.group(1)

    object_match = re.search(r'(\{.*\})', text, flags=re.DOTALL)
    if object_match:
        return object_match.group(1)

    return None


def guess_yfinance_ticker_with_gemini(asset_name):
    api_key = get_api_key('gemini')
    if not api_key:
        return None

    prompt = (
        'You are a finance assistant. Given an asset name or ticker, return only a JSON object '
        'with key "ticker" containing the best Yahoo Finance ticker symbol. '
        'Use .SA suffix for Brazilian equities/FIIs when applicable. '
        'If you are not confident, return {"ticker": ""}. '
        f'Input: {asset_name}'
    )

    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'temperature': 0, 'responseMimeType': 'application/json'},
    }

    try:
        response_data = _post_gemini_generate_content(api_key, payload)
        if not response_data:
            return None
        candidates = response_data.get('candidates', [])
        if len(candidates) == 0:
            return None

        parts = candidates[0].get('content', {}).get('parts', [])
        if len(parts) == 0:
            return None

        raw_text = parts[0].get('text', '')
        json_text = _extract_json_object(raw_text)
        if json_text is None:
            return None

        parsed = json.loads(json_text)
        suggested_ticker = str(parsed.get('ticker', '')).strip().upper()

        if not re.match(r'^[A-Z0-9\.\-=]{1,20}$', suggested_ticker):
            return None

        return suggested_ticker or None
    except Exception as e:
        app.logger.warning('Gemini ticker suggestion failed for %s (%s)', asset_name, type(e).__name__)
        return None


def get_online_info(ticker, asset_info=None):
    """Scrape online data for the specified asset"""
    app.logger.info('Scraping data for %s', ticker)

    if asset_info is None:
        asset_info = {}

    ticker_blacklist = ['VVAR3']
    if ticker in ticker_blacklist:
        return asset_info

    try:
        if is_b3_stock_ticker(ticker):
            yfinance_ticker = ticker + ".SA"
            online_data = get_yfinance_data(yfinance_ticker)
            asset_info.update(online_data)
            asset_info['asset_class'] = 'Equity'
            asset_info['yfinance_ticker'] = yfinance_ticker

        elif is_b3_fii_ticker(ticker):
            yfinance_ticker = ticker + ".SA"
            online_data = get_yfinance_data(yfinance_ticker)
            asset_info.update(online_data)
            asset_info['asset_class'] = 'FII'
            asset_info['yfinance_ticker'] = yfinance_ticker

        elif re.match(r'^(BTC|ETH)$', ticker):
            yfinance_ticker = ticker + "-USD"
            online_data = get_yfinance_data(yfinance_ticker)
            asset_info.update(online_data)
            rate = usd_exchange_rate('BRL')
            if rate:
                asset_info['last_close_price'] = round(rate * asset_info['last_close_price'], 2)
            asset_info['currency'] = 'BRL'
            asset_info['asset_class'] = 'Criptocurrency'
            asset_info['yfinance_ticker'] = yfinance_ticker

        elif ticker in scrape_dict:
            scrap_info = scrape_dict[ticker]  # TODO scrap past data
            scraped = scrape_data(scrap_info['url'], scrap_info['xpath'])
            asset_info['last_close_price'] = brl_to_float(scraped[0])
            asset_info['asset_class'] = scrap_info['class']
            asset_info['currency'] = scrap_info['currency']

        else:
            try:
                online_data = get_yfinance_data(ticker)
                asset_info.update(online_data)
                asset_info['asset_class'] = asset_info['asset_class'].capitalize()
                asset_info['yfinance_ticker'] = ticker
            except Exception:
                suggested_ticker = guess_yfinance_ticker_with_gemini(ticker)
                if suggested_ticker:
                    app.logger.info('Trying Gemini suggested ticker %s for %s', suggested_ticker, ticker)
                    online_data = get_yfinance_data(suggested_ticker)
                    asset_info.update(online_data)
                    asset_info['asset_class'] = asset_info['asset_class'].capitalize()
                    asset_info['yfinance_ticker'] = suggested_ticker
                else:
                    raise

    except Exception as e:
        flash(f'Failed to get online data for {ticker}.')
        app.logger.error('Exception: %s', e)

    return asset_info

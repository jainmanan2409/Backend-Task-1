from django.shortcuts import render
import json
import requests
from django.utils.safestring import mark_safe


def app(request):

    # ======== FETCH CHART DATA FROM API (BACKEND) =========
    url = "https://www.alphavantage.co/query?function=ALL_COMMODITIES&interval=monthly&apikey=demo"
    response = requests.get(url)
    
    api_json = response.json()

    # Extract API data safely
    data_list = api_json.get("data", [])

    # Convert API data → labels (dates) & series (values)
    labels = [item["date"] for item in data_list]
    series = [float(item["value"]) for item in data_list]
# app/views.py
import os
import json
import logging
from datetime import datetime

import requests
from django.shortcuts import render
from django.utils.safestring import mark_safe
from django.conf import settings

logger = logging.getLogger(__name__)

# Put your API key in env var ALPHAVANTAGE_KEY or Django settings,
# otherwise it will use 'demo' (AlphaVantage demo key which is rate-limited).
ALPHA_KEY = os.environ.get("ALPHAVANTAGE_KEY", getattr(settings, "ALPHAVANTAGE_KEY", "demo"))
ALPHA_URL = "https://www.alphavantage.co/query?function=ALL_COMMODITIES&interval=monthly&apikey={key}".format(key=ALPHA_KEY)

def fetch_chart_data_from_api(url=ALPHA_URL, timeout=8):
    """
    Fetches the JSON from the API and returns a list of (date_str, float_value) tuples.
    Skips entries where value can't be parsed to float (e.g. '.' or '').
    """
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
        # expected payload['data'] to be a list of {"date": "...", "value":"..."}
        data_list = payload.get("data") or []
        parsed = []
        for item in data_list:
            date_str = item.get("date") or item.get("timestamp") or item.get("datetime")
            value_raw = item.get("value", "")
            if not date_str:
                continue
            # normalize value and try convert to float
            if isinstance(value_raw, str):
                v = value_raw.strip().replace(",", "")
            else:
                v = value_raw
            try:
                value_f = float(v)
            except (ValueError, TypeError):
                # skip invalid entries like '.' or ''
                continue
            parsed.append((date_str, value_f))
        return parsed
    except Exception as e:
        logger.exception("Error fetching/parsing chart data from API: %s", e)
        return []

def prepare_chart_payload(parsed_date_values):
    """
    Accepts list of (date_str, float_value) pairs.
    Sorts by date ascending and returns dict with labels and series lists.
    """
    def parse_date(s):
        # try common ISO formats
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m", "%Y/%m/%d"):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue
        # last resort, try slicing
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None

    # convert to (dt_obj, value, original_date_str)
    rows = []
    for date_str, val in parsed_date_values:
        dt = parse_date(date_str)
        rows.append((dt, val, date_str))

    # sort by dt; None dates go to end
    rows.sort(key=lambda r: (r[0] is None, r[0]))

    labels = [r[2] for r in rows]
    series = [r[1] for r in rows]
    return {"labels": labels, "series": series}

def app(request):
    # Fetch backend chart data
    parsed = fetch_chart_data_from_api()

    if parsed:
        chart_data = prepare_chart_payload(parsed)
    else:
        # Fallback sample data if API fails / no data
        labels = [
            "2024-12-01","2025-01-01","2025-02-01","2025-03-01",
            "2025-04-01","2025-05-01","2025-06-01"
        ]
        series = [166.63436509257, 172.779787344212, 172.042952296535, 167.42371963722, 162.488984129654, 160.525599378657, 165.786567246984]
        chart_data = {"labels": labels, "series": series}

    # Users table data (you said you already have this; kept sample rows)
    users = [
        {"broker":"Zerodha (DU000004)","active_positions":1,"available_capital":"₹ 1.54 Cr","total_deployed":3,"active_strategies":1,"status":"Active","current_pl":"₹ 50.02 K","required_capital":"₹ 50.02 K"},
        {"broker":"Angel One (MNBn1026)","active_positions":2,"available_capital":"₹ 2.50 K","total_deployed":2,"active_strategies":2,"status":"Active","current_pl":"₹ 60.02 K","required_capital":"₹ 60.02 K"},
        {"broker":"Finvasia (FA189009)","active_positions":0,"available_capital":"₹ 50.02 K","total_deployed":0,"active_strategies":0,"status":"Pending","current_pl":"₹ 0.00","required_capital":"₹ 0.00"},
    ]

    context = {
        "chart_data_json": mark_safe(json.dumps(chart_data)),
        "users": users,
    }
    # IMPORTANT: pass context to template
    return render(request, 'index.html', context)

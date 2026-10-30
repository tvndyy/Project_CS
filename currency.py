"""
currency.py - Exchange Cost Planner

Role: "Berechnung & Wechselkurse" (exchange rates)

Gets current exchange rates from the free Frankfurter API
(https://frankfurter.dev, rates of the European Central Bank, no API key)
and converts CHF amounts into the local currency of the exchange city.

If the API cannot be reached, we use the last rates that were saved in
data/last_rates.json, so the app keeps working (with a note that the
rates are not live).

How to use it in the Streamlit app (see demo_app.py):

    from currency import get_exchange_rates, convert_from_chf
    rates, source = get_exchange_rates(["EUR", "USD"])
    if rates is not None:
        st.write(convert_from_chf(1000, rates["EUR"]), "EUR")
"""

# AI assistance:
# Initial implementation developed with assistance from Claude.
# Students reviewed, tested, adapted and must document the exact use
# according to HSG course requirements.

import json
import os

import requests

API_URL = "https://api.frankfurter.dev/v1"

PROJECT_FOLDER = os.path.dirname(os.path.abspath(__file__))
SAVED_RATES_PATH = os.path.join(PROJECT_FOLDER, "data", "last_rates.json")


# ---------------------------------------------------------------------------
# Saving and loading rates (file handling)
# ---------------------------------------------------------------------------
def save_rates(rates, rates_date):
    """Write the rates into a JSON file, so we can use them if the API is down."""
    os.makedirs(os.path.dirname(SAVED_RATES_PATH), exist_ok=True)
    with open(SAVED_RATES_PATH, "w") as file:
        json.dump({"date": rates_date, "rates": rates}, file, indent=2)


def load_saved_rates():
    """Read the saved rates. Returns (rates, date) or (None, None) if there is no file."""
    if not os.path.exists(SAVED_RATES_PATH):
        return None, None
    try:
        with open(SAVED_RATES_PATH) as file:
            saved = json.load(file)
        return saved["rates"], saved["date"]
    except Exception:
        # File is damaged or has the wrong format
        return None, None


# ---------------------------------------------------------------------------
# API requests
# ---------------------------------------------------------------------------
def get_exchange_rates(currencies):
    """Get today's value of 1 CHF in each of the given currencies.

    currencies - list of currency codes, e.g. ["EUR", "USD", "SGD"]

    How it works:
    1. Our app sends an HTTP GET request to the Frankfurter server.
    2. The server answers with JSON, e.g.
       {"amount": 1.0, "base": "CHF", "date": "2026-10-30", "rates": {"EUR": 1.07, "USD": 1.25}}
    3. response.json() turns this text into a Python dictionary.

    Returns two values: (rates, source)
      rates  - dictionary like {"CHF": 1.0, "EUR": 1.07, ...} or None if no rates are available
      source - text for the app, e.g. "live (ECB, 2026-10-30)" or "saved rates from 2026-10-28"
    """
    # We only need to ask for currencies other than CHF
    other_currencies = []
    for currency in currencies:
        if currency != "CHF" and currency not in other_currencies:
            other_currencies.append(currency)

    if len(other_currencies) == 0:
        return {"CHF": 1.0}, "no conversion needed"

    try:
        response = requests.get(
            API_URL + "/latest",
            params={"base": "CHF", "symbols": ",".join(other_currencies)},
            timeout=5,
        )
        response.raise_for_status()  # error if the status code is 4xx or 5xx
        data = response.json()

        rates = data["rates"]
        rates["CHF"] = 1.0
        save_rates(rates, data["date"])
        return rates, f"live (ECB, {data['date']})"

    except Exception:
        # No internet, server down, or unknown currency -> try the saved rates
        saved_rates, saved_date = load_saved_rates()
        if saved_rates is None:
            return None, "not available"

        # Only use the saved rates if they contain all currencies we need
        for currency in other_currencies:
            if currency not in saved_rates:
                return None, "not available"
        return saved_rates, f"saved rates from {saved_date} (API not reachable)"


def get_supported_currencies():
    """Ask the API which currencies it knows.

    Returns a dictionary like {"EUR": "Euro", "USD": "United States Dollar", ...}
    or None if the request fails. Useful to check our city list once.
    """
    try:
        response = requests.get(API_URL + "/currencies", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def find_unsupported_currencies(currencies):
    """Return the currencies from our list that the API does NOT offer.

    For these cities the app can only show CHF. Returns None if the
    API cannot be reached.
    """
    supported = get_supported_currencies()
    if supported is None:
        return None

    unsupported = []
    for currency in currencies:
        if currency != "CHF" and currency not in supported:
            unsupported.append(currency)
    return unsupported


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------
def convert_from_chf(amount_chf, rate):
    """Convert an amount from CHF into the local currency.

    rate = value of 1 CHF in the local currency (from get_exchange_rates)
    Example: convert_from_chf(1000, 1.07) -> 1070 (EUR)
    """
    return round(amount_chf * rate)


def convert_table_from_chf(table, rate, currency):
    """Add local-currency columns to the cost table from calculation.costs_to_table()."""
    converted = table.copy()
    converted[currency.lower() + "_total"] = (converted["chf_total"] * rate).round(0)
    return converted


# Run "python currency.py" to check which of our currencies the API supports
if __name__ == "__main__":
    # Put the currencies of all cities in our database here
    our_currencies = ["EUR", "USD", "GBP", "SGD", "AUD", "CAD", "JPY", "KRW", "DKK", "SEK", "NOK", "HKD",
                      "CNY", "MXN", "BRL", "ARS", "CLP", "TWD", "AED"]

    unsupported = find_unsupported_currencies(our_currencies)
    if unsupported is None:
        print("The API could not be reached. Check your internet connection.")
    elif len(unsupported) == 0:
        print("All currencies are supported.")
    else:
        print("NOT supported (show only CHF for these cities):", unsupported)

    rates, source = get_exchange_rates(["EUR", "USD"])
    print("Example rates:", rates, "-", source)

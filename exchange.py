import requests
BASE_URL = "https://open.er-api.com/v6/latest/"

def convert_currency(amount, from_currency, to_currency="TWD"):
    url = BASE_URL + from_currency.upper()
    response = requests.get(url)
    data = response.json()
    rate = data["rates"].get(to_currency.upper())

    if rate is None:
        return None
    converted = amount * rate
    return round(converted, 2)

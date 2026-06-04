import requests

from config import SHEETS_WEBHOOK_URL


def call_sheets_api(data):
    try:
        response = requests.post(
            SHEETS_WEBHOOK_URL,
            json=data,
            timeout=10
        )
        return response.json()

    except Exception as e:
        print("Google Sheets API error:", e)
        return None


# -------------------------
# Taiwan Price DB
# -------------------------

def find_taiwan_price_from_sheet(item_name):
    result = call_sheets_api({
        "action": "find_price",
        "item": item_name
    })

    if result and result.get("found"):
        return float(result.get("taiwan_price"))

    return None


def list_taiwan_prices_from_sheet():
    result = call_sheets_api({
        "action": "list_prices"
    })

    if result and result.get("success"):
        return result.get("items", [])

    return []


def save_taiwan_price_to_sheet(item_name, taiwan_price):
    return call_sheets_api({
        "action": "save_price",
        "item": item_name.lower().strip(),
        "taiwan_price": taiwan_price
    })


def update_taiwan_price_in_sheet(item_name, taiwan_price):
    return call_sheets_api({
        "action": "update_price",
        "item": item_name.lower().strip(),
        "taiwan_price": taiwan_price
    })


def delete_taiwan_price_from_sheet(item_name):
    return call_sheets_api({
        "action": "delete_price",
        "item": item_name.lower().strip()
    })


def log_price_check_to_sheet(result, raw_message):
    if not SHEETS_WEBHOOK_URL:
        return

    if "error" in result:
        return

    return call_sheets_api({
        "action": "log",
        "item": result["item"],
        "currency": result["currency"],
        "original_price": result["original_price"],
        "converted_twd": result["converted_twd"],
        "taiwan_price": result["taiwan_price"],
        "difference_percent": result["difference_percent"],
        "decision": result["decision"],
        "raw_message": raw_message
    })


# -------------------------
# Trips / Buckets
# -------------------------

def get_active_trip(user_key):
    result = call_sheets_api({
        "action": "get_active_trip",
        "user_key": user_key
    })

    if result and result.get("success"):
        return result.get("trip_name", "Default")

    return "Default"


def set_active_trip(user_key, trip_name):
    return call_sheets_api({
        "action": "set_active_trip",
        "user_key": user_key,
        "trip_name": trip_name
    })


def list_trips(user_key):
    result = call_sheets_api({
        "action": "list_trips",
        "user_key": user_key
    })

    if result and result.get("success"):
        return result.get("trips", [])

    return []


def delete_trips(user_key, trip_names):
    return call_sheets_api({
        "action": "delete_trips",
        "user_key": user_key,
        "trip_names": trip_names
    })


# -------------------------
# Expenses
# -------------------------

def log_expense(user_key, trip_name, platform, item, currency, original_price, converted_twd):
    return call_sheets_api({
        "action": "log_expense",
        "user_key": user_key,
        "trip_name": trip_name,
        "platform": platform,
        "item": item,
        "currency": currency,
        "original_price": original_price,
        "converted_twd": converted_twd
    })


def list_expenses(user_key, trip_name):
    result = call_sheets_api({
        "action": "list_expenses",
        "user_key": user_key,
        "trip_name": trip_name
    })

    if result and result.get("success"):
        return result.get("expenses", [])

    return []


def recent_expenses(user_key, trip_name, limit=10):
    result = call_sheets_api({
        "action": "recent_expenses",
        "user_key": user_key,
        "trip_name": trip_name,
        "limit": limit
    })

    if result and result.get("success"):
        return result.get("expenses", [])

    return []


def delete_expense(user_key, row_number):
    return call_sheets_api({
        "action": "delete_expense",
        "user_key": user_key,
        "row_number": row_number
    })


def calculate_total_expenses(user_key, trip_name):
    expenses = list_expenses(user_key, trip_name)
    total = 0

    for expense in expenses:
        total += float(expense.get("converted_twd", 0))

    return total, expenses


# -------------------------
# Budget
# -------------------------

def set_budget(user_key, trip_name, budget_twd):
    return call_sheets_api({
        "action": "set_budget",
        "user_key": user_key,
        "trip_name": trip_name,
        "budget_twd": budget_twd
    })


def get_budget(user_key, trip_name):
    result = call_sheets_api({
        "action": "get_budget",
        "user_key": user_key,
        "trip_name": trip_name
    })

    if result and result.get("found"):
        return float(result.get("budget_twd"))

    return None

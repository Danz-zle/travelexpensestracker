import os
import re
import requests
from flask import Flask, request, jsonify

from evaluator import evaluate_purchase

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SHEETS_WEBHOOK_URL = os.environ.get("SHEETS_WEBHOOK_URL")

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

SUPPORTED_CURRENCIES = {
    "JPY": ["jpy", "yen", "¥"],
    "USD": ["usd", "$"],
    "EUR": ["eur", "€"],
    "KRW": ["krw", "won"],
    "HKD": ["hkd"],
    "SGD": ["sgd"]
}


def detect_currency(text):
    lower_text = text.lower()

    for currency_code, keywords in SUPPORTED_CURRENCIES.items():
        for keyword in keywords:
            if keyword in lower_text:
                return currency_code

    return "JPY"


def extract_price(text):
    numbers = re.findall(r"\d+", text)

    if not numbers:
        return None

    return int(numbers[-1])


def clean_item_name(text):
    cleaned = text

    for keywords in SUPPORTED_CURRENCIES.values():
        for keyword in keywords:
            cleaned = cleaned.replace(keyword, "")
            cleaned = cleaned.replace(keyword.upper(), "")

    cleaned = re.sub(r"\d+", "", cleaned)

    return cleaned.strip()


def parse_message(text):
    currency = detect_currency(text)
    price = extract_price(text)
    item_name = clean_item_name(text)

    if price is None or item_name == "":
        return None, None, None

    return item_name, price, currency


def send_message(chat_id, text):
    url = BASE_URL + "/sendMessage"

    data = {
        "chat_id": chat_id,
        "text": text
    }

    requests.post(url, data=data)


def log_to_google_sheets(result, raw_message):
    if not SHEETS_WEBHOOK_URL:
        return

    if "error" in result:
        return

    data = {
        "item": result["item"],
        "currency": result["currency"],
        "original_price": result["original_price"],
        "converted_twd": result["converted_twd"],
        "taiwan_price": result["taiwan_price"],
        "difference_percent": result["difference_percent"],
        "decision": result["decision"],
        "raw_message": raw_message
    }

    try:
        requests.post(SHEETS_WEBHOOK_URL, json=data, timeout=10)
    except Exception as e:
        print("Google Sheets log error:", e)


def format_result(result):
    if "error" in result:
        return f"❌ {result['error']}"

    return (
        f"📦 Item: {result['item']}\n"
        f"💰 Original: {result['currency']} {result['original_price']}\n"
        f"💱 Converted: NT${result['converted_twd']}\n"
        f"🇹🇼 Taiwan Price: NT${result['taiwan_price']}\n"
        f"📊 Difference: {result['difference_percent']}%\n"
        f"🧠 Decision: {result['decision']}"
    )


@app.route("/", methods=["GET"])
def home():
    return "Travel Expense Tracker webhook is running."


@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    update = request.get_json()

    message = update.get("message")

    if not message:
        return jsonify({"ok": True})

    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    item_name, price, currency = parse_message(text)

    if item_name is None:
        send_message(
            chat_id,
            "Example:\nUniqlo Jacket 5999 JPY\nNike Shoes USD 120"
        )
        return jsonify({"ok": True})

    result = evaluate_purchase(item_name, price, currency)

    log_to_google_sheets(result, text)

    send_message(chat_id, format_result(result))

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

import os
import re
import requests
from flask import Flask, request, jsonify

from evaluator import evaluate_purchase

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SHEETS_WEBHOOK_URL = os.environ.get("SHEETS_WEBHOOK_URL")

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

LAST_PENDING_ITEM = {}

SUPPORTED_CURRENCIES = {
    "JPY": ["jpy", "yen", "¥", "円", "日幣"],
    "USD": ["usd", "$", "usd$", "us$", "美金"],
    "EUR": ["eur", "€", "euro"],
    "KRW": ["krw", "won", "₩", "韓元"],
    "HKD": ["hkd", "hk$", "港幣"],
    "SGD": ["sgd", "s$", "新幣"],
    "MYR": ["myr", "rm", "ringgit", "馬幣"],
    "THB": ["thb", "baht", "฿", "泰銖"],
    "VND": ["vnd", "dong", "₫", "越盾"],
    "PHP": ["php", "peso", "₱", "披索"],
    "KHR": ["khr", "riel", "៛", "柬幣"]
}


def detect_currency(text):
    lower_text = text.lower()

    for currency_code, keywords in SUPPORTED_CURRENCIES.items():
        for keyword in keywords:
            if keyword.lower() in lower_text:
                return currency_code

    return "JPY"


def remove_currency_words(text):
    cleaned = text

    for keywords in SUPPORTED_CURRENCIES.values():
        for keyword in keywords:
            if keyword in ["¥", "$", "€", "₩"]:
                cleaned = cleaned.replace(keyword, "")
            else:
                cleaned = re.sub(
                    r"\b" + re.escape(keyword) + r"\b",
                    "",
                    cleaned,
                    flags=re.IGNORECASE
                )

    return cleaned


def extract_last_number(text):
    matches = list(re.finditer(r"\d+", text))

    if not matches:
        return None, text

    last_match = matches[-1]
    price = int(last_match.group())

    cleaned_text = (
        text[:last_match.start()] +
        text[last_match.end():]
    )

    return price, cleaned_text


def normalize_spaces(text):
    return re.sub(r"\s+", " ", text).strip()


def parse_message(text):
    currency = detect_currency(text)

    cleaned = remove_currency_words(text)

    price, item_text = extract_last_number(cleaned)

    item_name = normalize_spaces(item_text)

    if price is None or item_name == "":
        return None, None, None

    return item_name, price, currency


def is_twprice_command(text):
    return text.lower().startswith("twprice")


def parse_twprice(text):
    numbers = re.findall(r"\d+", text)

    if not numbers:
        return None

    return int(numbers[-1])


def is_addprice_command(text):
    return text.lower().startswith("addprice")


def parse_addprice_line(line):
    line = line.strip()

    if not line:
        return None, None

    line = line.replace(",", " ")

    price, item_text = extract_last_number(line)

    item_name = normalize_spaces(item_text)

    if price is None or item_name == "":
        return None, None

    return item_name, price


def parse_addprice(text):
    cleaned = re.sub(
        r"(?i)^addprice",
        "",
        text
    ).strip()

    if not cleaned:
        return []

    lines = cleaned.splitlines()

    results = []

    for line in lines:
        item_name, taiwan_price = parse_addprice_line(line)

        if item_name and taiwan_price:
            results.append({
                "item": item_name,
                "taiwan_price": taiwan_price
            })

    return results


def send_message(chat_id, text):
    url = BASE_URL + "/sendMessage"

    data = {
        "chat_id": chat_id,
        "text": text
    }

    requests.post(url, data=data)


def find_taiwan_price_from_sheet(item_name):
    data = {
        "action": "find_price",
        "item": item_name
    }

    try:
        response = requests.post(
            SHEETS_WEBHOOK_URL,
            json=data,
            timeout=10
        )

        result = response.json()

        if result.get("found"):
            return int(result.get("taiwan_price"))

        return None

    except Exception as e:
        print("Find Taiwan price error:", e)
        return None


def save_taiwan_price_to_sheet(item_name, taiwan_price):
    data = {
        "action": "save_price",
        "item": item_name.lower().strip(),
        "taiwan_price": taiwan_price
    }

    try:
        response = requests.post(
            SHEETS_WEBHOOK_URL,
            json=data,
            timeout=10
        )

        return response.json()

    except Exception as e:
        print("Save Taiwan price error:", e)
        return None


def log_to_google_sheets(result, raw_message):

    if not SHEETS_WEBHOOK_URL:
        return

    if "error" in result:
        return

    data = {
        "action": "log",
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
        requests.post(
            SHEETS_WEBHOOK_URL,
            json=data,
            timeout=10
        )

    except Exception as e:
        print("Google Sheets log error:", e)


def format_result(result):

    if "error" in result:
        return f"❌ {result['error']}"

    converted = result["converted_twd"]
    taiwan_price = result["taiwan_price"]

    difference_amount = converted - taiwan_price
    abs_difference = abs(difference_amount)

    decision = result["decision"]

    if decision == "BUY":

        title = "✅ BUY"

        summary = (
            f"You save about NT${abs_difference} vs Taiwan."
        )

    elif decision == "NORMAL":

        title = "🟡 NORMAL"

        summary = (
            "Price is close to Taiwan. "
            "Buy only if you really want it."
        )

    else:

        title = "❌ DON'T BUY"

        summary = (
            f"This is about NT${abs_difference} "
            f"more expensive than Taiwan."
        )

    return (
        f"{title}\n\n"
        f"📦 Item: {result['item']}\n"
        f"💰 Original: {result['currency']} "
        f"{result['original_price']}\n"
        f"💱 Converted: NT${converted}\n"
        f"🇹🇼 Taiwan Price: NT${taiwan_price}\n"
        f"📊 Difference: "
        f"{result['difference_percent']}%\n\n"
        f"{summary}"
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

    if is_addprice_command(text):

        items = parse_addprice(text)

        if not items:

            send_message(
                chat_id,
                "Example:\n"
                "ADDPRICE Sony XM6 10990\n\n"
                "Or bulk add:\n"
                "ADDPRICE\n"
                "AirPods Pro, 7490\n"
                "Sony XM6, 10990\n"
                "Samsung smart watch420, 3500"
            )

            return jsonify({"ok": True})

        saved_lines = []

        for item in items:
            save_taiwan_price_to_sheet(
                item["item"],
                item["taiwan_price"]
            )

            saved_lines.append(
                f"📦 {item['item']} → NT${item['taiwan_price']}"
            )

        send_message(
            chat_id,
            "✅ Taiwan price added.\n\n" +
            "\n".join(saved_lines)
        )

        return jsonify({"ok": True})

    if is_twprice_command(text):

        taiwan_price = parse_twprice(text)

        pending_item = LAST_PENDING_ITEM.get(chat_id)

        if taiwan_price is None:
            send_message(
                chat_id,
                "Please use:\nTWPRICE 1490"
            )
            return jsonify({"ok": True})

        if not pending_item:
            send_message(
                chat_id,
                "No pending item found. Please search an item first."
            )
            return jsonify({"ok": True})

        save_taiwan_price_to_sheet(
            pending_item,
            taiwan_price
        )

        send_message(
            chat_id,
            f"✅ Taiwan price saved.\n\n"
            f"📦 Item: {pending_item}\n"
            f"🇹🇼 Taiwan Price: NT${taiwan_price}\n\n"
            f"Now send the item again to evaluate it."
        )

        return jsonify({"ok": True})

    item_name, price, currency = parse_message(text)

    if item_name is None:

        send_message(
            chat_id,
            "Example:\n"
            "Uniqlo Jacket 5999 JPY\n"
            "Nike Shoes USD 120\n\n"
            "Or preload Taiwan price:\n"
            "ADDPRICE Sony XM6 10990"
        )

        return jsonify({"ok": True})

    taiwan_price = find_taiwan_price_from_sheet(item_name)

    if taiwan_price is None:

        LAST_PENDING_ITEM[chat_id] = item_name

        send_message(
            chat_id,
            f"❌ Taiwan price not found.\n\n"
            f"📦 Item: {item_name}\n\n"
            f"Reply with:\n"
            f"TWPRICE 1490\n\n"
            f"or preload directly:\n"
            f"ADDPRICE {item_name} 1490"
        )

        return jsonify({"ok": True})

    result = evaluate_purchase(
        item_name,
        price,
        currency,
        taiwan_price
    )

    log_to_google_sheets(result, text)

    send_message(
        chat_id,
        format_result(result)
    )

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000
    )

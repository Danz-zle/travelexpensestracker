import os
import re
import hmac
import base64
import hashlib
import requests
from flask import Flask, request, jsonify

from evaluator import evaluate_purchase
from exchange import convert_currency

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SHEETS_WEBHOOK_URL = os.environ.get("SHEETS_WEBHOOK_URL")

LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")

TELEGRAM_BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

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
            if keyword in ["¥", "$", "€", "₩", "฿", "₫", "₱", "៛"]:
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
    matches = list(re.finditer(r"\d+(?:\.\d+)?", text))
    if not matches:
        return None, text

    last_match = matches[-1]
    raw_number = last_match.group()

    price = float(raw_number) if "." in raw_number else int(raw_number)

    cleaned_text = text[:last_match.start()] + text[last_match.end():]
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


def is_help_command(text):
    return text.lower().strip() in ["help", "/help", "menu", "指令", "幫助"]


def is_status_command(text):
    return text.lower().strip() in ["status", "狀態"]


def is_listprice_command(text):
    return text.lower().strip() in ["listprice", "list", "prices", "清單"]


def is_rate_command(text):
    return text.lower().startswith("rate")


def is_twprice_command(text):
    return text.lower().startswith("twprice")


def is_addprice_command(text):
    return text.lower().startswith("addprice")


def is_updateprice_command(text):
    return text.lower().startswith("updateprice")


def is_deleteprice_command(text):
    return text.lower().startswith("deleteprice")


def parse_twprice(text):
    numbers = re.findall(r"\d+(?:\.\d+)?", text)
    if not numbers:
        return None

    value = numbers[-1]
    return float(value) if "." in value else int(value)


def parse_rate_command(text):
    parts = text.strip().split()
    if len(parts) < 2:
        return None

    target = parts[1].upper()
    if target not in SUPPORTED_CURRENCIES:
        return None

    return target


def parse_price_line(line):
    line = line.strip()
    if not line:
        return None, None

    line = line.replace(",", " ")
    price, item_text = extract_last_number(line)
    item_name = normalize_spaces(item_text)

    if price is None or item_name == "":
        return None, None

    return item_name, price


def parse_items_with_prices(text, command):
    cleaned = re.sub(
        r"(?i)^" + re.escape(command),
        "",
        text
    ).strip()

    if not cleaned:
        return []

    results = []

    for line in cleaned.splitlines():
        item_name, taiwan_price = parse_price_line(line)

        if item_name and taiwan_price:
            results.append({
                "item": item_name,
                "taiwan_price": taiwan_price
            })

    return results


def parse_delete_items(text):
    cleaned = re.sub(r"(?i)^deleteprice", "", text).strip()

    if not cleaned:
        return []

    results = []

    for line in cleaned.splitlines():
        item_name = normalize_spaces(line.replace(",", " "))
        if item_name:
            results.append(item_name)

    return results


def send_telegram_message(chat_id, text):
    url = TELEGRAM_BASE_URL + "/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text})


def send_line_message(reply_token, text):
    url = "https://api.line.me/v2/bot/message/reply"

    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}]
    }

    requests.post(url, headers=headers, json=data)


def call_sheets_api(data):
    try:
        response = requests.post(SHEETS_WEBHOOK_URL, json=data, timeout=10)
        return response.json()
    except Exception as e:
        print("Google Sheets API error:", e)
        return None


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


def format_money(value):
    if isinstance(value, float) and not value.is_integer():
        return round(value, 2)
    return int(value)


def log_to_google_sheets(result, raw_message):
    if not SHEETS_WEBHOOK_URL:
        return

    if "error" in result:
        return

    call_sheets_api({
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
        summary = f"You save about NT${format_money(abs_difference)} vs Taiwan."
    elif decision == "NORMAL":
        title = "🟡 NORMAL"
        summary = "Price is close to Taiwan. Buy only if you really want it."
    else:
        title = "❌ DON'T BUY"
        summary = f"This is about NT${format_money(abs_difference)} more expensive than Taiwan."

    return (
        f"{title}\n\n"
        f"📦 Item: {result['item']}\n"
        f"💰 Original: {result['currency']} {format_money(result['original_price'])}\n"
        f"💱 Converted: NT${format_money(converted)}\n"
        f"🇹🇼 Taiwan Price: NT${format_money(taiwan_price)}\n"
        f"📊 Difference: {result['difference_percent']}%\n\n"
        f"{summary}"
    )


def format_missing_price_message(item_name, price, currency, converted_twd):
    return (
        f"❌ Taiwan price not found.\n\n"
        f"📦 Item: {item_name}\n"
        f"💰 Original: {currency} {format_money(price)}\n"
        f"💱 Converted: NT${format_money(converted_twd)}\n\n"
        f"Database has no Taiwan reference price yet, so I cannot judge BUY / DON'T BUY.\n\n"
        f"Next actions:\n\n"
        f"➕ Save Taiwan price:\n"
        f"ADDPRICE {item_name} 999\n\n"
        f"⚡ Quick save current item:\n"
        f"TWPRICE 999\n\n"
        f"💱 Check currency rate:\n"
        f"RATE {currency}\n\n"
        f"📖 Help:\n"
        f"HELP"
    )


def handle_help():
    return (
        "📖 Travel Expense Tracker Commands\n\n"
        "🔍 Check overseas price:\n"
        "AirPods Pro USD 199\n"
        "GU 黑皮夾克 Yen 23999\n"
        "Test item 59.9 MYR\n\n"
        "➕ Add Taiwan price:\n"
        "ADDPRICE AirPods Pro 7490\n\n"
        "➕ Bulk add:\n"
        "ADDPRICE\n"
        "AirPods Pro, 7490\n"
        "Sony XM6, 10990\n"
        "GU 黑皮夾克, 4500\n\n"
        "🔄 Update Taiwan price:\n"
        "UPDATEPRICE AirPods Pro 6990\n\n"
        "🗑️ Delete Taiwan price:\n"
        "DELETEPRICE AirPods Pro\n\n"
        "📋 List all Taiwan prices:\n"
        "LISTPRICE\n\n"
        "💱 Currency reference:\n"
        "RATE JPY\n"
        "RATE USD\n"
        "RATE MYR\n\n"
        "📊 Bot/database status:\n"
        "STATUS"
    )


def handle_status():
    items = list_taiwan_prices_from_sheet()
    item_count = len(items)

    supported = ", ".join(SUPPORTED_CURRENCIES.keys())

    return (
        "📊 Travel Expense Tracker Status\n\n"
        f"Database items: {item_count}\n\n"
        "Platforms:\n"
        "✅ Telegram\n"
        "✅ LINE\n\n"
        "Supported currencies:\n"
        f"{supported}\n\n"
        "Main commands:\n"
        "HELP\n"
        "LISTPRICE\n"
        "RATE JPY\n"
        "ADDPRICE item price\n"
        "UPDATEPRICE item price\n"
        "DELETEPRICE item"
    )


def handle_listprice():
    items = list_taiwan_prices_from_sheet()

    if not items:
        return "📋 TaiwanPrices is empty."

    lines = []

    for index, item in enumerate(items, start=1):
        item_name = item.get("item", "")
        taiwan_price = item.get("taiwan_price", "")

        lines.append(
            f"{index}. {item_name} → NT${format_money(float(taiwan_price))}"
        )

    message = "📋 Taiwan Price Database\n\n" + "\n".join(lines)

    if len(message) > 4500:
        message = message[:4400] + "\n\n...list too long, please check Google Sheet."

    return message


def handle_rate(text):
    target_currency = parse_rate_command(text)

    if not target_currency:
        return (
            "Please use:\n"
            "RATE JPY\n"
            "RATE USD\n"
            "RATE MYR\n\n"
            "Supported:\n"
            "JPY, USD, EUR, KRW, HKD, SGD, MYR, THB, VND, PHP, KHR"
        )

    one_twd_to_target = convert_currency(1, "TWD", target_currency)
    thousand_target_to_twd = convert_currency(1000, target_currency, "TWD")

    if one_twd_to_target is None or thousand_target_to_twd is None:
        return "❌ Currency rate lookup failed."

    return (
        f"💱 Current Rate Reference\n\n"
        f"NT$1 ≈ {target_currency} {format_money(one_twd_to_target)}\n"
        f"{target_currency} 1000 ≈ NT${format_money(thousand_target_to_twd)}"
    )


def handle_addprice(text):
    items = parse_items_with_prices(text, "addprice")

    if not items:
        return (
            "Example:\n"
            "ADDPRICE Sony XM6 10990\n\n"
            "Or bulk add:\n"
            "ADDPRICE\n"
            "AirPods Pro, 7490\n"
            "Sony XM6, 10990\n"
            "Samsung smart watch420, 3500"
        )

    saved_lines = []

    for item in items:
        save_taiwan_price_to_sheet(item["item"], item["taiwan_price"])
        saved_lines.append(
            f"📦 {item['item']} → NT${format_money(item['taiwan_price'])}"
        )

    return "✅ Taiwan price added.\n\n" + "\n".join(saved_lines)


def handle_updateprice(text):
    items = parse_items_with_prices(text, "updateprice")

    if not items:
        return (
            "Example:\n"
            "UPDATEPRICE Sony XM6 9990\n\n"
            "Or bulk update:\n"
            "UPDATEPRICE\n"
            "AirPods Pro, 6990\n"
            "Sony XM6, 9990"
        )

    updated_lines = []

    for item in items:
        result = update_taiwan_price_in_sheet(item["item"], item["taiwan_price"])

        status = "updated" if result and result.get("updated_existing") else "added"

        updated_lines.append(
            f"📦 {item['item']} → NT${format_money(item['taiwan_price'])} ({status})"
        )

    return "✅ Taiwan price updated.\n\n" + "\n".join(updated_lines)


def handle_deleteprice(text):
    items = parse_delete_items(text)

    if not items:
        return (
            "Example:\n"
            "DELETEPRICE Sony XM6\n\n"
            "Or bulk delete:\n"
            "DELETEPRICE\n"
            "AirPods Pro\n"
            "Sony XM6"
        )

    deleted_lines = []

    for item_name in items:
        result = delete_taiwan_price_from_sheet(item_name)
        deleted_count = result.get("deleted_count", 0) if result else 0

        if deleted_count > 0:
            deleted_lines.append(f"🗑️ {item_name} deleted ({deleted_count})")
        else:
            deleted_lines.append(f"⚠️ {item_name} not found")

    return "✅ Delete result:\n\n" + "\n".join(deleted_lines)


def handle_text_message(user_key, text):
    if is_help_command(text):
        return handle_help()

    if is_status_command(text):
        return handle_status()

    if is_listprice_command(text):
        return handle_listprice()

    if is_rate_command(text):
        return handle_rate(text)

    if is_addprice_command(text):
        return handle_addprice(text)

    if is_updateprice_command(text):
        return handle_updateprice(text)

    if is_deleteprice_command(text):
        return handle_deleteprice(text)

    if is_twprice_command(text):
        taiwan_price = parse_twprice(text)
        pending_item = LAST_PENDING_ITEM.get(user_key)

        if taiwan_price is None:
            return "Please use:\nTWPRICE 1490"

        if not pending_item:
            return "No pending item found. Please search an item first."

        save_taiwan_price_to_sheet(pending_item, taiwan_price)

        return (
            f"✅ Taiwan price saved.\n\n"
            f"📦 Item: {pending_item}\n"
            f"🇹🇼 Taiwan Price: NT${format_money(taiwan_price)}\n\n"
            f"Now send the item again to evaluate it."
        )

    item_name, price, currency = parse_message(text)

    if item_name is None:
        return handle_help()

    taiwan_price = find_taiwan_price_from_sheet(item_name)

    if taiwan_price is None:
        LAST_PENDING_ITEM[user_key] = item_name

        converted_twd = convert_currency(price, currency, "TWD")

        if converted_twd is None:
            return (
                f"❌ Taiwan price not found.\n\n"
                f"📦 Item: {item_name}\n"
                f"💰 Original: {currency} {format_money(price)}\n\n"
                f"Currency conversion failed.\n\n"
                f"Try:\nRATE {currency}"
            )

        return format_missing_price_message(
            item_name,
            price,
            currency,
            converted_twd
        )

    result = evaluate_purchase(item_name, price, currency, taiwan_price)

    log_to_google_sheets(result, text)

    return format_result(result)


def verify_line_signature(body, signature):
    if not LINE_CHANNEL_SECRET:
        return False

    hash_value = hmac.new(
        LINE_CHANNEL_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).digest()

    expected_signature = base64.b64encode(hash_value).decode("utf-8")

    return hmac.compare_digest(expected_signature, signature)


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
    user_key = f"telegram:{chat_id}"

    reply_text = handle_text_message(user_key, text)

    send_telegram_message(chat_id, reply_text)

    return jsonify({"ok": True})


@app.route("/line-webhook", methods=["POST"])
def line_webhook():
    body = request.get_data()
    signature = request.headers.get("X-Line-Signature", "")

    if not verify_line_signature(body, signature):
        return jsonify({"error": "Invalid signature"}), 403

    payload = request.get_json()
    events = payload.get("events", [])

    for event in events:
        if event.get("type") != "message":
            continue

        message = event.get("message", {})

        if message.get("type") != "text":
            continue

        source = event.get("source", {})
        user_id = source.get("userId", "unknown")
        user_key = f"line:{user_id}"
        reply_token = event.get("replyToken")
        text = message.get("text", "")

        reply_text = handle_text_message(user_key, text)

        send_line_message(reply_token, reply_text)

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

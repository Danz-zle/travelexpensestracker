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
    "USD": ["usd", "usd$", "us$", "$", "美金"],
    "EUR": ["eur", "euro", "€"],
    "KRW": ["krw", "won", "₩", "韓元"],
    "HKD": ["hkd", "hk$", "港幣"],
    "SGD": ["sgd", "s$", "新幣"],
    "MYR": ["myr", "rm", "ringgit", "馬幣"],
    "THB": ["thb", "baht", "฿", "泰銖"],
    "VND": ["vnd", "dong", "₫", "越盾"],
    "PHP": ["php", "peso", "₱", "披索"],
    "KHR": ["khr", "riel", "៛", "柬幣"],
    "CNY": ["cny", "rmb", "yuan", "renminbi", "人民幣", "人民币", "人民元"]
}


def is_word_keyword(keyword):
    return re.match(r"^[a-zA-Z0-9]+$", keyword) is not None


def keyword_exists(text, keyword):
    lower_text = text.lower()
    lower_keyword = keyword.lower()

    if is_word_keyword(lower_keyword):
        pattern = r"\b" + re.escape(lower_keyword) + r"\b"
        return re.search(pattern, lower_text) is not None

    return lower_keyword in lower_text


def detect_currency(text):
    matches = []

    for currency_code, keywords in SUPPORTED_CURRENCIES.items():
        for keyword in keywords:
            if keyword_exists(text, keyword):
                matches.append({
                    "currency": currency_code,
                    "keyword": keyword,
                    "length": len(keyword)
                })

    if not matches:
        return None

    best_match = sorted(
        matches,
        key=lambda x: x["length"],
        reverse=True
    )[0]

    return best_match["currency"]


def remove_currency_words(text):
    cleaned = text

    all_keywords = []

    for keywords in SUPPORTED_CURRENCIES.values():
        for keyword in keywords:
            all_keywords.append(keyword)

    all_keywords = sorted(
        all_keywords,
        key=len,
        reverse=True
    )

    for keyword in all_keywords:
        if is_word_keyword(keyword):
            cleaned = re.sub(
                r"\b" + re.escape(keyword) + r"\b",
                "",
                cleaned,
                flags=re.IGNORECASE
            )
        else:
            cleaned = re.sub(
                re.escape(keyword),
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

    if currency is None:
        return None, None, None

    cleaned = remove_currency_words(text)

    price, item_text = extract_last_number(cleaned)

    item_name = normalize_spaces(item_text)

    if price is None or item_name == "":
        return None, None, currency

    return item_name, price, currency


def remove_command(text, command):
    return re.sub(
        r"(?i)^" + re.escape(command),
        "",
        text
    ).strip()


def format_money(value):
    if isinstance(value, float) and not value.is_integer():
        return round(value, 2)

    return int(value)


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


def send_telegram_message(chat_id, text):
    url = TELEGRAM_BASE_URL + "/sendMessage"

    requests.post(
        url,
        data={
            "chat_id": chat_id,
            "text": text
        }
    )


def send_line_message(reply_token, text):
    url = "https://api.line.me/v2/bot/message/reply"

    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "replyToken": reply_token,
        "messages": [
            {
                "type": "text",
                "text": text
            }
        ]
    }

    requests.post(url, headers=headers, json=data)


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


def log_expense(user_key, platform, item, currency, original_price, converted_twd):
    return call_sheets_api({
        "action": "log_expense",
        "user_key": user_key,
        "platform": platform,
        "item": item,
        "currency": currency,
        "original_price": original_price,
        "converted_twd": converted_twd
    })


def list_expenses(user_key):
    result = call_sheets_api({
        "action": "list_expenses",
        "user_key": user_key
    })

    if result and result.get("success"):
        return result.get("expenses", [])

    return []


def set_budget(user_key, budget_twd):
    return call_sheets_api({
        "action": "set_budget",
        "user_key": user_key,
        "budget_twd": budget_twd
    })


def get_budget(user_key):
    result = call_sheets_api({
        "action": "get_budget",
        "user_key": user_key
    })

    if result and result.get("found"):
        return float(result.get("budget_twd"))

    return None


def reset_trip(user_key):
    return call_sheets_api({
        "action": "reset_trip",
        "user_key": user_key
    })


def calculate_total_expenses(user_key):
    expenses = list_expenses(user_key)

    total = 0

    for expense in expenses:
        converted_twd = float(expense.get("converted_twd", 0))
        total += converted_twd

    return total, expenses


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
    cleaned = remove_command(text, command)

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
    cleaned = remove_command(text, "deleteprice")

    if not cleaned:
        return []

    results = []

    for line in cleaned.splitlines():
        item_name = normalize_spaces(line.replace(",", " "))

        if item_name:
            results.append(item_name)

    return results


def is_start_command(text):
    return text.lower().strip() in ["start", "/start", "開始", "開始使用"]


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


def is_spent_command(text):
    return text.lower().startswith("spent")


def is_expense_command(text):
    return text.lower().strip() in ["expense", "expenses", "spending", "花費", "支出"]


def is_budget_command(text):
    return text.lower().startswith("budget")


def is_resettrip_command(text):
    return text.lower().strip() in ["resettrip", "reset trip", "重置旅程"]


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


def format_currency_required_message():
    return (
        "❌ Currency not detected / 未偵測到幣別\n\n"
        "Please include currency in your message.\n"
        "請輸入商品價格時加上幣別。\n\n"
        "Examples / 範例:\n"
        "AirPods Pro USD 199\n"
        "GU 黑皮夾克 JPY 23999\n"
        "Lunch MYR 59.9\n"
        "Xiaomi Power Bank CNY 129\n\n"
        "Supported / 支援:\n"
        "JPY, USD, EUR, KRW, HKD, SGD, MYR, THB, VND, PHP, KHR, CNY\n\n"
        "Note / 注意:\n"
        "¥ is treated as JPY.\n"
        "¥ 會被視為日幣。中國請用 CNY / RMB / yuan / 人民幣。"
    )


def format_missing_price_message(item_name, price, currency, converted_twd):
    return (
        f"❌ Taiwan price not found / 尚無台灣參考價\n\n"
        f"📦 Item: {item_name}\n"
        f"💰 Original: {currency} {format_money(price)}\n"
        f"💱 Converted: NT${format_money(converted_twd)}\n\n"
        f"Database has no Taiwan reference price yet, so I cannot judge BUY / DON'T BUY.\n"
        f"資料庫還沒有台灣參考價，因此暫時無法判斷是否值得買。\n\n"
        f"Next actions / 下一步:\n\n"
        f"➕ Save Taiwan price / 新增台灣價格:\n"
        f"ADDPRICE {item_name} 999\n\n"
        f"⚡ Quick save current item / 快速保存目前商品:\n"
        f"TWPRICE 999\n\n"
        f"💱 Check currency rate / 查詢匯率:\n"
        f"RATE {currency}\n\n"
        f"📖 Help / 說明:\n"
        f"HELP"
    )


def handle_start():
    return (
        "👋 Welcome to Travel Expense Tracker\n"
        "歡迎使用 Travel Expense Tracker\n\n"
        "🛍️ Smart Shopping / 智慧比價\n"
        "Compare overseas prices against Taiwan reference prices.\n"
        "比較海外價格與台灣參考價，判斷是否值得購買。\n\n"
        "💸 Expense Tracking / 旅費記帳\n"
        "Track your spending and manage travel budgets.\n"
        "記錄旅遊花費並管理預算。\n\n"
        "────────────────\n\n"
        "You can start anywhere / 你可以從任何功能開始:\n\n"
        "➕ Build Taiwan price DB / 建立台灣價格資料庫\n"
        "ADDPRICE AirPods Pro 7490\n\n"
        "🔍 Compare price / 查詢海外價格\n"
        "AirPods Pro USD 199\n\n"
        "💰 Record expense / 記錄實際花費\n"
        "SPENT Lunch MYR 59.9\n\n"
        "📊 View spending / 查看花費\n"
        "EXPENSE\n\n"
        "📖 Full guide / 完整說明\n"
        "HELP"
    )


def handle_help():
    return (
        "📖 Travel Expense Tracker Guide\n"
        "使用說明\n\n"
        "This bot has 2 main modules:\n"
        "這個 Bot 有兩個主要功能:\n\n"
        "🛍️ MODULE A: Smart Shopping / 智慧比價\n"
        "Compare overseas prices with Taiwan reference prices.\n"
        "比較海外價格與台灣參考價。\n\n"
        "Why Taiwan price DB matters:\n"
        "為什麼需要台灣價格資料庫:\n\n"
        "Overseas converted price vs Taiwan reference price\n"
        "海外換算台幣價格 vs 台灣參考價\n\n"
        "Then bot can judge:\n"
        "然後 Bot 才能判斷:\n"
        "✅ BUY / 🟡 NORMAL / ❌ DON'T BUY\n\n"
        "🔍 Check overseas price / 查詢海外價格:\n"
        "AirPods Pro USD 199\n"
        "GU 黑皮夾克 JPY 23999\n\n"
        "➕ Add Taiwan price / 新增台灣價格:\n"
        "ADDPRICE AirPods Pro 7490\n\n"
        "Bulk add / 批量新增:\n"
        "ADDPRICE\n"
        "AirPods Pro, 7490\n"
        "Sony XM6, 10990\n\n"
        "🔄 Update / 更新:\n"
        "UPDATEPRICE AirPods Pro 6990\n\n"
        "🗑️ Delete / 刪除:\n"
        "DELETEPRICE AirPods Pro\n\n"
        "📋 List DB / 查看資料庫:\n"
        "LISTPRICE\n\n"
        "────────────────\n\n"
        "💸 MODULE B: Expense Tracking / 旅費記帳\n"
        "Record actual purchases and monitor travel budget.\n"
        "記錄實際花費並追蹤旅遊預算。\n\n"
        "💰 Record spending / 記錄花費:\n"
        "SPENT Lunch MYR 59.9\n"
        "SPENT Hotel THB 2500\n\n"
        "💵 Set budget / 設定預算:\n"
        "BUDGET 30000\n\n"
        "📊 View expenses / 查看花費:\n"
        "EXPENSE\n\n"
        "♻️ Reset trip / 重置旅程:\n"
        "RESETTRIP\n\n"
        "────────────────\n\n"
        "💱 Utilities / 工具:\n"
        "RATE JPY\n"
        "RATE USD\n"
        "RATE MYR\n"
        "RATE CNY\n\n"
        "📌 Status / 狀態:\n"
        "STATUS"
    )


def format_budget_block(budget, total):
    if budget is None:
        return (
            f"Spent / 已花費: NT${format_money(total)}\n\n"
            "⚠️ No budget set / 尚未設定預算\n\n"
            "Recommended / 建議:\n"
            "BUDGET 30000"
        )

    remaining = budget - total

    if remaining < 0:
        return (
            f"Budget / 預算: NT${format_money(budget)}\n"
            f"Spent / 已花費: NT${format_money(total)}\n\n"
            "🚨 OVER BUDGET / 已超出預算\n\n"
            f"Exceeded by / 超出: NT${format_money(abs(remaining))}"
        )

    return (
        f"Budget / 預算: NT${format_money(budget)}\n"
        f"Spent / 已花費: NT${format_money(total)}\n\n"
        f"✅ Remaining / 剩餘: NT${format_money(remaining)}"
    )


def handle_status(user_key):
    items = list_taiwan_prices_from_sheet()
    total, expenses = calculate_total_expenses(user_key)
    budget = get_budget(user_key)

    supported = " ".join(SUPPORTED_CURRENCIES.keys())

    return (
        "📊 Travel Expense Tracker Status\n"
        "目前狀態\n\n"
        "🛍️ Smart Shopping / 智慧比價\n"
        f"Taiwan DB items / 台灣價格資料庫: {len(items)}\n\n"
        "💸 Expense Tracking / 旅費記帳\n"
        f"{format_budget_block(budget, total)}\n\n"
        "────────────────\n\n"
        "🌍 Supported currencies / 支援幣別:\n"
        f"{supported}\n\n"
        "📖 Type HELP for guide / 輸入 HELP 查看說明"
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
            "Please use / 請使用:\n"
            "RATE JPY\n"
            "RATE USD\n"
            "RATE MYR\n"
            "RATE CNY\n\n"
            "Supported / 支援:\n"
            "JPY, USD, EUR, KRW, HKD, SGD, MYR, THB, VND, PHP, KHR, CNY"
        )

    one_twd_to_target = convert_currency(1, "TWD", target_currency)
    thousand_target_to_twd = convert_currency(1000, target_currency, "TWD")

    if one_twd_to_target is None or thousand_target_to_twd is None:
        return "❌ Currency rate lookup failed."

    return (
        f"💱 Current Rate Reference\n"
        f"目前匯率參考\n\n"
        f"NT$1 ≈ {target_currency} {format_money(one_twd_to_target)}\n"
        f"{target_currency} 1000 ≈ NT${format_money(thousand_target_to_twd)}"
    )


def handle_addprice(text):
    items = parse_items_with_prices(text, "addprice")

    if not items:
        return (
            "Example / 範例:\n"
            "ADDPRICE Sony XM6 10990\n\n"
            "Bulk add / 批量新增:\n"
            "ADDPRICE\n"
            "AirPods Pro, 7490\n"
            "Sony XM6, 10990"
        )

    saved_lines = []

    for item in items:
        save_taiwan_price_to_sheet(
            item["item"],
            item["taiwan_price"]
        )

        saved_lines.append(
            f"📦 {item['item']} → NT${format_money(item['taiwan_price'])}"
        )

    return "✅ Taiwan price added / 台灣價格已新增\n\n" + "\n".join(saved_lines)


def handle_updateprice(text):
    items = parse_items_with_prices(text, "updateprice")

    if not items:
        return (
            "Example / 範例:\n"
            "UPDATEPRICE Sony XM6 9990\n\n"
            "Bulk update / 批量更新:\n"
            "UPDATEPRICE\n"
            "AirPods Pro, 6990\n"
            "Sony XM6, 9990"
        )

    updated_lines = []

    for item in items:
        result = update_taiwan_price_in_sheet(
            item["item"],
            item["taiwan_price"]
        )

        status = "updated" if result and result.get("updated_existing") else "added"

        updated_lines.append(
            f"📦 {item['item']} → NT${format_money(item['taiwan_price'])} ({status})"
        )

    return "✅ Taiwan price updated / 台灣價格已更新\n\n" + "\n".join(updated_lines)


def handle_deleteprice(text):
    items = parse_delete_items(text)

    if not items:
        return (
            "Example / 範例:\n"
            "DELETEPRICE Sony XM6\n\n"
            "Bulk delete / 批量刪除:\n"
            "DELETEPRICE\n"
            "AirPods Pro\n"
            "Sony XM6"
        )

    deleted_lines = []

    for item_name in items:
        result = delete_taiwan_price_from_sheet(item_name)
        deleted_count = result.get("deleted_count", 0) if result else 0

        if deleted_count > 0:
            deleted_lines.append(
                f"🗑️ {item_name} deleted ({deleted_count})"
            )
        else:
            deleted_lines.append(
                f"⚠️ {item_name} not found"
            )

    return "✅ Delete result / 刪除結果:\n\n" + "\n".join(deleted_lines)


def handle_spent(user_key, platform, text):
    cleaned = remove_command(text, "spent")

    item_name, price, currency = parse_message(cleaned)

    if currency is None:
        return (
            "❌ Currency not detected for expense.\n"
            "記帳時請輸入幣別。\n\n"
            "Example / 範例:\n"
            "SPENT Lunch MYR 59.9\n"
            "SPENT Hotel THB 2500\n"
            "SPENT AirPods Pro USD 199"
        )

    if item_name is None:
        return (
            "Please use / 請使用:\n"
            "SPENT Lunch MYR 59.9\n"
            "SPENT Hotel THB 2500"
        )

    converted_twd = convert_currency(price, currency, "TWD")

    if converted_twd is None:
        return "❌ Currency conversion failed."

    rounded_twd = round(converted_twd)

    log_expense(
        user_key,
        platform,
        item_name,
        currency,
        price,
        rounded_twd
    )

    total, expenses = calculate_total_expenses(user_key)
    budget = get_budget(user_key)

    reply = (
        "✅ Expense recorded / 花費已記錄\n\n"
        f"📦 Item: {item_name}\n"
        f"💰 Original: {currency} {format_money(price)}\n"
        f"💱 Converted: NT${format_money(rounded_twd)}"
    )

    if budget is None:
        reply += (
            "\n\n⚠️ No budget set / 尚未設定預算\n\n"
            "Recommended / 建議:\n"
            "BUDGET 30000"
        )
        return reply

    remaining = budget - total

    if remaining < 0:
        reply += (
            "\n\n🚨 OVER BUDGET / 已超出預算\n\n"
            f"Budget / 預算: NT${format_money(budget)}\n"
            f"Spent / 已花費: NT${format_money(total)}\n"
            f"Exceeded by / 超出: NT${format_money(abs(remaining))}"
        )
    else:
        reply += (
            "\n\n✅ Within budget / 預算內\n\n"
            f"Budget / 預算: NT${format_money(budget)}\n"
            f"Spent / 已花費: NT${format_money(total)}\n"
            f"Remaining / 剩餘: NT${format_money(remaining)}"
        )

    return reply


def handle_budget(user_key, text):
    budget = parse_twprice(text)

    if budget is None:
        current_budget = get_budget(user_key)

        if current_budget is None:
            return (
                "No budget set yet / 尚未設定預算。\n\n"
                "Set budget / 設定預算:\n"
                "BUDGET 30000"
            )

        total, expenses = calculate_total_expenses(user_key)
        return (
            "💰 Current Trip Budget / 目前旅遊預算\n\n"
            f"{format_budget_block(current_budget, total)}"
        )

    set_budget(user_key, budget)

    return (
        "✅ Budget set / 預算已設定\n\n"
        f"Trip Budget / 旅遊預算: NT${format_money(budget)}"
    )


def handle_expense(user_key):
    expenses = list_expenses(user_key)
    budget = get_budget(user_key)

    if not expenses:
        if budget is None:
            return (
                "📊 No expenses recorded yet / 尚未記錄花費\n\n"
                "Record one / 記錄一筆:\n"
                "SPENT Lunch MYR 59.9\n\n"
                "Set budget / 設定預算:\n"
                "BUDGET 30000"
            )

        return (
            "📊 No expenses recorded yet / 尚未記錄花費\n\n"
            f"Budget / 預算: NT${format_money(budget)}"
        )

    total = 0
    lines = []

    for index, expense in enumerate(expenses, start=1):
        item = expense.get("item", "")
        converted_twd = float(expense.get("converted_twd", 0))
        total += converted_twd

        lines.append(
            f"{index}. {item} → NT${format_money(converted_twd)}"
        )

    summary = "💸 Trip Expense Summary\n旅費摘要\n\n"

    summary += format_budget_block(budget, total)

    summary += "\n\n────────────────\n\nPurchases / 花費明細:\n"
    summary += "\n".join(lines)

    if len(summary) > 4500:
        summary = summary[:4400] + "\n\n...too many expenses, please check Google Sheet."

    return summary


def handle_resettrip(user_key):
    result = reset_trip(user_key)

    if not result or not result.get("success"):
        return "❌ Reset failed."

    deleted_expenses = result.get("deleted_expenses", 0)
    deleted_budgets = result.get("deleted_budgets", 0)

    return (
        "♻️ Trip reset completed / 旅程已重置\n\n"
        f"Deleted expenses / 刪除花費: {deleted_expenses}\n"
        f"Deleted budgets / 刪除預算: {deleted_budgets}\n\n"
        "You can now start a new trip.\n"
        "現在可以開始新的旅程。"
    )


def handle_text_message(user_key, platform, text):
    if is_start_command(text):
        return handle_start()

    if is_help_command(text):
        return handle_help()

    if is_status_command(text):
        return handle_status(user_key)

    if is_listprice_command(text):
        return handle_listprice()

    if is_rate_command(text):
        return handle_rate(text)

    if is_spent_command(text):
        return handle_spent(user_key, platform, text)

    if is_expense_command(text):
        return handle_expense(user_key)

    if is_budget_command(text):
        return handle_budget(user_key, text)

    if is_resettrip_command(text):
        return handle_resettrip(user_key)

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
            return "Please use / 請使用:\nTWPRICE 1490"

        if not pending_item:
            return "No pending item found. Please search an item first."

        save_taiwan_price_to_sheet(
            pending_item,
            taiwan_price
        )

        return (
            f"✅ Taiwan price saved / 台灣價格已保存\n\n"
            f"📦 Item: {pending_item}\n"
            f"🇹🇼 Taiwan Price: NT${format_money(taiwan_price)}\n\n"
            f"Now send the item again to evaluate it.\n"
            f"現在可以重新輸入商品價格進行判斷。"
        )

    item_name, price, currency = parse_message(text)

    if currency is None:
        return format_currency_required_message()

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

    result = evaluate_purchase(
        item_name,
        price,
        currency,
        taiwan_price
    )

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

    reply_text = handle_text_message(
        user_key,
        "Telegram",
        text
    )

    send_telegram_message(
        chat_id,
        reply_text
    )

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

        reply_text = handle_text_message(
            user_key,
            "LINE",
            text
        )

        send_line_message(
            reply_token,
            reply_text
        )

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000
    )

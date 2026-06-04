from exchange import convert_currency

from config import SUPPORTED_CURRENCIES
from currency_utils import parse_rate_command
from formatters import (
    bucket_label,
    format_budget_block,
    format_money,
    supported_currency_text
)
from sheets_api import (
    calculate_total_expenses,
    get_active_trip,
    get_budget,
    list_taiwan_prices_from_sheet
)


def is_start_command(text):
    return text.lower().strip() in [
        "start",
        "/start",
        "開始",
        "開始使用"
    ]


def is_help_command(text):
    return text.lower().strip() in [
        "help",
        "/help",
        "menu",
        "指令",
        "幫助"
    ]


def is_status_command(text):
    return text.lower().strip() in [
        "status",
        "狀態"
    ]


def is_rate_command(text):
    return text.lower().startswith("rate")


def handle_start():
    return (
        "👋 Welcome to Travel Expense Tracker\n"
        "歡迎使用 Travel Expense Tracker\n\n"
        "🛍️ Smart Shopping / 智慧比價\n"
        "Compare overseas prices against Taiwan reference prices.\n"
        "比較海外價格與台灣參考價，判斷是否值得購買。\n\n"
        "💸 Expense Tracking / 旅費記帳\n"
        "Track your spending by trip or daily mode.\n"
        "依照旅程或日常模式記錄花費。\n\n"
        "────────────────\n\n"
        "You can start anywhere / 你可以從任何功能開始:\n\n"
        "🧳 Start a trip / 建立旅程\n"
        "NEWTRIP Japan Sakura 2027\n\n"
        "🏠 Daily mode / 日常模式\n"
        "USEDEFAULT\n\n"
        "➕ Build Taiwan price DB / 建立台灣價格資料庫\n"
        "ADDPRICE AirPods Pro 7490\n\n"
        "🔍 Compare price / 查詢海外價格\n"
        "AirPods Pro USD 199\n\n"
        "💰 Record expense / 記錄實際花費\n"
        "SPENT Lunch MYR 59.9\n\n"
        "💰 Bulk record / 批量記帳\n"
        "SPENT\n"
        "Lunch MYR 59.9\n"
        "Taxi MYR 20\n\n"
        "📊 View spending / 查看花費\n"
        "EXPENSE\n\n"
        "📖 Full guide / 完整說明\n"
        "HELP"
    )


def handle_help():
    return (
        "📖 Travel Expense Tracker Guide\n"
        "使用說明\n\n"
        "🛍️ MODULE A: Smart Shopping / 智慧比價\n"
        "Compare overseas prices with Taiwan reference prices.\n"
        "比較海外價格與台灣參考價。\n\n"
        "Why Taiwan price DB matters:\n"
        "海外換算台幣價格 vs 台灣參考價\n"
        "Then bot can judge:\n"
        "✅ BUY / 🟡 NORMAL / ❌ DON'T BUY\n\n"
        "🔍 Check overseas price / 查詢海外價格:\n"
        "AirPods Pro USD 199\n\n"
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
        "Record expenses by trip or daily mode.\n"
        "依照旅程或日常模式記錄花費。\n\n"
        "🧳 Create or switch trip / 建立或切換旅程:\n"
        "NEWTRIP Japan Sakura 2027\n\n"
        "🏠 Daily mode / 日常模式:\n"
        "USEDEFAULT\n\n"
        "📂 View buckets / 查看花費分類:\n"
        "MYTRIPS\n\n"
        "💰 Record spending / 記錄花費:\n"
        "SPENT Lunch MYR 59.9\n"
        "SPENT Flight TWD 13435\n\n"
        "💰 Bulk spending / 批量記帳:\n"
        "SPENT\n"
        "Lunch MYR 59.9\n"
        "Taxi MYR 20\n"
        "Coffee 80 TWD\n\n"
        "💵 Set budget / 設定預算:\n"
        "BUDGET 30000\n\n"
        "📊 View expenses / 查看花費:\n"
        "EXPENSE\n\n"
        "────────────────\n\n"
        "💱 Utilities / 工具:\n"
        "RATE JPY\n"
        "RATE USD\n"
        "RATE MYR\n"
        "RATE CNY\n\n"
        "📌 Status / 狀態:\n"
        "STATUS"
    )


def handle_status(user_key):
    items = list_taiwan_prices_from_sheet()
    trip_name = get_active_trip(user_key)
    total, expenses = calculate_total_expenses(
        user_key,
        trip_name
    )
    budget = get_budget(
        user_key,
        trip_name
    )

    return (
        "📊 Travel Expense Tracker Status\n"
        "目前狀態\n\n"
        "📂 Active Bucket / 目前花費分類\n"
        f"{bucket_label(trip_name)}\n\n"
        "🛍️ Smart Shopping / 智慧比價\n"
        f"Taiwan DB items / 台灣價格資料庫: {len(items)}\n\n"
        "💸 Expense Tracking / 旅費記帳\n"
        f"{format_budget_block(budget, total)}\n\n"
        "────────────────\n\n"
        "🌍 Supported currencies / 支援幣別:\n"
        f"{supported_currency_text()}\n\n"
        "📖 Type HELP for guide / 輸入 HELP 查看說明"
    )


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
            "TWD, JPY, USD, EUR, KRW, HKD, SGD, MYR, THB, VND, PHP, KHR, CNY"
        )

    if target_currency == "TWD":
        return (
            "💱 Current Rate Reference\n"
            "目前匯率參考\n\n"
            "NT$1 = TWD 1\n"
            "TWD 1000 = NT$1000"
        )

    one_twd_to_target = convert_currency(
        1,
        "TWD",
        target_currency
    )

    thousand_target_to_twd = convert_currency(
        1000,
        target_currency,
        "TWD"
    )

    if one_twd_to_target is None or thousand_target_to_twd is None:
        return "❌ Currency rate lookup failed."

    return (
        "💱 Current Rate Reference\n"
        "目前匯率參考\n\n"
        f"NT$1 ≈ {target_currency} {format_money(one_twd_to_target)}\n"
        f"{target_currency} 1000 ≈ NT${format_money(thousand_target_to_twd)}"
    )

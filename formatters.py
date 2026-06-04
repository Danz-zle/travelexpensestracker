from config import SUPPORTED_CURRENCIES


def format_money(value):
    if isinstance(value, float) and not value.is_integer():
        return round(value, 2)

    return int(value)


def is_default_trip(trip_name):
    return str(trip_name).strip().lower() == "default"


def bucket_label(trip_name):
    if is_default_trip(trip_name):
        return "🏠 Mode: Default / Daily\n日常模式"

    return f"🧳 Trip: {trip_name}"


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
        "Flight TWD 13435\n"
        "Xiaomi Power Bank CNY 129\n\n"
        "Supported / 支援:\n"
        "TWD, JPY, USD, EUR, KRW, HKD, SGD, MYR, THB, VND, PHP, KHR, CNY\n\n"
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


def supported_currency_text():
    return " ".join(SUPPORTED_CURRENCIES.keys())

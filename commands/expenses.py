import re

from currency_utils import (
    convert_to_twd,
    parse_message
)
from formatters import (
    bucket_label,
    format_budget_block,
    format_money,
    is_default_trip
)
from sheets_api import (
    calculate_total_expenses,
    delete_expense,
    get_active_trip,
    get_budget,
    list_expenses,
    log_expense,
    recent_expenses,
    set_budget
)
from state import (
    LAST_RECENT_EXPENSES,
    PENDING_EXPENSE_DELETE
)


def remove_command(text, command):
    return re.sub(
        r"(?i)^" + re.escape(command),
        "",
        text
    ).strip()


def is_spent_command(text):
    return text.lower().startswith("spent")


def is_expense_command(text):
    return text.lower().strip() in [
        "expense",
        "expenses",
        "spending",
        "花費",
        "支出"
    ]


def is_budget_command(text):
    return text.lower().startswith("budget")


def is_recent_command(text):
    return text.lower().startswith("recent")


def is_deleteexpense_command(text):
    return text.lower().startswith("deleteexpense")


def is_yesdelete_command(text):
    return text.lower().strip() == "yesdelete"


def is_cancel_command(text):
    return text.lower().strip() in [
        "cancel",
        "取消"
    ]


def parse_twprice(text):
    numbers = re.findall(
        r"\d+(?:\.\d+)?",
        text
    )

    if not numbers:
        return None

    value = numbers[-1]

    return float(value) if "." in value else int(value)


def parse_recent_limit(text):
    numbers = re.findall(
        r"\d+",
        text
    )

    if not numbers:
        return 10

    limit = int(numbers[-1])

    if limit < 1:
        return 10

    if limit > 30:
        return 30

    return limit


def parse_deleteexpense_index(text):
    numbers = re.findall(
        r"\d+",
        text
    )

    if not numbers:
        return None

    return int(numbers[-1])


def parse_bulk_spent_items(text):
    cleaned = remove_command(
        text,
        "spent"
    )

    if not cleaned:
        return []

    lines = cleaned.splitlines()
    results = []

    for line in lines:
        line = line.strip()

        if not line:
            continue

        item_name, price, currency = parse_message(line)

        if item_name and price is not None and currency:
            results.append({
                "item": item_name,
                "price": price,
                "currency": currency,
                "raw": line
            })
        else:
            results.append({
                "error": True,
                "raw": line
            })

    return results


def build_budget_reply_after_spent(user_key, trip_name):
    total, expenses = calculate_total_expenses(
        user_key,
        trip_name
    )

    budget = get_budget(
        user_key,
        trip_name
    )

    if budget is None:
        return (
            f"\n\nTotal / 總花費: NT${format_money(total)}\n\n"
            "⚠️ No budget set / 尚未設定預算\n\n"
            "Recommended / 建議:\n"
            "BUDGET 30000"
        )

    remaining = budget - total

    if remaining < 0:
        return (
            "\n\n🚨 OVER BUDGET / 已超出預算\n\n"
            f"Budget / 預算: NT${format_money(budget)}\n"
            f"Spent / 已花費: NT${format_money(total)}\n"
            f"Exceeded by / 超出: NT${format_money(abs(remaining))}"
        )

    return (
        "\n\n✅ Within budget / 預算內\n\n"
        f"Budget / 預算: NT${format_money(budget)}\n"
        f"Spent / 已花費: NT${format_money(total)}\n"
        f"Remaining / 剩餘: NT${format_money(remaining)}"
    )


def handle_single_spent(user_key, platform, text):
    cleaned = remove_command(
        text,
        "spent"
    )

    item_name, price, currency = parse_message(cleaned)

    if currency is None:
        return (
            "❌ Currency not detected for expense.\n"
            "記帳時請輸入幣別。\n\n"
            "Example / 範例:\n"
            "SPENT Lunch MYR 59.9\n"
            "SPENT Flight TWD 13435\n"
            "SPENT Hotel THB 2500\n\n"
            "Bulk / 批量:\n"
            "SPENT\n"
            "Lunch MYR 59.9\n"
            "Taxi MYR 20"
        )

    if item_name is None:
        return (
            "Please use / 請使用:\n"
            "SPENT Lunch MYR 59.9\n"
            "SPENT Flight TWD 13435"
        )

    trip_name = get_active_trip(user_key)

    converted_twd = convert_to_twd(
        price,
        currency
    )

    if converted_twd is None:
        return "❌ Currency conversion failed."

    rounded_twd = round(converted_twd)

    log_expense(
        user_key,
        trip_name,
        platform,
        item_name,
        currency,
        price,
        rounded_twd
    )

    reply = (
        "✅ Expense recorded / 花費已記錄\n\n"
        f"{bucket_label(trip_name)}\n\n"
        f"📦 Item: {item_name}\n"
        f"💰 Original: {currency} {format_money(price)}\n"
        f"💱 Converted: NT${format_money(rounded_twd)}"
    )

    reply += build_budget_reply_after_spent(
        user_key,
        trip_name
    )

    return reply


def handle_bulk_spent(user_key, platform, text):
    parsed_items = parse_bulk_spent_items(text)

    if not parsed_items:
        return handle_single_spent(
            user_key,
            platform,
            text
        )

    trip_name = get_active_trip(user_key)

    recorded_lines = []
    error_lines = []
    added_total = 0
    recorded_count = 0

    for item in parsed_items:
        if item.get("error"):
            error_lines.append(
                f"⚠️ Could not parse: {item.get('raw')}"
            )
            continue

        converted_twd = convert_to_twd(
            item["price"],
            item["currency"]
        )

        if converted_twd is None:
            error_lines.append(
                f"⚠️ Conversion failed: {item.get('raw')}"
            )
            continue

        rounded_twd = round(converted_twd)

        log_expense(
            user_key,
            trip_name,
            platform,
            item["item"],
            item["currency"],
            item["price"],
            rounded_twd
        )

        recorded_count += 1
        added_total += rounded_twd

        recorded_lines.append(
            f"{recorded_count}. {item['item']} → NT${format_money(rounded_twd)}"
        )

    if recorded_count == 0:
        return (
            "❌ No expenses recorded.\n"
            "沒有成功記錄任何花費。\n\n"
            "Please use / 請使用:\n"
            "SPENT\n"
            "Lunch MYR 59.9\n"
            "Taxi MYR 20\n"
            "Coffee 80 TWD"
        )

    reply = (
        f"✅ {recorded_count} expenses recorded / 已記錄 {recorded_count} 筆花費\n\n"
        f"{bucket_label(trip_name)}\n\n"
        + "\n".join(recorded_lines) +
        f"\n\nAdded / 本次新增: NT${format_money(added_total)}"
    )

    if error_lines:
        reply += "\n\n" + "\n".join(error_lines)

    reply += build_budget_reply_after_spent(
        user_key,
        trip_name
    )

    return reply


def handle_spent(user_key, platform, text):
    cleaned = remove_command(
        text,
        "spent"
    )

    if "\n" in cleaned.strip():
        return handle_bulk_spent(
            user_key,
            platform,
            text
        )

    return handle_single_spent(
        user_key,
        platform,
        text
    )


def handle_budget(user_key, text):
    budget = parse_twprice(text)

    trip_name = get_active_trip(user_key)

    if budget is None:
        current_budget = get_budget(
            user_key,
            trip_name
        )

        if current_budget is None:
            return (
                f"{bucket_label(trip_name)}\n\n"
                "No budget set yet / 尚未設定預算。\n\n"
                "Set budget / 設定預算:\n"
                "BUDGET 30000"
            )

        total, expenses = calculate_total_expenses(
            user_key,
            trip_name
        )

        return (
            "💰 Current Budget / 目前預算\n\n"
            f"{bucket_label(trip_name)}\n\n"
            f"{format_budget_block(current_budget, total)}"
        )

    set_budget(
        user_key,
        trip_name,
        budget
    )

    return (
        "✅ Budget set / 預算已設定\n\n"
        f"{bucket_label(trip_name)}\n"
        f"Budget / 預算: NT${format_money(budget)}"
    )


def handle_expense(user_key):
    trip_name = get_active_trip(user_key)

    expenses = list_expenses(
        user_key,
        trip_name
    )

    budget = get_budget(
        user_key,
        trip_name
    )

    if is_default_trip(trip_name):
        title = "💸 Daily Expense Summary\n日常花費摘要"
    else:
        title = "💸 Trip Expense Summary\n旅費摘要"

    if not expenses:
        if budget is None:
            return (
                "📊 No expenses recorded yet / 尚未記錄花費\n\n"
                f"{bucket_label(trip_name)}\n\n"
                "Record one / 記錄一筆:\n"
                "SPENT Lunch MYR 59.9\n\n"
                "Set budget / 設定預算:\n"
                "BUDGET 30000"
            )

        return (
            "📊 No expenses recorded yet / 尚未記錄花費\n\n"
            f"{bucket_label(trip_name)}\n"
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

    summary = f"{title}\n\n{bucket_label(trip_name)}\n\n"
    summary += format_budget_block(
        budget,
        total
    )
    summary += "\n\n────────────────\n\nPurchases / 花費明細:\n"
    summary += "\n".join(lines)

    if len(summary) > 4500:
        summary = summary[:4400] + "\n\n...too many expenses, please check Google Sheet."

    return summary


def handle_recent(user_key, text):
    trip_name = get_active_trip(user_key)
    limit = parse_recent_limit(text)

    expenses = recent_expenses(
        user_key,
        trip_name,
        limit
    )

    if not expenses:
        return (
            "🧾 No recent expenses found / 沒有最近花費\n\n"
            f"{bucket_label(trip_name)}\n\n"
            "Record one / 記錄一筆:\n"
            "SPENT Lunch MYR 59.9"
        )

    LAST_RECENT_EXPENSES[user_key] = {}

    lines = []
    shown_total = 0

    for index, expense in enumerate(expenses, start=1):
        row_number = expense.get("row_number")
        item = expense.get("item", "")
        currency = expense.get("currency", "")
        original_price = expense.get("original_price", "")
        converted_twd = float(expense.get("converted_twd", 0))

        shown_total += converted_twd

        LAST_RECENT_EXPENSES[user_key][index] = expense

        lines.append(
            f"{index}. {item}\n"
            f"   {currency} {format_money(float(original_price))} → NT${format_money(converted_twd)}"
        )

    return (
        "🧾 Recent Expenses\n"
        "最近花費\n\n"
        f"{bucket_label(trip_name)}\n\n"
        + "\n\n".join(lines) +
        "\n\n────────────────\n\n"
        f"Total shown / 顯示總額: NT${format_money(shown_total)}\n\n"
        "Delete / 刪除:\n"
        "DELETEEXPENSE 2\n\n"
        "Show more / 顯示更多:\n"
        "RECENT 20"
    )


def handle_deleteexpense(user_key, text):
    index = parse_deleteexpense_index(text)

    if index is None:
        return (
            "Please choose an expense number from RECENT.\n"
            "請先從 RECENT 選擇要刪除的編號。\n\n"
            "Example / 範例:\n"
            "RECENT\n"
            "DELETEEXPENSE 2"
        )

    recent_map = LAST_RECENT_EXPENSES.get(user_key)

    if not recent_map or index not in recent_map:
        return (
            "Expense number not found.\n"
            "找不到這個花費編號。\n\n"
            "Please run RECENT again first.\n"
            "請先重新輸入 RECENT。"
        )

    expense = recent_map[index]

    PENDING_EXPENSE_DELETE[user_key] = expense

    item = expense.get("item", "")
    currency = expense.get("currency", "")
    original_price = expense.get("original_price", "")
    converted_twd = float(expense.get("converted_twd", 0))
    trip_name = expense.get("trip_name", "")

    return (
        "⚠️ Confirm expense deletion\n"
        "確認刪除花費\n\n"
        f"{bucket_label(trip_name)}\n\n"
        f"Item / 項目:\n"
        f"{item}\n\n"
        f"Original / 原始金額:\n"
        f"{currency} {format_money(float(original_price))}\n\n"
        f"Converted / 換算台幣:\n"
        f"NT${format_money(converted_twd)}\n\n"
        "Reply / 回覆:\n"
        "YESDELETE\n\n"
        "Cancel / 取消:\n"
        "CANCEL"
    )


def handle_yesdelete_expense(user_key):
    expense = PENDING_EXPENSE_DELETE.get(user_key)

    if not expense:
        return (
            "No pending expense deletion found.\n"
            "目前沒有等待確認的花費刪除。"
        )

    row_number = expense.get("row_number")

    result = delete_expense(
        user_key,
        row_number
    )

    PENDING_EXPENSE_DELETE.pop(
        user_key,
        None
    )

    if not result or not result.get("success"):
        return (
            "❌ Expense deletion failed.\n"
            "花費刪除失敗。"
        )

    deleted = result.get("deleted_expense", {})

    item = deleted.get("item", "")
    currency = deleted.get("currency", "")
    original_price = deleted.get("original_price", "")
    converted_twd = float(deleted.get("converted_twd", 0))
    trip_name = deleted.get("trip_name", "")

    return (
        "✅ Expense deleted / 花費已刪除\n\n"
        f"{bucket_label(trip_name)}\n\n"
        f"Item / 項目:\n"
        f"{item}\n\n"
        f"Removed / 已移除:\n"
        f"{currency} {format_money(float(original_price))} → NT${format_money(converted_twd)}"
    )


def handle_cancel_expense_delete(user_key):
    if user_key in PENDING_EXPENSE_DELETE:
        PENDING_EXPENSE_DELETE.pop(
            user_key,
            None
        )

        return (
            "✅ Cancelled / 已取消\n\n"
            "Pending expense deletion has been cancelled.\n"
            "待確認的花費刪除已取消。"
        )

    return None

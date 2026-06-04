import re

from formatters import (
    format_money,
    is_default_trip
)
from sheets_api import (
    calculate_total_expenses,
    delete_trips,
    get_budget,
    list_trips,
    set_active_trip
)
from state import PENDING_TRIP_DELETE


def remove_command(text, command):
    return re.sub(
        r"(?i)^" + re.escape(command),
        "",
        text
    ).strip()


def is_newtrip_command(text):
    return text.lower().startswith("newtrip")


def is_usedefault_command(text):
    return text.lower().strip() in [
        "usedefault",
        "default",
        "dailymode",
        "daily",
        "日常模式"
    ]


def is_mytrips_command(text):
    return text.lower().strip() in [
        "mytrips",
        "mytrip",
        "trips",
        "triplist",
        "旅程",
        "我的旅程"
    ]


def is_deletetrip_command(text):
    return text.lower().startswith("deletetrip")


def is_confirmdelete_command(text):
    return text.lower().strip() == "confirmdelete"


def is_cancel_command(text):
    return text.lower().strip() in [
        "cancel",
        "取消"
    ]


def is_resettrip_command(text):
    return text.lower().strip() in [
        "resettrip",
        "reset trip",
        "重置旅程"
    ]


def parse_trip_names_for_delete(text):
    cleaned = remove_command(
        text,
        "deletetrip"
    )

    if not cleaned:
        return []

    lines = cleaned.splitlines()
    trip_names = []

    for line in lines:
        name = line.strip()

        if name:
            trip_names.append(name)

    return trip_names


def handle_newtrip(user_key, text):
    trip_name = remove_command(
        text,
        "newtrip"
    )

    if not trip_name:
        return (
            "Please enter trip name / 請輸入旅程名稱:\n\n"
            "NEWTRIP Japan Sakura 2027\n"
            "NEWTRIP Bangkok Food Trip\n"
            "NEWTRIP Korea Family Trip"
        )

    set_active_trip(
        user_key,
        trip_name
    )

    budget = get_budget(
        user_key,
        trip_name
    )

    reply = (
        "✅ Active trip set / 目前旅程已設定\n\n"
        f"🧳 Trip / 旅程:\n"
        f"{trip_name}\n\n"
        "All SPENT / BUDGET / EXPENSE commands will use this trip.\n"
        "接下來的 SPENT / BUDGET / EXPENSE 都會記錄在此旅程。"
    )

    if budget is None:
        reply += (
            "\n\n💡 Budget not set yet / 尚未設定預算\n\n"
            "Suggested / 建議:\n"
            "BUDGET 30000"
        )

    return reply


def handle_usedefault(user_key):
    set_active_trip(
        user_key,
        "Default"
    )

    return (
        "🏠 Switched to Daily Mode\n"
        "已切換至日常模式\n\n"
        "📂 Active Bucket:\n"
        "Default / Daily\n\n"
        "All new SPENT / BUDGET / EXPENSE records will use Default.\n"
        "之後所有 SPENT / BUDGET / EXPENSE 都會記錄在 Default。"
    )


def handle_mytrips(user_key):
    trips = list_trips(user_key)

    if not trips:
        return (
            "📂 No expense buckets yet / 尚未建立花費分類\n\n"
            "Create trip / 建立旅程:\n"
            "NEWTRIP Japan Sakura 2027\n\n"
            "Or use daily mode / 或使用日常模式:\n"
            "USEDEFAULT"
        )

    active_lines = []
    other_lines = []

    for index, trip in enumerate(trips, start=1):
        trip_name = trip.get("trip_name", "")
        is_active = str(trip.get("is_active", "")).lower() == "true"

        total, expenses = calculate_total_expenses(
            user_key,
            trip_name
        )

        budget = get_budget(
            user_key,
            trip_name
        )

        if budget is None:
            budget_text = f"Spent NT${format_money(total)}"
        else:
            remaining = budget - total

            if remaining < 0:
                budget_text = (
                    f"Spent NT${format_money(total)} / "
                    f"Over NT${format_money(abs(remaining))}"
                )
            else:
                budget_text = (
                    f"Spent NT${format_money(total)} / "
                    f"Remaining NT${format_money(remaining)}"
                )

        if is_default_trip(trip_name):
            name_line = "🏠 Default / Daily"
        else:
            name_line = f"🧳 {trip_name}"

        trip_line = (
            f"{index}. {name_line}\n"
            f"   {budget_text}"
        )

        if is_active:
            active_lines.append(trip_line)
        else:
            other_lines.append(trip_line)

    message = "📂 Expense Buckets / 花費分類\n\n"

    if active_lines:
        message += "🟢 Active Bucket\n目前使用\n\n"
        message += "\n".join(active_lines)

    if other_lines:
        message += "\n\n⚪ Other Buckets\n其他分類\n\n"
        message += "\n".join(other_lines)

    message += (
        "\n\n────────────────\n\n"
        "Create or switch trip / 建立或切換旅程:\n"
        "NEWTRIP Japan Sakura 2027\n\n"
        "Daily mode / 日常模式:\n"
        "USEDEFAULT\n\n"
        "Delete trip / 刪除旅程:\n"
        "DELETETRIP Japan Sakura 2027"
    )

    return message


def handle_deletetrip(user_key, text):
    trip_names = parse_trip_names_for_delete(text)

    if not trip_names:
        return (
            "Please enter trip name to delete / 請輸入要刪除的旅程名稱:\n\n"
            "Single / 單筆:\n"
            "DELETETRIP Japan Sakura 2027\n\n"
            "Bulk / 批量:\n"
            "DELETETRIP\n"
            "Japan Sakura 2027\n"
            "Bangkok Food Trip\n\n"
            "Default cannot be deleted.\n"
            "Default 無法刪除。"
        )

    valid_names = []
    skipped_names = []

    for trip_name in trip_names:
        if is_default_trip(trip_name):
            skipped_names.append(trip_name)
        else:
            valid_names.append(trip_name)

    if not valid_names:
        return (
            "⚠️ No trips can be deleted.\n"
            "沒有可刪除的旅程。\n\n"
            "Default cannot be deleted.\n"
            "Default 無法刪除。"
        )

    PENDING_TRIP_DELETE[user_key] = valid_names

    lines = []

    for index, trip_name in enumerate(valid_names, start=1):
        lines.append(
            f"{index}. {trip_name}"
        )

    message = (
        "⚠️ Confirm trip deletion\n"
        "確認刪除旅程\n\n"
        "Trips to delete / 即將刪除:\n"
        + "\n".join(lines) +
        "\n\nThis will also delete:\n"
        "• Trip record\n"
        "• Budget\n"
        "• All expenses under these trips\n\n"
        "這也會刪除:\n"
        "• 旅程資料\n"
        "• 預算\n"
        "• 這些旅程下的所有花費\n\n"
        "Reply / 回覆:\n"
        "CONFIRMDELETE\n\n"
        "Cancel / 取消:\n"
        "CANCEL"
    )

    if skipped_names:
        message += (
            "\n\nSkipped / 已略過:\n"
            + "\n".join(skipped_names) +
            "\n(Default cannot be deleted)"
        )

    return message


def handle_confirm_delete_trip(user_key):
    trip_names = PENDING_TRIP_DELETE.get(user_key)

    if not trip_names:
        return (
            "No pending trip deletion found.\n"
            "目前沒有等待確認的旅程刪除。"
        )

    result = delete_trips(
        user_key,
        trip_names
    )

    PENDING_TRIP_DELETE.pop(
        user_key,
        None
    )

    if not result or not result.get("success"):
        return "❌ Trip deletion failed / 旅程刪除失敗。"

    deleted_trips = result.get("deleted_trips", [])
    deleted_expenses = result.get("deleted_expenses", 0)
    deleted_budgets = result.get("deleted_budgets", 0)
    skipped_trips = result.get("skipped_trips", [])

    reply = (
        "✅ Trip deletion completed / 旅程刪除完成\n\n"
        f"Deleted trips / 已刪除旅程: {len(deleted_trips)}\n"
        f"Deleted expenses / 已刪除花費: {deleted_expenses}\n"
        f"Deleted budgets / 已刪除預算: {deleted_budgets}\n\n"
        "Active bucket switched to:\n"
        "🏠 Default / Daily"
    )

    if deleted_trips:
        reply += (
            "\n\nDeleted / 已刪除:\n"
            + "\n".join(deleted_trips)
        )

    if skipped_trips:
        skipped_lines = []

        for item in skipped_trips:
            skipped_lines.append(
                f"{item.get('trip_name')} - {item.get('reason')}"
            )

        reply += (
            "\n\nSkipped / 已略過:\n"
            + "\n".join(skipped_lines)
        )

    return reply


def handle_cancel_trip_delete(user_key):
    if user_key in PENDING_TRIP_DELETE:
        PENDING_TRIP_DELETE.pop(
            user_key,
            None
        )

        return (
            "✅ Cancelled / 已取消\n\n"
            "Pending trip deletion has been cancelled.\n"
            "待確認的旅程刪除已取消。"
        )

    return None


def handle_resettrip():
    return (
        "⚠️ RESETTRIP is disabled / RESETTRIP 已停用\n\n"
        "To protect your travel history, trip deletion is disabled.\n"
        "為避免誤刪歷史旅程資料，目前不支援清除旅程。\n\n"
        "Delete a specific trip / 刪除指定旅程:\n"
        "DELETETRIP Japan Sakura 2027\n\n"
        "Use daily mode / 使用日常模式:\n"
        "USEDEFAULT\n\n"
        "View buckets / 查看分類:\n"
        "MYTRIPS"
    )

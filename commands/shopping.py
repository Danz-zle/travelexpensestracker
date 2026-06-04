from currency_utils import (
    extract_last_number,
    normalize_spaces,
    parse_message,
    convert_to_twd
)
from evaluator import evaluate_purchase
from formatters import (
    format_currency_required_message,
    format_missing_price_message,
    format_money,
    format_result
)
from sheets_api import (
    delete_taiwan_price_from_sheet,
    find_taiwan_price_from_sheet,
    list_taiwan_prices_from_sheet,
    log_price_check_to_sheet,
    save_taiwan_price_to_sheet,
    update_taiwan_price_in_sheet
)
from state import LAST_PENDING_ITEM


def remove_command(text, command):
    import re
    return re.sub(
        r"(?i)^" + re.escape(command),
        "",
        text
    ).strip()


def is_listprice_command(text):
    return text.lower().strip() in [
        "listprice",
        "list",
        "prices",
        "清單"
    ]


def is_twprice_command(text):
    return text.lower().startswith("twprice")


def is_addprice_command(text):
    return text.lower().startswith("addprice")


def is_updateprice_command(text):
    return text.lower().startswith("updateprice")


def is_deleteprice_command(text):
    return text.lower().startswith("deleteprice")


def parse_twprice(text):
    import re

    numbers = re.findall(
        r"\d+(?:\.\d+)?",
        text
    )

    if not numbers:
        return None

    value = numbers[-1]

    return float(value) if "." in value else int(value)


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


def handle_twprice(user_key, text):
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


def handle_price_compare(user_key, text):
    item_name, price, currency = parse_message(text)

    if currency is None:
        return format_currency_required_message()

    if item_name is None:
        return None

    taiwan_price = find_taiwan_price_from_sheet(item_name)

    if taiwan_price is None:
        LAST_PENDING_ITEM[user_key] = item_name

        converted_twd = convert_to_twd(
            price,
            currency
        )

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

    log_price_check_to_sheet(
        result,
        text
    )

    return format_result(result)

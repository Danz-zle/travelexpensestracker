import json
from exchange import convert_currency


def load_prices():
    with open("taiwan_prices.json", "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_text(text):

    text = text.lower()
    text = text.replace("s", "")

    return text.strip()


def calculate_match_score(input_text, db_text):

    input_words = set(normalize_text(input_text).split())
    db_words = set(normalize_text(db_text).split())

    matched_words = input_words.intersection(db_words)

    return len(matched_words)


def find_taiwan_price(item_name):

    prices = load_prices()

    best_match = None
    best_score = 0

    for p in prices:

        score = calculate_match_score(
            item_name,
            p["item"]
        )

        if score > best_score:
            best_score = score
            best_match = p

    if best_match and best_score >= 2:
        return best_match["taiwan_price"]

    return None


def evaluate_purchase(item_name, original_price, currency):

    converted = convert_currency(
        original_price,
        currency,
        "TWD"
    )

    if converted is None:
        return {
            "error": "Currency conversion failed"
        }

    taiwan_price = find_taiwan_price(item_name)

    if taiwan_price is None:
        return {
            "error": "No Taiwan price found"
        }

    diff_percent = (
        (converted - taiwan_price)
        / taiwan_price
    ) * 100

    if diff_percent <= -15:
        decision = "BUY"

    elif diff_percent <= 10:
        decision = "NORMAL"

    else:
        decision = "DON'T BUY"

    return {
        "item": item_name,
        "original_price": original_price,
        "currency": currency,
        "converted_twd": round(converted),
        "taiwan_price": taiwan_price,
        "difference_percent": round(diff_percent, 1),
        "decision": decision
    }

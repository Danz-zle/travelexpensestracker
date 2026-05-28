from exchange import convert_currency


def evaluate_purchase(item_name, original_price, currency, taiwan_price):

    converted = convert_currency(
        original_price,
        currency,
        "TWD"
    )

    if converted is None:
        return {
            "error": "Currency conversion failed"
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

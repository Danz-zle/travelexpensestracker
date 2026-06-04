import re

from config import SUPPORTED_CURRENCIES
from exchange import convert_currency


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
        all_keywords.extend(keywords)

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
    matches = list(
        re.finditer(
            r"\d+(?:\.\d+)?",
            text
        )
    )

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


def convert_to_twd(amount, currency):
    if currency == "TWD":
        return amount

    return convert_currency(
        amount,
        currency,
        "TWD"
    )


def parse_rate_command(text):
    parts = text.strip().split()

    if len(parts) < 2:
        return None

    target = parts[1].upper()

    if target in SUPPORTED_CURRENCIES:
        return target

    return None

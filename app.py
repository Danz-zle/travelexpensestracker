import hmac
import base64
import hashlib
import requests
from flask import Flask, request, jsonify

from command_aliases import normalize_command_text
from config import LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET, TELEGRAM_BASE_URL

from commands.utility import *
from commands.shopping import *
from commands.trips import *
from commands.expenses import *

app = Flask(__name__)


def send_telegram_message(chat_id, text):
    requests.post(TELEGRAM_BASE_URL + "/sendMessage", data={"chat_id": chat_id, "text": text})


def send_line_message(reply_token, text):
    requests.post(
        "https://api.line.me/v2/bot/message/reply",
        headers={"Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}", "Content-Type": "application/json"},
        json={"replyToken": reply_token, "messages": [{"type": "text", "text": text}]}
    )


def verify_line_signature(body, signature):
    if not LINE_CHANNEL_SECRET:
        return False
    expected = base64.b64encode(
        hmac.new(LINE_CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    ).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def handle_cancel(user_key):
    return (
        handle_cancel_expense_delete(user_key)
        or handle_cancel_trip_delete(user_key)
        or "Nothing to cancel.\n目前沒有等待取消的操作。"
    )


def handle_text_message(user_key, platform, text):
    text = normalize_command_text(text)

    if is_cancel_command(text):
        return handle_cancel(user_key)
    if is_yesdelete_command(text):
        return handle_yesdelete_expense(user_key)
    if is_confirmdelete_command(text):
        return handle_confirm_delete_trip(user_key)
    if is_start_command(text):
        return handle_start()
    if is_help_command(text):
        return handle_help()
    if is_status_command(text):
        return handle_status(user_key)
    if is_rate_command(text):
        return handle_rate(text)
    if is_listprice_command(text):
        return handle_listprice()
    if is_newtrip_command(text):
        return handle_newtrip(user_key, text)
    if is_usedefault_command(text):
        return handle_usedefault(user_key)
    if is_mytrips_command(text):
        return handle_mytrips(user_key)
    if is_deletetrip_command(text):
        return handle_deletetrip(user_key, text)
    if is_spent_command(text):
        return handle_spent(user_key, platform, text)
    if is_expense_command(text):
        return handle_expense(user_key)
    if is_budget_command(text):
        return handle_budget(user_key, text)
    if is_recent_command(text):
        return handle_recent(user_key, text)
    if is_deleteexpense_command(text):
        return handle_deleteexpense(user_key, text)
    if is_resettrip_command(text):
        return handle_resettrip()
    if is_addprice_command(text):
        return handle_addprice(text)
    if is_updateprice_command(text):
        return handle_updateprice(text)
    if is_deleteprice_command(text):
        return handle_deleteprice(text)
    if is_twprice_command(text):
        return handle_twprice(user_key, text)

    return handle_price_compare(user_key, text) or handle_help()


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
    reply = handle_text_message(f"telegram:{chat_id}", "Telegram", message.get("text", ""))
    send_telegram_message(chat_id, reply)
    return jsonify({"ok": True})


@app.route("/line-webhook", methods=["POST"])
def line_webhook():
    body = request.get_data()
    signature = request.headers.get("X-Line-Signature", "")

    if not verify_line_signature(body, signature):
        return jsonify({"error": "Invalid signature"}), 403

    for event in request.get_json().get("events", []):
        if event.get("type") != "message":
            continue
        message = event.get("message", {})
        if message.get("type") != "text":
            continue

        user_id = event.get("source", {}).get("userId", "unknown")
        reply = handle_text_message(f"line:{user_id}", "LINE", message.get("text", ""))
        send_line_message(event.get("replyToken"), reply)

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

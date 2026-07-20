import json
import os
import urllib.request
import urllib.error
import sys

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

REST_URL = f"{SUPABASE_URL}/rest/v1/credits_status?id=eq.1"


def supabase_get():
    req = urllib.request.Request(
        REST_URL + "&select=credits_claimed_today,last_update_id",
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        },
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
        return data[0]


def supabase_patch(fields):
    body = json.dumps(fields).encode()
    req = urllib.request.Request(
        REST_URL,
        data=body,
        method="PATCH",
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    urllib.request.urlopen(req)


def telegram_get_updates(offset):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}"
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())


def telegram_send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    body = json.dumps({"chat_id": CHAT_ID, "text": text}).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"

    if mode == "reset":
        supabase_patch({"credits_claimed_today": False})
        print("Reset done for the new day.")
        return

    status = supabase_get()
    claimed = status["credits_claimed_today"]
    last_update_id = status["last_update_id"] or 0

    updates = telegram_get_updates(last_update_id + 1)
    highest_seen = last_update_id

    for update in updates.get("result", []):
        highest_seen = max(highest_seen, update["update_id"])
        message = update.get("message", {})
        text = message.get("text", "").strip().lower()
        sender_id = str(message.get("chat", {}).get("id", ""))
        if sender_id == str(CHAT_ID) and "done" in text:
            claimed = True

    if highest_seen != last_update_id or claimed != status["credits_claimed_today"]:
        supabase_patch(
            {"credits_claimed_today": claimed, "last_update_id": highest_seen}
        )

    if not claimed:
        telegram_send_message(
            "Reminder: claim your free daily credits on Kling, Pika, Hailuo, and Seedance. Reply 'done' once claimed."
        )
    else:
        print("Already claimed today. Staying quiet.")


if __name__ == "__main__":
    main()

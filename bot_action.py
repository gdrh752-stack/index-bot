import os, sys, requests, datetime as dt
from pytz import timezone

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
INDEX     = os.getenv("INDEX", "SENSEX")

if not BOT_TOKEN or not CHAT_ID:
    print("ENV missing: BOT_TOKEN/CHAT_ID")
    sys.exit(1)

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send(text, pin=True):
    r = requests.post(f"{API}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
                      timeout=20)
    print("send status:", r.status_code, r.text)
    if pin and r.ok:
        msg_id = r.json().get("result", {}).get("message_id")
        if msg_id:
            p = requests.post(f"{API}/pinChatMessage",
                              data={"chat_id": CHAT_ID, "message_id": msg_id, "disable_notification": True},
                              timeout=20)
            print("pin status:", p.status_code, p.text)

def run():
    ist = timezone("Asia/Kolkata")
    now = dt.datetime.now(ist).strftime("%d-%m-%Y %H:%M")
    # yaha tum apna price fetch lagate ho; abhi demo ke liye dummy:
    price_decimal = "??"   # <- yaha real scraping/quote aa jayega
    text = f"<b>{INDEX}</b> : <b>{price_decimal}</b>\n<i>{now} IST</i>"
    send(text, pin=True)

if __name__ == "__main__" :
    run()

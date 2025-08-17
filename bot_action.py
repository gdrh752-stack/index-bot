import os, sys, datetime as dt
import requests
from zoneinfo import ZoneInfo  # Py 3.11+

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
INDEX     = (os.getenv("INDEX") or "").strip().upper()

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# hamare index -> Yahoo Finance symbol
YAHOO_SYMBOLS = {
    "SENSEX":   "^BSESN",   # BSE Sensex
    "HANGSENG": "^HSI",     # Hang Seng
    "TAIWAN":   "^TWII",    # Taiwan Weighted (TAIEX)
    "KOSPI":    "^KS11",    # KOSPI
    "DAX":      "^GDAXI",   # DAX
    "DOWJONES": "^DJI",     # Dow Jones
}

def ist_now_str():
    now_ist = dt.datetime.now(ZoneInfo("Asia/Kolkata"))
    return now_ist.strftime("%d-%m-%Y %H:%M IST")

def send_message(text: str, pin: bool = True):
    try:
        r = requests.post(f"{API}/sendMessage",
                          data={"chat_id": CHAT_ID, "text": text}, timeout=20)
        print("sendMessage:", r.status_code, r.text)
        if pin:
            data = r.json()
            if data.get("ok") and "message_id" in data["result"]:
                mid = data["result"]["message_id"]
                pr = requests.post(f"{API}/pinChatMessage",
                                   data={"chat_id": CHAT_ID, "message_id": mid,
                                         "disable_notification": True},
                                   timeout=20)
                print("pinChatMessage:", pr.status_code, pr.text)
    except Exception as e:
        print("Telegram error:", repr(e))

def get_price_from_yahoo(symbol: str):
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbol}"
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        print("Yahoo GET:", r.status_code)
        if r.status_code != 200:
            return None
        js = r.json()
        res = js.get("quoteResponse", {}).get("result", [])
        if not res:
            return None
        q = res[0]
        price = q.get("regularMarketPrice") or q.get("postMarketPrice") or q.get("regularMarketPreviousClose")
        return float(price) if price is not None else None
    except Exception as e:
        print("Yahoo error:", repr(e))
        return None

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("ENV missing: BOT_TOKEN/CHAT_ID"); sys.exit(1)
    if INDEX not in YAHOO_SYMBOLS:
        send_message(f"{INDEX or 'INDEX'} : ??\n{ist_now_str()}"); return

    symbol = YAHOO_SYMBOLS[INDEX]
    print("Fetching:", INDEX, "->", symbol)

    price = get_price_from_yahoo(symbol)
    if price is None:
        send_message(f"{INDEX} : ??\n{ist_now_str()}"); return

    two_dec = f"{price:.2f}"
    dec_part = two_dec.split(".")[1]  # exactly 2 digits
    msg = f"{INDEX} : {dec_part}\n{ist_now_str()}"
    send_message(msg, pin=True)

if __name__ == "__main__":
    print("Job start:", INDEX)
    main()

import os, json, time, requests
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID   = os.environ["CHAT_ID"]
INDEX     = os.environ.get("INDEX","SENSEX").upper().strip()

# Map: INDEX -> (nice name, Yahoo symbol)
MAP = {
    "SENSEX":   ("SENSEX",   "^BSESN"),
    "HANGSENG": ("HANGSENG", "^HSI"),
    "TAIWAN":   ("TAIWAN",   "^TWII"),
    "KOSPI":    ("KOSPI",    "^KS11"),
    "DAX":      ("DAX",      "^GDAXI"),
    "DOW":      ("DOW",      "^DJI"),
    "DOWJONES": ("DOW",      "^DJI"),
}

nice, symbol = MAP.get(INDEX, ("SENSEX","^BSESN"))

def yahoo_price(sym):
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={sym}"
    r = requests.get(url, timeout=15, headers={"User-Agent":"Mozilla/5.0"})
    r.raise_for_status()
    data = r.json()["quoteResponse"]["result"]
    if not data:
        return None
    price = data[0].get("regularMarketPrice")
    return float(price) if price is not None else None

def last_two_decimals(num):
    # price -> last two digits after decimal, always 2 chars
    x = int(round(num * 100)) % 100
    return f"{x:02d}"

def send_and_pin(text):
    api = f"https://api.telegram.org/bot{BOT_TOKEN}"
    # send
    m = requests.post(f"{api}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True},
                      timeout=15).json()
    # pin
    try:
        msg_id = m["result"]["message_id"]
        requests.post(f"{api}/pinChatMessage",
                      data={"chat_id": CHAT_ID, "message_id": msg_id},
                      timeout=15)
    except Exception:
        pass

def ist_now_str():
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist).strftime("%d-%m-%Y %H:%M IST")

def main():
    try:
        p = yahoo_price(symbol)
    except Exception as e:
        p = None

    if p is None:
        body = f"{nice} : ??\n{ist_now_str()}"
    else:
        tail = last_two_decimals(p)
        body = f"{nice} : {tail}\n{ist_now_str()}"

    send_and_pin(body)

if __name__ == "__main__":
    main()

import os, time
import requests
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode

BOT_TOKEN = os.environ["BOT_TOKEN"].strip()
CHAT_ID   = os.environ["CHAT_ID"].strip()
INDEX     = os.environ["INDEX"].strip().upper()

SYMBOLS = {
    "TAIWAN":   "^TWII",
    "KOSPI":    "^KS11",
    "HANGSENG": "^HSI",
    "SENSEX":   "^BSESN",
    "DAX":      "^GDAXI",
    "DOWJONES": "^DJI",
}

UA = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
}

def http_get(url, params=None, timeout=12):
    # simple helper with headers
    return requests.get(url, params=params, headers=UA, timeout=timeout)

def fetch_price_from_yahoo(symbol, retries=6, pause=2.5):
    """
    Robust fetch:
      - query1 and query2 दोनों try
      - params से caret सही encode होता है
      - fallback: previousClose (market बंद होने पर)
    """
    hosts = ["https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com"]
    last_err = None
    for attempt in range(1, retries + 1):
        for host in hosts:
            try:
                url = f"{host}/v7/finance/quote"
                r = http_get(url, params={"symbols": symbol})
                if r.status_code != 200:
                    last_err = f"HTTP {r.status_code}"
                    continue
                data = r.json()
                res = data.get("quoteResponse", {}).get("result", [])
                if not res:
                    last_err = "empty result"
                    continue
                q = res[0]
                px = q.get("regularMarketPrice")
                if px is None:
                    px = q.get("postMarketPrice") or q.get("preMarketPrice") or q.get("regularMarketPreviousClose")
                if px is None:
                    last_err = "no price field"
                    continue
                return float(px)
            except Exception as e:
                last_err = str(e)
        time.sleep(pause)
    raise RuntimeError(f"fetch failed: {last_err}")

def last_two_decimals(number: float) -> str:
    s = f"{number:.2f}"          # ensures 2 decimals
    return s.split(".")[1]       # "85" from "25176.85"

def tg_send(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()["result"]["message_id"]

def tg_pin(mid: int):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/pinChatMessage"
    payload = {"chat_id": CHAT_ID, "message_id": mid, "disable_notification": True}
    # pin fail होने पर job fail मत करो
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception:
        pass

def main():
    if INDEX not in SYMBOLS:
        raise ValueError(f"Unknown INDEX: {INDEX}")

    symbol = SYMBOLS[INDEX]
    try:
        price = fetch_price_from_yahoo(symbol)
        two = last_two_decimals(price)
        ist = timezone(timedelta(hours=5, minutes=30))
        ts  = datetime.now(ist).strftime("%d-%m-%Y %H:%M IST")
        msg = f"{INDEX} : {two}\n{ts}"
        mid = tg_send(msg)
        tg_pin(mid)
        print("OK:", msg)
    except Exception as e:
        # Error detail group में भेज दो (taaki samajh aaye क्या टूटा)
        err = f"⚠️ {INDEX} fetch error: {e}"
        try:
            tg_send(err)
        finally:
            # workflow को hard-fail ना कराओ—silent success so that अगला schedule चले
            print(err)

if __name__ == "__main__":
    main()

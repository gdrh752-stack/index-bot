import os, sys, datetime as dt
import requests
from zoneinfo import ZoneInfo

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
INDEX     = (os.getenv("INDEX") or "").strip().upper()

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

YAHOO_SYMBOLS = {
    "SENSEX":   "^BSESN",
    "HANGSENG": "^HSI",
    "TAIWAN":   "^TWII",
    "KOSPI":    "^KS11",
    "DAX":      "^GDAXI",
    "DOWJONES": "^DJI",
}

UA_HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Connection": "close",
}

def ist_now_str():
    now_ist = dt.datetime.now(ZoneInfo("Asia/Kolkata"))
    return now_ist.strftime("%d-%m-%Y %H:%M IST")

def send_message(text: str, pin: bool = True):
    try:
        r = requests.post(f"{API}/sendMessage",
                          data={"chat_id": CHAT_ID, "text": text}, timeout=25)
        if pin and r.ok:
            mid = r.json().get("result", {}).get("message_id")
            if mid:
                requests.post(f"{API}/pinChatMessage",
                              data={"chat_id": CHAT_ID, "message_id": mid,
                                    "disable_notification": True},
                              timeout=25)
    except Exception as e:
        print("Telegram error:", repr(e))

def _extract_price(q: dict):
    # teen fallback: live -> post -> prev close
    for k in ("regularMarketPrice", "postMarketPrice", "regularMarketPreviousClose"):
        v = q.get(k)
        if v is not None:
            try:
                return float(v)
            except Exception:
                pass
    return None

def fetch_yahoo(symbol: str):
    # try 1: query1
    url1 = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbol}&lang=en-US&region=US"
    # try 2: query2
    url2 = f"https://query2.finance.yahoo.com/v7/finance/quote?symbols={symbol}&lang=en-US&region=US"
    # try 3: chart (kabhi kabhi quote fail ho, chart deta hai)
    url3 = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=1m&lang=en-US&region=US"

    for url in (url1, url2):
        try:
            r = requests.get(url, headers=UA_HDRS, timeout=25)
            print("GET", url.split('/')[2], r.status_code)
            if r.status_code == 200:
                js = r.json()
                res = js.get("quoteResponse", {}).get("result", [])
                if res:
                    p = _extract_price(res[0])
                    if p is not None:
                        return p
        except Exception as e:
            print("quote error:", repr(e))

    # chart fallback
    try:
        r = requests.get(url3, headers=UA_HDRS, timeout=25)
        print("GET chart", r.status_code)
        if r.status_code == 200:
            js = r.json()
            result = js.get("chart", {}).get("result", [])
            if result:
                meta = result[0].get("meta", {})
                p = meta.get("regularMarketPrice") or meta.get("previousClose")
                if p is not None:
                    return float(p)
    except Exception as e:
        print("chart error:", repr(e))

    return None

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("ENV missing"); sys.exit(1)

    sym = YAHOO_SYMBOLS.get(INDEX)
    if not sym:
        send_message(f"{INDEX or 'INDEX'} : ??\n{ist_now_str()}"); return

    print("Fetching:", INDEX, "->", sym)
    price = fetch_yahoo(sym)

    if price is None:
        # last resort: clear message but time pin ho jaye
        send_message(f"{INDEX} : ??\n{ist_now_str()}")
        return

    # exactly 2 digits decimal
    dec = f"{price:.2f}".split(".")[1]
    msg = f"{INDEX} : {dec}\n{ist_now_str()}"
    send_message(msg, pin=True)

if __name__ == "__main__" :
    main()

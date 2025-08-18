import os, time, random
from decimal import Decimal
from datetime import datetime
from zoneinfo import ZoneInfo
import requests

INDEX_SYMBOL = {
    "HANGSENG":  "^HSI",
    "TAIWAN":    "^TWII",
    "KOSPI":     "^KS11",
    "SENSEX":    "^BSESN",
    "DAX":       "^GDAXI",
    "DOWJONES":  "^DJI",
}

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

IST = ZoneInfo("Asia/Kolkata")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID   = os.environ.get("CHAT_ID", "").strip()
INDEX     = os.environ.get("INDEX", "").strip().upper()

def two_decimals_from_price(num) -> str:
    s = format(Decimal(str(num)), "f")
    if "." in s:
        frac = s.split(".", 1)[1]
        return (frac + "00")[:2]
    return "00"

def _headers(symbol):
    return {
        "User-Agent": random.choice(UA_POOL),
        "Accept": "application/json,text/plain,*/*",
        "Connection": "keep-alive",
        "Referer": f"https://finance.yahoo.com/quote/{symbol.replace('^','%5E')}",
        "Accept-Language": "en-US,en;q=0.9",
    }

def fetch_price(symbol: str, max_tries: int = 6):
    """
    Try multiple Yahoo endpoints to avoid 401/429:
      1) v7 quote (query1, query2)
      2) v8 chart (query1, query2)
    Returns float price.
    """
    endpoints = [
        ("https://query1.finance.yahoo.com/v7/finance/quote", {"symbols": symbol}, "v7"),
        ("https://query2.finance.yahoo.com/v7/finance/quote", {"symbols": symbol}, "v7"),
        (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}", {"range":"1d","interval":"1m"}, "v8"),
        (f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}", {"range":"1d","interval":"1m"}, "v8"),
    ]
    attempt = 0
    last_err = None
    while attempt < max_tries:
        for url, params, kind in endpoints:
            attempt += 1
            try:
                r = requests.get(url, params=params, headers=_headers(symbol), timeout=12)
                if r.status_code in (401, 403, 429, 503):
                    # backoff
                    time.sleep(1.0 + 0.6*attempt + random.uniform(0,0.7))
                    continue
                r.raise_for_status()
                data = r.json()
                if kind == "v7":
                    res = data.get("quoteResponse", {}).get("result", [])
                    if not res:
                        raise ValueError("empty quote result")
                    price = res[0].get("regularMarketPrice")
                    if price is None:
                        raise ValueError("no regularMarketPrice")
                    return float(price)
                else:
                    res = data.get("chart", {}).get("result", [])
                    if not res:
                        raise ValueError("empty chart result")
                    meta = res[0].get("meta", {}) or {}
                    price = meta.get("regularMarketPrice")
                    if price is None:
                        # fallback: last non-null close from indicators
                        ind = res[0].get("indicators", {}).get("quote", [])
                        closes = ind[0].get("close") if ind else None
                        if closes:
                            for v in reversed(closes):
                                if v is not None:
                                    price = v
                                    break
                    if price is None:
                        raise ValueError("no price in chart")
                    return float(price)
            except Exception as e:
                last_err = e
                time.sleep(0.6 + 0.4*attempt + random.uniform(0,0.5))
    raise RuntimeError(f"Yahoo fetch failed after retries: {last_err}")

def tg(method, payload):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    r = requests.post(url, json=payload, timeout=12)
    r.raise_for_status()
    return r.json()

def send_and_pin(text):
    m = tg("sendMessage", {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
        "parse_mode": "HTML",
    })
    mid = m["result"]["message_id"]
    tg("pinChatMessage", {
        "chat_id": CHAT_ID,
        "message_id": mid,
        "disable_notification": True
    })

def main():
    if INDEX not in INDEX_SYMBOL:
        raise SystemExit(f"Unknown INDEX '{INDEX}'. Expected one of: {', '.join(INDEX_SYMBOL.keys())}")
    if not BOT_TOKEN or not CHAT_ID:
        raise SystemExit("BOT_TOKEN / CHAT_ID missing.")

    symbol = INDEX_SYMBOL[INDEX]

    try:
        price = fetch_price(symbol)
    except Exception as e:
        msg = f"⚠️ {INDEX} fetch error: {e}"
        send_and_pin(msg)
        print(msg)
        return

    last2 = two_decimals_from_price(price)
    stamp = datetime.now(IST).strftime("%d-%m-%Y %H:%M IST")
    text = f"{INDEX} : <b>{last2}</b>\n{stamp}"
    send_and_pin(text)
    print(f"Posted: {text}")

if __name__ == "__main__":
    main()

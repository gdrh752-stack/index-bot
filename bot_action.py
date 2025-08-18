import os
import time
import json
import random
from decimal import Decimal
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

# ---------- Config ----------

YA_SYMBOL = {
    "HANGSENG":  "^HSI",    # Hang Seng Index
    "TAIWAN":    "^TWII",   # TAIEX (Taiwan Weighted)
    "KOSPI":     "^KS11",   # KOSPI
    "SENSEX":    "^BSESN",  # BSE Sensex
    "DAX":       "^GDAXI",  # DAX
    "DOWJONES":  "^DJI",    # Dow Jones Industrial Average
}

YA_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

IST = ZoneInfo("Asia/Kolkata")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID   = os.environ.get("CHAT_ID", "").strip()
INDEX     = os.environ.get("INDEX", "").strip().upper()  # e.g., HANGSENG

# ---------- Helpers ----------

def two_decimals_from_price(price_num) -> str:
    """
    Decimal ko exact string me convert karke fractional part ke first 2 digits
    return karta hai. Koi rounding nahi, pure truncate.
    Examples:
      25176.85  -> "85"
      25176.849 -> "84"
      123.4     -> "40"
      123.0     -> "00"
    """
    s = format(Decimal(str(price_num)), "f")
    if "." in s:
        frac = s.split(".", 1)[1]
        return (frac + "00")[:2]
    return "00"

def fetch_yahoo_price(symbol: str, max_tries: int = 4, base_wait: float = 1.2):
    params = {"symbols": symbol}
    for attempt in range(1, max_tries + 1):
        try:
            headers = {"User-Agent": random.choice(UA_LIST)}
            r = requests.get(YA_URL, params=params, headers=headers, timeout=12)
            if r.status_code == 429:
                # Rate limited — thoda wait + retry
                time.sleep(base_wait * attempt + random.uniform(0, 0.8))
                continue
            r.raise_for_status()
            data = r.json()
            quote = data["quoteResponse"]["result"]
            if not quote:
                raise ValueError("Empty quote result")
            price = quote[0].get("regularMarketPrice")
            if price is None:
                raise ValueError("No regularMarketPrice in quote")
            return price
        except Exception as e:
            if attempt == max_tries:
                raise
            time.sleep(base_wait * attempt + random.uniform(0, 0.8))
    raise RuntimeError("unreachable")

def tg_api(method: str, payload: dict):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    r = requests.post(url, json=payload, timeout=12)
    r.raise_for_status()
    return r.json()

def send_and_pin(text: str):
    msg = tg_api("sendMessage", {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
        "parse_mode": "HTML"
    })
    mid = msg["result"]["message_id"]
    # Pin silently
    tg_api("pinChatMessage", {
        "chat_id": CHAT_ID,
        "message_id": mid,
        "disable_notification": True
    })

# ---------- Main ----------

def main():
    if INDEX not in YA_SYMBOL:
        raise SystemExit(f"Unknown INDEX '{INDEX}'. Use one of: {', '.join(YA_SYMBOL.keys())}")

    if not BOT_TOKEN or not CHAT_ID:
        raise SystemExit("BOT_TOKEN / CHAT_ID missing in env")

    symbol = YA_SYMBOL[INDEX]

    try:
        price = fetch_yahoo_price(symbol)
    except Exception as e:
        warn = f"⚠️ {INDEX} fetch error: {e}"
        send_and_pin(warn)
        print(warn)
        return

    last2 = two_decimals_from_price(price)

    # Timestamp in IST
    now_ist = datetime.now(IST)
    stamp = now_ist.strftime("%d-%m-%Y %H:%M IST")

    text = f"{INDEX} : <b>{last2}</b>\n{stamp}"
    send_and_pin(text)
    print(f"Posted: {text}")

if __name__ == "__main__":
    main()

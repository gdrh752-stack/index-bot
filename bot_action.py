import os, time, datetime as dt, json, textwrap
import requests

BOT_TOKEN  = os.environ["BOT_TOKEN"]
CHAT_ID    = os.environ["CHAT_ID"]
INDEX      = os.environ.get("INDEX", "").upper().strip()   # HSI, KS11, TWII, BSESN, DAX, DJI
TD_API_KEY = os.environ["TD_API_KEY"]

# Twelve Data symbols map (safe defaults)
SYMBOLS = {
    "HANGSENG": "HSI",
    "KOSPI":    "KS11",
    "TAIWAN":   "TWII",
    "SENSEX":   "BSESN",
    "DAX":      "DAX",
    "DOWJONES": "DJI",
    "DOW":      "DJI",
}

SYMBOL = SYMBOLS.get(INDEX, INDEX)

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

def tg_send(text, disable_notification=False):
    r = requests.post(f"{TG_API}/sendMessage", json={
        "chat_id": CHAT_ID,
        "text": text,
        "disable_notification": disable_notification,
    }, timeout=20)
    r.raise_for_status()
    return r.json()["result"]["message_id"]

def tg_pin(message_id):
    r = requests.post(f"{TG_API}/pinChatMessage", json={
        "chat_id": CHAT_ID,
        "message_id": message_id,
        "disable_notification": True
    }, timeout=20)
    # ignore pin errors (not admin etc.)
    try:
        r.raise_for_status()
    except Exception:
        pass

def ist_now():
    # UTC+5:30
    return dt.datetime.utcnow() + dt.timedelta(hours=5, minutes=30)

def fetch_price(symbol, retries=5, base_sleep=5):
    """
    Robust Twelve Data fetch with backoff.
    We call the lightweight /price endpoint; when market is closed, it returns last price.
    """
    url = "https://api.twelvedata.com/price"
    params = {"symbol": symbol, "apikey": TD_API_KEY}
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=15)
            # Handle 429 and other errors explicitly
            if r.status_code == 429:
                # Too many requests -> backoff harder
                sleep_for = base_sleep * (2 ** i)
                time.sleep(sleep_for)
                continue
            r.raise_for_status()
            data = r.json()
            if "price" in data:
                # return string price like "25176.85"
                return data["price"]
            # sometimes TwelveData returns {'status':'error','message':...}
            # slow down and retry
        except Exception:
            pass
        time.sleep(base_sleep * (i + 1))
    return None

def last_two_digits_from_price(price_str):
    """
    Keep only the last two digits after removing decimals and separators.
    Example: "25176.85" -> "85"
    """
    raw = "".join(ch for ch in price_str if ch.isdigit())
    if not raw:
        return None
    return raw[-2:].zfill(2)

def main():
    now_ist = ist_now()
    when = now_ist.strftime("%d-%m-%Y %H:%M IST")

    price = fetch_price(SYMBOL)
    if not price:
        tg_send(f"⚠️ {INDEX} fetch error: no price (rate/conn).")
        return

    last2 = last_two_digits_from_price(price)
    if not last2:
        tg_send(f"⚠️ {INDEX} parse error.")
        return

    text = f"{INDEX} : {last2}\n{when}"
    mid = tg_send(text)
    tg_pin(mid)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # absolute last-chance guard so Action shows a message instead of hard fail
        try:
            tg_send(f"⚠️ {INDEX} unexpected error: {e}")
        finally:
            raise

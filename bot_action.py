import os, time, requests
from datetime import datetime
import pytz
import yfinance as yf

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
INDEX     = (os.getenv("INDEX") or "").strip().upper()   # e.g. HANGSENG, KOSPI, SENSEX, DAX, DOWJONES, TAIWAN

# Map: INDEX -> (Yahoo symbol, Display name)
YMAP = {
    "SENSEX":   ("^BSESN",  "SENSEX"),
    "HANGSENG": ("^HSI",    "HANG SENG"),
    "KOSPI":    ("^KS11",   "KOSPI"),
    "TAIWAN":   ("^TWII",   "TAIWAN"),
    "DAX":      ("^GDAXI",  "DAX"),
    "DOWJONES": ("^DJI",    "DOWJONES"),
}

IST = pytz.timezone("Asia/Kolkata")

def get_last_two_digits(price: float) -> str:
    # integer part ke last 2 digits, zero-padded
    n = int(abs(price)) % 100
    return f"{n:02d}"

def fetch_price(symbol: str) -> float:
    """
    Robust fetch with small retries. Prefer fast_info, else history.
    """
    attempts = 4
    for i in range(attempts):
        try:
            t = yf.Ticker(symbol)
            # 1) super-fast path
            p = getattr(t.fast_info, "last_price", None)
            if p is not None and p > 0:
                return float(p)

            # 2) recent candle
            df = t.history(period="1d", interval="1m")
            if df is not None and not df.empty:
                # last non-NaN close
                close = df["Close"].dropna()
                if not close.empty:
                    return float(close.iloc[-1])

            # 3) 1d daily close fallback
            df = t.history(period="5d", interval="1d")
            if df is not None and not df.empty:
                close = df["Close"].dropna()
                if not close.empty:
                    return float(close.iloc[-1])
        except Exception as e:
            # mild backoff (avoid 429)
            time.sleep(2 + i)
    raise RuntimeError("no price (rate/conn).")

def send_msg(text: str, disable_notification: bool=False):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": text
    }, timeout=30)
    r.raise_for_status()
    return r.json()["result"]["message_id"]

def pin_message(message_id: int):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/pinChatMessage"
    # silent pin (no push)
    r = requests.post(url, json={
        "chat_id": CHAT_ID,
        "message_id": message_id,
        "disable_notification": True
    }, timeout=30)
    # ignore pin errors silently
    try:
        r.raise_for_status()
    except Exception:
        pass

def main():
    if INDEX not in YMAP:
        # safety: agar env galat hai
        send_msg(f"⚠️ INDEX env invalid: '{INDEX}'")
        return

    symbol, display = YMAP[INDEX]

    try:
        price = fetch_price(symbol)
        last2 = get_last_two_digits(price)
        now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M IST")
        text = f"{display} : {last2}\n{now_ist}"
        mid = send_msg(text)
        pin_message(mid)
    except Exception as e:
        # clear & helpful error
        err = str(e)
        mid = send_msg(f"⚠️ {display} fetch error: {err}")
        # don't pin errors

if __name__ == "__main__":
    main()

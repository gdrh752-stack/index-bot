import os, time, datetime as dt
from zoneinfo import ZoneInfo

import requests
import yfinance as yf
import pandas as pd


# ---------- Config ----------
INDEX = (os.getenv("INDEX") or "").strip().upper()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Map INDEX -> Yahoo Finance ticker
TICKERS = {
    "TAIWAN":  "^TWII",     # Taiwan Weighted (TAIEX)
    "KOSPI":   "^KS11",
    "HANGSENG":"^HSI",
    "SENSEX":  "^BSESN",
    "DAX":     "^GDAXI",
    "DOWJONES":"^DJI",
}

# ---------- Helpers ----------
def send_message(text: str, pin: bool = True):
    if not (BOT_TOKEN and CHAT_ID):
        raise RuntimeError("BOT_TOKEN or CHAT_ID missing")

    api = f"https://api.telegram.org/bot{BOT_TOKEN}"
    r = requests.post(f"{api}/sendMessage",
                      json={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True})
    r.raise_for_status()
    msg = r.json().get("result", {})
    if pin and msg.get("message_id"):
        try:
            requests.post(f"{api}/pinChatMessage",
                          json={"chat_id": CHAT_ID, "message_id": msg["message_id"], "disable_notification": True})
        except Exception:
            pass  # not admin or pin disabled – ignore


def last_two_decimals(number) -> str:
    """
    Exactly last two digits of the decimal part, zero-padded.
    25176.85 -> '85', 25176.8 -> '80', 25176.00 -> '00'
    """
    try:
        s = f"{float(number):.2f}"
    except Exception:
        return "??"
    dec = s.split(".")[1] if "." in s else "00"
    if len(dec) == 1:
        dec = dec + "0"
    return dec[:2]


def fetch_price_yf(ticker: str):
    """
    Try multiple ways with yfinance:
    1) fast_info.last_price
    2) history 1m (tail 1)
    3) info['regularMarketPrice']
    Returns float or None
    """
    tk = yf.Ticker(ticker)

    # 1) fast_info
    try:
        lp = getattr(tk, "fast_info", {}).get("last_price")
        if lp: 
            return float(lp)
    except Exception:
        pass

    # 2) intraday last candle
    try:
        df = tk.history(period="1d", interval="1m", auto_adjust=False, prepost=False)
        if isinstance(df, pd.DataFrame) and not df.empty:
            v = df["Close"].dropna().tail(1)
            if not v.empty:
                return float(v.iloc[0])
    except Exception:
        pass

    # 3) regularMarketPrice
    try:
        info = tk.info
        v = info.get("regularMarketPrice")
        if v:
            return float(v)
    except Exception:
        pass

    # 4) Previous close (fallback)
    try:
        df = tk.history(period="5d", interval="1d", auto_adjust=False, prepost=False)
        if isinstance(df, pd.DataFrame) and not df.empty:
            v = df["Close"].dropna().tail(1)
            if not v.empty:
                return float(v.iloc[0])
    except Exception:
        pass

    return None


def fetch_with_retry(ticker: str, attempts: int = 5, delay_sec: int = 5):
    last_val = None
    for i in range(1, attempts + 1):
        try:
            val = fetch_price_yf(ticker)
            if val is not None and float(val) > 0:
                return float(val), False  # value, is_fallback=False
        except Exception:
            pass
        last_val = val if 'val' in locals() else None
        time.sleep(delay_sec)

    # Couldn’t fetch live; try explicit fallback (previous close already attempted inside)
    if last_val is None:
        last_val = fetch_price_yf(ticker)
    return (float(last_val) if last_val else None), True  # value, is_fallback=True if we got here


def main():
    if INDEX not in TICKERS:
        raise RuntimeError(f"Unknown INDEX '{INDEX}'. Valid: {', '.join(TICKERS)}")

    ticker = TICKERS[INDEX]

    value, used_fallback = fetch_with_retry(ticker)

    ist = dt.datetime.now(ZoneInfo("Asia/Kolkata"))
    stamp = ist.strftime("%d-%m-%Y %H:%M IST")

    if value is None:
        # Total failure – very rare with above fallbacks
        send_message(f"⚠️ {INDEX} update failed after retries.", pin=False)
        return

    two = last_two_decimals(value)

    # Compose message
    head = f"{INDEX} : {two}"
    body = f"{stamp}"
    trailer = "\n(⚠️ fallback used)" if used_fallback else ""
    text = f"{head}\n{body}{trailer}"

    send_message(text, pin=True)
    print(text)


if __name__ == "__main__":
    main()

import os, math, time, json, requests
import yfinance as yf

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID   = os.environ["CHAT_ID"]
INDEX     = os.environ["INDEX"].upper().strip()

# INDEX -> Yahoo tickers
TICKERS = {
    "SENSEX":    "^BSESN",
    "HANGSENG":  "^HSI",
    "KOSPI":     "^KS11",
    "TAIWAN":    "^TWII",
    "DAX":       "^GDAXI",
    "DOWJONES":  "^DJI",
}

if INDEX not in TICKERS:
    raise SystemExit(f"Unknown INDEX '{INDEX}'. Use one of: {', '.join(TICKERS)}")

ticker = TICKERS[INDEX]

def get_price(t):
    """Try fast quote; fallback to history(1m). Return float price."""
    tk = yf.Ticker(t)
    # 1) fast info
    p = tk.fast_info.last_price
    if p is None:
        # 2) regularMarketPrice
        info = tk.info or {}
        p = info.get("regularMarketPrice")
    if p is None:
        # 3) last 1 minute close
        hist = tk.history(period="1d", interval="1m")
        if not hist.empty:
            p = float(hist["Close"].iloc[-1])
    if p is None:
        raise RuntimeError("no price")
    return float(p)

def two_decimals(price):
    """Decimal ke baad ke exact 2 digits (floor), e.g. 25176.85 -> 85, 123.00 -> 00"""
    frac = price - math.floor(price)
    val  = int(math.floor(frac * 100 + 1e-6))  # 1e-6 to avoid 0.849999 → 84
    return f"{val:02d}"

def send_message(text, disable_notification=False):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_notification": disable_notification
    }
    r = requests.post(url, data=data, timeout=20)
    r.raise_for_status()
    return r.json()["result"]["message_id"]

def pin_message(message_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/pinChatMessage"
    data = {"chat_id": CHAT_ID, "message_id": message_id, "disable_notification": True}
    requests.post(url, data=data, timeout=20)

def main():
    tries = 0
    last_err = None
    while tries < 3:
        tries += 1
        try:
            price = get_price(ticker)
            num   = two_decimals(price)
            # IST time stamp
            ist_time = time.strftime("%d-%m-%Y %H:%M IST", time.gmtime(time.time() + 19800))
            text = f"<b>{INDEX.replace('DOWJONES','DOW JONES')}</b> : <b>{num}</b>\n{ist_time}"
            mid  = send_message(text)
            pin_message(mid)
            return
        except Exception as e:
            last_err = str(e)
            time.sleep(6)  # short backoff
    # fail notice (quiet, no pin)
    send_message(f"⚠️ {INDEX.replace('DOWJONES','DOW JONES')} fetch error: {last_err}", disable_notification=True)

if __name__ == "__main__" :
    main()

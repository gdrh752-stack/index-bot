import os, time, math, requests
import yfinance as yf

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
INDEX     = (os.getenv("INDEX") or "").upper().strip()

# Yahoo symbols map
YAHOO = {
    "TAIWAN":   "^TWII",   # TAIEX
    "KOSPI":    "^KS11",
    "HANGSENG": "^HSI",
    "SENSEX":   "^BSESN",
    "DAX":      "^GDAXI",
    "DOWJONES": "^DJI",
    "DOW":      "^DJI",    # fallback
}

if INDEX not in YAHOO:
    raise SystemExit(f"Unknown INDEX '{INDEX}'. Allowed: {', '.join(YAHOO)}")

SYMBOL = YAHOO[INDEX]

def send_message(text: str, pin: bool = True):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": CHAT_ID, "text": text})
    r.raise_for_status()
    if pin:
        msg_id = r.json()["result"]["message_id"]
        # Best-effort pin; ignore if rights not available
        try:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/pinChatMessage",
                json={"chat_id": CHAT_ID, "message_id": msg_id, "disable_notification": True},
                timeout=10
            )
        except Exception:
            pass

def last_trade_price(symbol: str) -> float | None:
    """
    Try multiple safe ways to get a sane last price.
    Returns float or None.
    """
    tk = yf.Ticker(symbol)

    # 1) fast_info last price
    try:
        p = tk.fast_info.get("lastPrice")
        if p and math.isfinite(p):
            return float(p)
    except Exception:
        pass

    # 2) recent 1d candles (1m/2m interval)
    for interval in ("1m", "2m", "5m"):
        try:
            df = tk.history(period="1d", interval=interval, auto_adjust=False)
            if df is not None and not df.empty:
                val = float(df["Close"].dropna().iloc[-1])
                if math.isfinite(val):
                    return val
        except Exception:
            pass

    # 3) fallback to info (slower)
    try:
        info = tk.info or {}
        p = info.get("regularMarketPrice") or info.get("previousClose")
        if p and math.isfinite(p):
            return float(p)
    except Exception:
        pass

    return None

def two_digits_after_decimal(price: float) -> str:
    """
    Tumhari requirement: 'decimal ke baad ke 2 number'.
    Example: 25176.85 → '85'
    """
    frac = int(abs(round(price * 100)) % 100)
    return f"{frac:02d}"

# -------- main ----------
attempts = 5
delay = 6  # seconds

price = None
for i in range(1, attempts + 1):
    price = last_trade_price(SYMBOL)
    if price is not None:
        break
    time.sleep(delay)

if price is None:
    # Data nahi mila – job ko GREEN rakhte hue sirf warning bhej do
    send_message(f"⚠️ {INDEX} update failed after {attempts} attempts.")
else:
    pair = two_digits_after_decimal(price)
    send_message(f"{INDEX} : {pair}")

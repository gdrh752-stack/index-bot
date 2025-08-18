import os
import time
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timezone
import pytz
import requests

# We will use yfinance but import lazily to control retries
import yfinance as yf

# ---------- Config ----------
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID   = os.getenv("CHAT_ID", "").strip()
INDEX_NAME         = (os.getenv("INDEX", "") or "").strip().upper()  # e.g. SENSEX, HANGSENG, KOSPI, TAIWAN, DAX, DOWJONES

# Yahoo tickers for each index
TICKERS = {
    "SENSEX":   "^BSESN",
    "HANGSENG": "^HSI",
    "KOSPI":    "^KS11",
    "TAIWAN":   "^TWII",
    "DAX":      "^GDAXI",
    "DOWJONES": "^DJI",
}

# Retry config
FETCH_RETRIES = 5
FETCH_DELAYS  = [2, 3, 5, 7, 10]  # seconds

SEND_RETRIES  = 5
SEND_DELAYS   = [2, 3, 5, 7, 10]

IST = pytz.timezone("Asia/Kolkata")


def get_last_two_decimal_digits(price) -> str:
    """
    Return last two digits after decimal (00..99) as string, from a numeric price.
    Uses Decimal to avoid float issues.
    Example: 80597.66 -> '66', 17894.00 -> '00', 15678.1 -> '10'
    """
    d = Decimal(str(price))
    # Format to exactly 2 decimal places without rounding up weirdly
    d2 = d.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    # Separate fractional part
    frac = (d2 - int(d2)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    # frac will be like 0.66, 0.00, 0.10 ...
    # multiply by 100 and take integer
    last2 = int((frac * 100).to_integral_value(rounding=ROUND_DOWN))
    return f"{last2:02d}"


def fetch_price_with_retry(ticker: str):
    """
    Try to fetch last price via yfinance with retries.
    Returns a Decimal-compatible number or None if failed.
    """
    err = None
    for attempt, delay in zip(range(1, FETCH_RETRIES + 1), FETCH_DELAYS + [FETCH_DELAYS[-1]]):
        try:
            t = yf.Ticker(ticker)
            # Fast path: try .fast_info (newer yfinance)
            price = None
            try:
                fi = getattr(t, "fast_info", None)
                if fi:
                    price = fi.get("last_price") or fi.get("lastPrice")
            except Exception:
                price = None

            # Fallback to .info or .history
            if price is None:
                info = {}
                try:
                    info = t.info or {}
                except Exception:
                    info = {}
                price = info.get("regularMarketPrice") or info.get("previousClose")

            if price is None:
                # Last resort: short history (1d), get last close
                hist = t.history(period="1d", interval="1m")
                if not hist.empty:
                    # Prefer last valid close
                    price = hist["Close"].dropna().iloc[-1]

            if price is not None:
                return float(price)

            err = f"No price in attempt {attempt}"
        except Exception as e:
            err = str(e)

        time.sleep(delay)

    print(f"[ERROR] fetch_price_with_retry failed for {ticker}: {err}")
    return None


def send_telegram(text: str) -> bool:
    """
    Send message to Telegram with retries. Returns True if sent.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[ERROR] BOT_TOKEN / CHAT_ID missing.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    last_err = None
    for attempt, delay in zip(range(1, SEND_RETRIES + 1), SEND_DELAYS + [SEND_DELAYS[-1]]):
        try:
            r = requests.post(url, json=payload, timeout=20)
            if r.ok:
                return True
            last_err = f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            last_err = str(e)
        time.sleep(delay)

    print(f"[ERROR] send_telegram failed: {last_err}")
    return False


def main():
    if INDEX_NAME not in TICKERS:
        print(f"[ERROR] Unknown INDEX '{INDEX_NAME}'. Valid: {', '.join(TICKERS.keys())}")
        return

    ticker = TICKERS[INDEX_NAME]
    price = fetch_price_with_retry(ticker)

    if price is None:
        # Don’t spam “??”. Quietly exit; GH Action logs will show error.
        return

    last2 = get_last_two_decimal_digits(price)

    # Timestamp in IST
    now_ist = datetime.now(timezone.utc).astimezone(IST)
    ts = now_ist.strftime("%d-%m-%Y %H:%M IST")

    # Final message (exact style you’re using)
    # Example: "SENSEX : 66\n17-08-2025 16:34 IST"
    msg = f"{INDEX_NAME} : {last2}\n{ts}"

    ok = send_telegram(msg)
    print("[INFO] Sent" if ok else "[WARN] Not sent")


if __name__ == "__main__":
    main()

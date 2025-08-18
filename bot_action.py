# bot_action.py
import os, time, random, requests, re
from datetime import datetime
from urllib.parse import quote

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
INDEX     = os.getenv("INDEX", "").strip().upper()
TD_API_KEY= os.getenv("TD_API_KEY", "").strip()

# ------------ Config ------------
# आपके 6 indices का canonical नाम -> Twelve Data symbol mapping
TD_SYMBOLS = {
    "TAIWAN":   "TAIEX",     # Taiwan TAIEX
    "KOSPI":    "KOSPI",     # Korea KOSPI
    "HANGSENG": "HSI",       # Hang Seng Index
    "SENSEX":   "SENSEX",    # BSE Sensex (कुछ अकाउंट में BSESN/ ^BSESN भी होता है)
    "DAX":      "DAX",       # Germany DAX
    "DOWJONES": "DJI",       # Dow Jones Industrial Average
}
# Yahoo fallback symbols (अगर Twelve Data न दे)
YAHOO_SYMBOLS = {
    "TAIWAN":   "^TWII",     # TAIEX
    "KOSPI":    "^KS11",
    "HANGSENG": "^HSI",
    "SENSEX":   "^BSESN",
    "DAX":      "^GDAXI",
    "DOWJONES": "^DJI",
}

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
]

def _send(msg: str, pin: bool=False):
    base = f"https://api.telegram.org/bot{BOT_TOKEN}"
    requests.post(f"{base}/sendMessage", json={
        "chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML",
        "disable_web_page_preview": True
    }, timeout=20)
    if pin:
        try:
            # pin last message in chat from this bot
            # (Telegram API: need message_id; simplest: getUpdates then pin)
            upd = requests.get(f"{base}/getUpdates", timeout=20).json()
            msgs = [u["message"] for u in upd.get("result", []) if "message" in u]
            if msgs:
                mid = msgs[-1]["message_id"]
                requests.post(f"{base}/pinChatMessage", json={
                    "chat_id": CHAT_ID, "message_id": mid, "disable_notification": True
                }, timeout=20)
        except Exception:
            pass

def twelvedata_latest(symbol: str):
    if not TD_API_KEY: 
        return None
    url = f"https://api.twelvedata.com/time_series?symbol={quote(symbol)}&interval=1min&outputsize=1&apikey={TD_API_KEY}"
    r = requests.get(url, timeout=25)
    js = r.json()
    # expected: {"values":[{"close":"..."}], ...}
    vals = js.get("values") if isinstance(js, dict) else None
    if vals and len(vals)>0 and "close" in vals[0]:
        close = vals[0]["close"]
        return close
    return None

def yahoo_last_price(symbol: str, retries=6):
    # lightweight quote endpoint
    url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{quote(symbol)}?modules=price"
    pause = 5
    for i in range(retries):
        try:
            r = requests.get(url, headers={"User-Agent": random.choice(UA_POOL)}, timeout=25)
            if r.status_code == 429:
                time.sleep(pause); pause = min(pause*2, 60); continue
            js = r.json()
            price = js["quoteSummary"]["result"][0]["price"].get("regularMarketPrice") or \
                    js["quoteSummary"]["result"][0]["price"].get("postMarketPrice")
            if price:
                return str(price["raw"] if isinstance(price, dict) and "raw" in price else price)
        except Exception:
            time.sleep(pause); pause = min(pause*2, 60)
    return None

def extract_two_digits(num_str: str) -> str:
    # num_str like "25176.85" -> "85"
    m = re.search(r"(\d+)(?:\.(\d{1,2}))?$", num_str)
    if not m:
        return None
    frac = m.group(2) or "00"
    if len(frac) == 1: frac += "0"
    return frac[-2:]

def get_index_two_digits(index_name: str):
    name = index_name.upper()
    # 1) Twelve Data
    td_sym = TD_SYMBOLS.get(name)
    if td_sym:
        try:
            price = twelvedata_latest(td_sym)
            if price:
                two = extract_two_digits(str(price))
                if two: return two, "TD"
        except Exception:
            pass
    # 2) Yahoo fallback
    yh_sym = YAHOO_SYMBOLS.get(name)
    if yh_sym:
        price = yahoo_last_price(yh_sym)
        if price:
            two = extract_two_digits(str(price))
            if two: return two, "YF"
    return None, None

def main():
    if not (BOT_TOKEN and CHAT_ID and INDEX):
        raise SystemExit("Missing BOT_TOKEN / CHAT_ID / INDEX")
    digits, src = get_index_two_digits(INDEX)
    ts = datetime.now().strftime("%d-%m-%Y %H:%M IST")
    if digits:
        text = f"<b>{INDEX}</b> : <b>{digits}</b>\n<code>{ts}</code>"
        _send(text, pin=True)
    else:
        _send(f"⚠️ {INDEX} fetch error: no price (rate/conn).", pin=False)
        raise SystemExit(1)

if __name__ == "__main__":
    main()

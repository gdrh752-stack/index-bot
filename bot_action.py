# bot_action.py
import os, sys, math, json, time, datetime as dt
import requests

# --------- ENV -----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
INDEX     = os.getenv("INDEX", "").upper().strip()   # e.g. SENSEX / HSI / KOSPI / DAX / DOW / TAIWAN

if not BOT_TOKEN or not CHAT_ID:
    print("ENV missing"); sys.exit(1)

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# --------- HELPERS ---------
def ist_now():
    return dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(hours=5, minutes=30)))

def send(text, pin=False):
    r = requests.post(f"{API}/sendMessage", data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=20)
    print("send:", r.status_code, r.text)
    if pin and r.ok:
        msg_id = r.json().get("result", {}).get("message_id")
        # unpin-all (ignore errors), then pin latest
        try:
            requests.post(f"{API}/unpinAllChatMessages", data={"chat_id": CHAT_ID}, timeout=10)
        except Exception as _:
            pass
        if msg_id:
            p = requests.post(f"{API}/pinChatMessage", data={"chat_id": CHAT_ID, "message_id": msg_id, "disable_notification": True}, timeout=10)
            print("pin:", p.status_code, p.text)

def pct_str(pct):
    s = f"{pct:.2f}"
    return ("+" if pct>=0 else "") + s

def yahoo_quote(symbol):
    url = "https://query1.finance.yahoo.com/v7/finance/quote"
    r = requests.get(url, params={"symbols": symbol}, timeout=20)
    r.raise_for_status()
    q = r.json()["quoteResponse"]["result"]
    if not q: raise RuntimeError("quote empty")
    x = q[0]
    price = x.get("regularMarketPrice")
    change = x.get("regularMarketChange")
    changep = x.get("regularMarketChangePercent")
    exch_ts = x.get("regularMarketTime")
    return price, change, changep, exch_ts

MAP = {
    "SENSEX": {"label": "Sensex", "yahoo": "^BSESN", "pin": True},
    "HSI":    {"label": "Hang Seng", "yahoo": "^HSI",   "pin": True},
    "KOSPI":  {"label": "KOSPI",     "yahoo": "^KS11",  "pin": True},
    "DAX":    {"label": "DAX",       "yahoo": "^GDAXI", "pin": True},
    "DOW":    {"label": "Dow Jones", "yahoo": "^DJI",   "pin": True},
    "TAIWAN": {"label": "Taiwan",    "yahoo": "^TWII",  "pin": True},
}

def main():
    if INDEX not in MAP:
        send(f"❌ Unknown INDEX: {INDEX}")
        return

    meta = MAP[INDEX]
    price, change, changep, exch_ts = yahoo_quote(meta["yahoo"])

    # IST date/time
    now_ist = ist_now()

    # Special case: Dow ka message raat 01:41 IST ke aas-paas aata hai,
    # to label me previous day dikhana hai (Friday-night issue fix).
    label_date = now_ist.date()
    if INDEX == "DOW" and now_ist.hour < 6:
        label_date = (now_ist - dt.timedelta(days=1)).date()

    # decimal ke baad ke do digit bhi aa jaye (exact)
    # e.g. 80597.66 -> "66"
    dec_two = f"{price:.2f}".split(".")[1] if isinstance(price, (float, int)) else "00"

    txt = (
        f"<b>{meta['label']}</b> : <b>{price:.2f}</b> "
        f"({pct_str(changep)}%)\n"
        f"Date: {label_date.strftime('%d-%b-%Y')}  •  Decimals: <b>{dec_two}</b>"
    )

    send(txt, pin=meta.get("pin", False))

if  __name__  ==  "__main__" :
    main()

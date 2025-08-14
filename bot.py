import os, re, time, json, threading, traceback
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# ====== ENV ======
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
TZ        = os.getenv("TIMEZONE","Asia/Kolkata")
if not BOT_TOKEN or not CHAT_ID:
    print("ENV missing! Add BOT_TOKEN & CHAT_ID in .env")
    raise SystemExit

API = f"https://api.telegram.org/bot{BOT_TOKEN}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

# ====== TELEGRAM HELPERS ======
def tg_send(text:str, disable_notification=False):
    r = requests.post(f"{API}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": text, "disable_notification": str(disable_notification).lower()},
                      timeout=20)
    try:
        return r.json()
    except:
        print("send json err:", r.text)
        return {"ok": False, "raw": r.text}

def tg_pin(message_id:int):
    requests.post(f"{API}/pinChatMessage",
                  data={"chat_id": CHAT_ID, "message_id": message_id, "disable_notification": True},
                  timeout=20)

def post_and_pin(text):
    resp = tg_send(text)
    if resp.get("ok"):
        mid = resp["result"]["message_id"]
        tg_pin(mid)
    else:
        print("send fail:", resp)

# ====== PARSE UTILS ======
PRICE_RE = re.compile(r"\b\d{1,3}(?:,\d{3})*(?:\.\d{2})\b")  # 80,597.66

def first_price_from_html(html:str):
    # return first price-like string found
    m = PRICE_RE.search(html)
    return m.group(0) if m else None

def last_two_after_decimal(price_str:str):
    # "80,597.66" -> "66"
    if "." in price_str:
        return price_str.split(".")[-1][:2]
    return "00"

def get_html(url:str):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text

# ====== SCRAPERS (per your exact links) ======
def sensex():
    # https://www.bseindia.com/sensex/code/16/
    url = "https://www.bseindia.com/sensex/code/16/"
    try:
        html = get_html(url)
        # BSE page shows big price block; generic fallback works well
        price = first_price_from_html(html)
        return price
    except Exception as e:
        print("sensex err:", e)
        return None

def kospi():
    # https://in.investing.com/indices/kospi
    url = "https://in.investing.com/indices/kospi"
    try:
        html = get_html(url)
        # investing pages contain price in many places; first match works
        price = first_price_from_html(html)
        return price
    except Exception as e:
        print("kospi err:", e)
        return None

def hangseng():
    # https://www.hsi.com.hk/eng
    url = "https://www.hsi.com.hk/eng"
    try:
        html = get_html(url)
        price = first_price_from_html(html)
        return price
    except Exception as e:
        print("hangseng err:", e)
        return None

def dax():
    # https://www.boerse-frankfurt.de/en
    url = "https://www.boerse-frankfurt.de/en"
    try:
        html = get_html(url)
        price = first_price_from_html(html)
        return price
    except Exception as e:
        print("dax err:", e)
        return None

def taiwan():
    # Google search result page (can block); best effort
    url = "https://www.google.com/search?q=taiwan+index"
    try:
        html = get_html(url)
        price = first_price_from_html(html)
        return price
    except Exception as e:
        print("taiwan err:", e)
        return None

def dow():
    # Google search result page (can block); best effort
    url = "https://www.google.com/search?q=dow+jones+index"
    try:
        html = get_html(url)
        price = first_price_from_html(html)
        return price
    except Exception as e:
        print("dow err:", e)
        return None

# ====== JOB RUNNER ======
def run_job(name, fetch_fn):
    try:
        price = fetch_fn()
        if not price:
            post_and_pin(f"{name} ({now_str()}): fetch fail")
            return
        two = last_two_after_decimal(price)
        post_and_pin(f"{name} ({now_str()}): {two}")
    except Exception as e:
        print(f"job {name} err:", e)
        traceback.print_exc()
        tg_send(f"{name} ({now_str()}): error")

def now_str():
    # simple stamp IST feel (without tz lib to keep light)
    return datetime.now().strftime("%d-%m-%Y %H:%M")

# ====== SCHEDULER (simple loop) ======
# Times (Mon–Fri) you gave (IST):
SLOTS = [
    ("Taiwan",   "11:30", taiwan),
    ("KOSPI",    "12:10", kospi),
    ("Hang Seng","12:35", hangseng),
    ("Sensex",   "13:35", sensex),     # 1:35 pm per your latest
    ("DAX",      "21:40", dax),
    ("Dow",      "01:41", dow),        # Fri->Sat rollover allowed
]

def should_run_today(name):
    # Mon–Fri for all; Dow भी Fri रात/Sat 01:41 चलता है, allow Sat for Dow:
    wd = datetime.now().weekday()  # Mon=0 ... Sun=6
    if name == "Dow":
        return wd in (0,1,2,3,4,5)  # Mon..Sat (Fri late-night counts as Sat 01:41)
    return wd in (0,1,2,3,4)       # Mon..Fri

def clock_loop():
    posted_cache = set()  # e.g. {"Sensex|2025-08-14 13:35"}
    tg_send("Scheduler ON ✅ (Mon–Fri) → secured group", disable_notification=True)

    while True:
        now = datetime.now()
        hhmm = now.strftime("%H:%M")
        ymd = now.strftime("%Y-%m-%d")
        for name, t, fn in SLOTS:
            if hhmm == t and should_run_today(name):
                key = f"{name}|{ymd} {t}"
                if key not in posted_cache:
                    posted_cache.add(key)
                    threading.Thread(target=run_job, args=(name, fn), daemon=True).start()
        time.sleep(10)  # check every 10s

if __name__ == "__main__":
    # start loop
    print("Scheduler starting…")
    clock_loop()
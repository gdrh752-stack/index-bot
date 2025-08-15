import os, sys, re, requests, datetime as dt
from decimal import Decimal, ROUND_DOWN
from pytz import timezone
from bs4 import BeautifulSoup

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
INDEX     = os.getenv("INDEX", "SENSEX").upper().strip()

if not BOT_TOKEN or not CHAT_ID:
    print("ENV missing: BOT_TOKEN/CHAT_ID")
    sys.exit(1)

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ✅ yaha apni official links भरो (jo tumne bheje the)
#   agar koi link blank "" रहेगा, to Yahoo fallback use होगा.
LINKS = {
    "SENSEX":     os.getenv("URL_SENSEX",     ""),  # e.g. https://www.bseindia.com/sensex/code/…
    "HANG_SENG":  os.getenv("URL_HANG_SENG",  ""),  # e.g. https://www.hsi.com.hk/eng/indices/…
    "KOSPI":      os.getenv("URL_KOSPI",      ""),  # e.g. https://finance.naver.com/sise/sise_index.nhn?code=KOSPI
    "TAIWAN":     os.getenv("URL_TAIWAN",     ""),  # e.g. https://twse.com.tw/…
    "DAX":        os.getenv("URL_DAX",        ""),  # e.g. https://www.deutsche-boerse.com/…
    "DOW_JONES":  os.getenv("URL_DOW_JONES",  ""),  # e.g. https://www.dowjones.com/… OR Yahoo fallback
}

# Yahoo symbols as fallback
YH_SYMBOL = {
    "SENSEX":     "%5EBSESN",  # ^BSESN
    "HANG_SENG":  "%5EHSI",    # ^HSI
    "KOSPI":      "%5EKS11",   # ^KS11
    "TAIWAN":     "%5ETWII",   # ^TWII
    "DAX":        "%5EGDAXI",  # ^GDAXI
    "DOW_JONES":  "%5EDJI",    # ^DJI
}

PRETTY = {
    "SENSEX": "SENSEX",
    "HANG_SENG": "HANG SENG",
    "KOSPI": "KOSPI",
    "TAIWAN": "TAIWAN",
    "DAX": "DAX",
    "DOW_JONES": "DOW JONES",
}

# ---------- helpers ----------
def send(text, pin=True):
    try:
        r = requests.post(f"{API}/sendMessage",
                          data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
                          timeout=25)
        print("send:", r.status_code, r.text)
        if pin and r.ok:
            mid = r.json().get("result", {}).get("message_id")
            if mid:
                p = requests.post(f"{API}/pinChatMessage",
                                  data={"chat_id": CHAT_ID, "message_id": mid, "disable_notification": True},
                                  timeout=25)
                print("pin:", p.status_code, p.text)
    except Exception as e:
        print("send/pin error:", repr(e))

_price_num_regex = re.compile(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b")

def decimal_two_from_number(x: str) -> str:
    # "80,597.66" -> "66"
    try:
        clean = x.replace(",", "")
        d = (Decimal(clean) % 1).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        return f"{d:.2f}".split(".")[1]
    except Exception:
        return "??"

def try_from_html(url: str) -> str:
    """Tumhari official page se decimal 2 digits nikaalna (best-effort)."""
    if not url:
        return "??"
    try:
        resp = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
        html = resp.text
        # 1) obvious JSON number inside page
        # 2) visible numbers — pick the largest-looking price (heuristic)
        nums = _price_num_regex.findall(html)
        if not nums:
            # maybe the page renders client-side; try basic BeautifulSoup text
            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text(" ", strip=True)
            nums = _price_num_regex.findall(text)

        if not nums:
            return "??"

        # Heuristic: choose the one with the most digits before decimal/commas (likely headline price)
        def score(n):
            a = n.replace(",", "")
            parts = a.split(".")
            left = parts[0]
            right_len = len(parts[1]) if len(parts) > 1 else 0
            return (len(left), right_len)

        nums.sort(key=score, reverse=True)
        return decimal_two_from_number(nums[0])

    except Exception as e:
        print("html parse err:", repr(e))
        return "??"

def yahoo_decimal(symbol: str) -> str:
    try:
        url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbol}"
        j = requests.get(url, timeout=25, headers={"User-Agent":"Mozilla/5.0"}).json()
        res = j["quoteResponse"]["result"]
        if not res:
            return "??"
        price = res[0].get("regularMarketPrice")
        if price is None:
            return "??"
        return decimal_two_from_number(str(price))
    except Exception as e:
        print("yahoo err:", repr(e))
        return "??"

# ---------- main ----------
def run():
    name = PRETTY.get(INDEX, INDEX)
    ist = timezone("Asia/Kolkata")
    stamp = dt.datetime.now(ist).strftime("%d-%m-%Y %H:%M IST")

    # 1) pehle tumhari link
    dec = try_from_html(LINKS.get(INDEX, ""))

    # 2) agar fail -> Yahoo fallback
    if dec == "??":
        sym = YH_SYMBOL.get(INDEX)
        if sym:
            dec = yahoo_decimal(sym)

    text = f"<b>{name}</b> : <b>{dec}</b>\n<i>{stamp}</i>"
    send(text, pin=True)

if __name__ == "__main__" :
    run()

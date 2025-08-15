import os, re, requests, datetime as dt
from zoneinfo import ZoneInfo  # Python 3.9+

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")

# URLs env se uthao (tumne jo links diye hain unhe yahan GitHub Secrets me daalna)
URLS = {
    "TAIWAN"  : os.getenv("URL_TAIWAN"),
    "KOSPI"   : os.getenv("URL_KOSPI"),
    "HANG SENG": os.getenv("URL_HANGSENG"),
    "SENSEX"  : os.getenv("URL_SENSEX"),
    "DAX"     : os.getenv("URL_DAX"),
    "DOW JONES": os.getenv("URL_DOWJONES"),
}

PIN_AFTER_SEND = os.getenv("PIN_AFTER_SEND", "1") == "1"  # chaaho to 0 kar dena

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

hdrs = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def pick_two_decimals(html: str) -> str | None:
    """
    page me jo pehla price jaisa number mile (xx,xxx.xx) uska
    decimal ke baad ke 2 digits nikaal do.
    """
    m = re.search(r"(?:\d{1,3}(?:,\d{3})+|\d+)\.(\d{2})", html)
    return m.group(1) if m else None

def fetch_decimal_tail(url: str) -> str | None:
    r = requests.get(url, headers=hdrs, timeout=20)
    r.raise_for_status()
    return pick_two_decimals(r.text)

def send_message(text: str) -> int | None:
    r = requests.post(f"{TG_API}/sendMessage", data={
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
    }, timeout=20)
    j = r.json()
    return j.get("result", {}).get("message_id") if j.get("ok") else None

def pin_message(mid: int):
    try:
        requests.post(f"{TG_API}/pinChatMessage", data={
            "chat_id": CHAT_ID, "message_id": mid, "disable_notification": True
        }, timeout=20)
    except Exception:
        pass  # agar admin rights na ho to silently ignore

def ist_now_str():
    ist = dt.datetime.now(ZoneInfo("Asia/Kolkata"))
    return ist.strftime("%d-%m-%Y %H:%M IST")

def main():
    assert BOT_TOKEN and CHAT_ID, "Secrets BOT_TOKEN / CHAT_ID missing"

    for name, url in URLS.items():
        if not url:
            continue
        try:
            tail = fetch_decimal_tail(url)
            tail_txt = tail if tail is not None else "??"
            msg = f"{name} : {tail_txt}\n{ist_now_str()}"
            mid = send_message(msg)
            if PIN_AFTER_SEND and mid:
                pin_message(mid)
        except Exception as e:
            err = f"{name} : ??\n{ist_now_str()}\n(error)"
            send_message(err)

if __name__ ==  "__main__" :
    main()

import os, re, time, html
import requests

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID   = os.environ["CHAT_ID"]
INDEX     = os.environ["INDEX"].upper().strip()

# Yahoo Finance pages (region-agnostic)
YAHOO_URLS = {
    "TAIWAN":   "https://finance.yahoo.com/quote/%5ETWII",
    "KOSPI":    "https://finance.yahoo.com/quote/%5EKS11",
    "HANGSENG": "https://finance.yahoo.com/quote/%5EHSI",
    "SENSEX":   "https://finance.yahoo.com/quote/%5EBSESN",
    "DAX":      "https://finance.yahoo.com/quote/%5EGDAXI",
    "DOWJONES": "https://finance.yahoo.com/quote/%5EDJI",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

def fetch_price(url, attempts=6, wait=8):
    """
    Pull the live price number from Yahoo Finance page HTML.
    We look for the first big numeric like 25,176.85 in the page.
    """
    for i in range(attempts):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                text = r.text

                # Find something like 25,176.85 or 2,345.00
                m = re.search(r'(\d{1,3}(?:,\d{3})*(?:\.\d+))', text)
                if m:
                    raw = m.group(1)              # e.g. "25,176.85"
                    no_commas = raw.replace(",", "")
                    return float(no_commas)       # 25176.85
                # Fallback: try a second pattern Yahoo sometimes uses
                m2 = re.search(r'currentPrice.+?raw":\s*([\d\.]+)', text)
                if m2:
                    return float(m2.group(1))
            # rate limiting / empty – back off
            time.sleep(wait)
        except Exception:
            time.sleep(wait)
    return None

def last_two_decimals(value: float) -> str:
    """
    Return first two digits after decimal (00-99), WITHOUT rounding issues.
    25176.85 -> "85"; 123.4 -> "40".
    """
    s = f"{value:.4f}"         # plenty precision
    decimal = s.split(".")[1]  # e.g. "8500"
    return (decimal + "00")[:2]

def tg_send(text: str, disable_notification=True, pin=False):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_notification": disable_notification,
        "parse_mode": "HTML",
    }
    r = requests.post(url, data=payload, timeout=15)
    if pin and r.ok:
        msg_id = r.json().get("result", {}).get("message_id")
        if msg_id:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/pinChatMessage",
                data={"chat_id": CHAT_ID, "message_id": msg_id, "disable_notification": True},
                timeout=15
            )

def main():
    if INDEX not in YAHOO_URLS:
        tg_send(f"⚠️ INDEX missing/invalid: <b>{html.escape(INDEX)}</b>")
        return

    price = fetch_price(YAHOO_URLS[INDEX])
    if price is None:
        tg_send(f"⚠️ {INDEX} fetch error: no price (rate/conn.).")
        return

    num = last_two_decimals(price)  # yehi tumhe chahiye
    tg_send(f"<b>{INDEX}</b> : <b>{num}</b>", pin=True)

if __name__ == "__main__":
    main()

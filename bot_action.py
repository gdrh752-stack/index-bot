import os, requests
from datetime import datetime
from zoneinfo import ZoneInfo

# Yahoo Finance symbols
TICKERS = {
    "TAIWAN": "^TWII",
    "KOSPI": "^KS11",
    "HANGSENG": "^HSI",
    "SENSEX": "^BSESN",
    "DAX": "^GDAXI",
    "DOWJONES": "^DJI",
}

def fetch_last2(symbol):
    url = "https://query1.finance.yahoo.com/v7/finance/quote"
    resp = requests.get(url, params={"symbols": symbol})
    data = resp.json()
    p = data["quoteResponse"]["result"][0]["regularMarketPrice"]
    return f"{p:.2f}".split(".")[1] if p else "??"

def send_telegram(msg):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": msg}
    r = requests.post(url, data=payload).json()
    # Pin message
    if "result" in r and "message_id" in r["result"]:
        mid = r["result"]["message_id"]
        pin_url = f"https://api.telegram.org/bot{token}/pinChatMessage"
        requests.post(pin_url, data={"chat_id": chat_id, "message_id": mid})

if __name__ == "__main__":
    idx = os.getenv("INDEX", "UNKNOWN").upper()
    sym = TICKERS.get(idx)
    last2 = fetch_last2(sym) if sym else "??"
    now = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d-%m-%Y %H:%M IST")
    msg = f"{idx} : {last2}\n{now}"
    send_telegram(msg)

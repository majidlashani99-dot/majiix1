import os
import sys
import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.environ.get("TG_TOKEN") or os.environ.get("TG_BOT_TOKEN")
CHAT_ID = os.environ.get("TG_CHAT_ID")

def fetch_bahesab_calendar():
    url = "https://www.bahesab.ir/time/today/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    print("🌐 Fetching data from bahesab.ir...")
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.encoding = 'utf-8'
        if resp.status_code != 200:
            return None
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        shamsi = ""
        gregorian = ""
        hijri = ""
        events = []

        # استخراج دقیق تاریخ‌ها
        for tag in soup.find_all(["p", "div", "span", "td"]):
            t = tag.get_text(" ", strip=True)
            # خورشیدی
            if not shamsi and any(m in t for m in ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]):
                if any(day in t for day in ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "سه شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]):
                    shamsi = t
            # میلادی
            if not gregorian and any(m in t for m in ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]):
                gregorian = t
            # قمری
            if not hijri and any(m in t for m in ["محرم", "صفر", "ربیع", "جمادی", "رجب", "شعبان", "رمضان", "شوال", "ذیقعده", "ذیحجه"]):
                hijri = t

        # استخراج مناسبت‌ها
        items = soup.select(".event, .events, ul li, ol li, td")
        for it in items:
            txt = it.get_text(" ", strip=True)
            if txt and len(txt) > 4:
                if any(k in txt for k in ["روز", "ولادت", "شهادت", "جشن", "عید", "بزرگداشت", "جهانی", "ملی"]):
                    if not any(bad in txt for bad in ["تبلیغ", "تماس", "درباره", "حقوق", "سایت"]):
                        events.append(f"▫️ {txt}")

        return {
            "shamsi": shamsi,
            "gregorian": gregorian,
            "hijri": hijri,
            "events": list(dict.fromkeys(events))[:5] # فقط ۵ مناسبت اول
        }
    except Exception as e:
        print(f"Error: {e}")
        return None

def build_minimal_ui(d):
    # ساختار کاملاً فشرده و بدون متن اضافی
    msg = "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    if d["shamsi"]:
        msg += f"🇮🇷 **تاریخ خورشیدی:**\n`{d['shamsi']}`\n\n"
        
    if d["gregorian"]:
        msg += f"🌐 **تاریخ میلادی:**\n`{d['gregorian']}`\n\n"
        
    if d["hijri"]:
        msg += f"🌙 **تاریخ قمری:**\n`{d['hijri']}`\n\n"
        
    if d["events"]:
        msg += "📌 **مناسبت‌ها:**\n"
        for e in d["events"]:
            msg += f"{e}\n"
    
    msg += "\n━━━━━━━━━━━━━━━━━━━━━━"
    return msg

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload, timeout=20)

if __name__ == "__main__":
    if not BOT_TOKEN or not CHAT_ID:
        sys.exit(1)

    data = fetch_bahesab_calendar()
    if data:
        message = build_minimal_ui(data)
        print(message)
        send_to_telegram(message)

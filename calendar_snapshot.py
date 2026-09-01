import os
import sys
import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.environ.get("TG_TOKEN") or os.environ.get("TG_BOT_TOKEN")
CHAT_ID = os.environ.get("TG_CHAT_ID")

def fetch_bahesab_calendar():
    url = "https://www.bahesab.ir/time/today/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "fa,en;q=0.9"
    }

    print("🌐 Fetching calendar data from bahesab.ir...")
    resp = requests.get(url, headers=headers, timeout=20)
    resp.encoding = 'utf-8'

    if resp.status_code != 200:
        print(f"❌ Failed to load bahesab.ir. HTTP Status: {resp.status_code}")
        sys.exit(1)

    soup = BeautifulSoup(resp.text, 'html.parser')

    # استخراج تاریخ خورشیدی، میلادی، قمری
    shamsi = ""
    gregorian = ""
    hijri = ""
    zodiac = ""
    events = []

    # استخراج بخش تاریخ‌ها از جداول و باکس‌های باحساب
    for tag in soup.select("table, div, p, span, h1, h2, h3, td"):
        t = tag.get_text(" ", strip=True)
        if not shamsi and any(m in t for m in ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]):
            if any(day in t for day in ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "سه شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]):
                shamsi = t
        if not gregorian and any(m in t for m in ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]):
            gregorian = t
        if not hijri and any(m in t for m in ["محرم", "صفر", "ربیع", "جمادی", "رجب", "شعبان", "رمضان", "شوال", "ذیقعده", "ذیحجه"]):
            hijri = t
        if not zodiac and any(z in t for z in ["برج", "فلکی", "حمل", "ثور", "جوزا", "سرطان", "اسد", "سنبله", "میزان", "عقرب", "قوس", "جدی", "دلو", "حوت", "موش", "گاو", "ببر", "خرگوش", "نهنگ", "مار", "اسب", "گوسفند", "میمون", "مرغ", "سگ", "خوک"]):
            if "سال" in t or "برج" in t:
                zodiac = t

    # استخراج مناسبت‌ها
    # در سایت باحساب مناسبت‌ها در لیست‌ها یا بخش‌های خاص روز قرار دارند
    items = soup.select(".event, .events, ul li, ol li, .box li, td")
    for it in items:
        txt = it.get_text(" ", strip=True)
        if txt and len(txt) > 4:
            if any(k in txt for k in ["روز", "ولادت", "شهادت", "جشن", "عید", "بزرگداشت", "جهانی", "ملی", "درگذشت", "سالروز"]):
                if not any(bad in txt for bad in ["تبلیغ", "تماس", "درباره", "حقوق", "سایت", "ماشین حساب"]):
                    is_holiday = "holiday" in str(it.get("class", "")).lower() or "red" in str(it.get("style", "")).lower()
                    prefix = "🔴" if is_holiday else "▫️"
                    events.append(f"{prefix} {txt}")

    # حذف تکراری‌ها و تمیزکاری
    clean_events = []
    seen = set()
    for ev in events:
        # پاکسازی بخش‌های اضافی
        ev_clean = " ".join(ev.split())
        if ev_clean not in seen and len(ev_clean) < 120:
            seen.add(ev_clean)
            clean_events.append(ev_clean)

    return {
        "shamsi": shamsi.strip(),
        "gregorian": gregorian.strip(),
        "hijri": hijri.strip(),
        "zodiac": zodiac.strip(),
        "events": clean_events[:8] # حداکثر ۸ رویداد برتر روز
    }

def build_telegram_ui(data):
    msg = (
        "✨ **تـقـویـم و رویدادهای روز** ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if data["shamsi"]:
        msg += f"🇮🇷 **تاریخ خورشیدی:**\n` 📅 {data['shamsi']} `\n\n"

    if data["gregorian"]:
        msg += f"🌐 **تاریخ میلادی:**\n` 🗓 {data['gregorian']} `\n\n"

    if data["hijri"]:
        msg += f"🌙 **تاریخ قمری:**\n` 🕋 {data['hijri']} `\n\n"

    if data["zodiac"]:
        msg += f"🪐 **نماد / برج روز:**\n` 🔮 {data['zodiac']} `\n\n"

    msg += "📌 **مناسبت‌ها و رویدادهای مهم امروز:**\n"
    if data["events"]:
        for e in data["events"]:
            msg += f"{e}\n"
    else:
        msg += "▫️ _برای امروز رویداد یا مناسبت رسمی ثبت نشده است._\n"

    msg += (
        "\n━━━━━━━━━━━━━━━━━━━━━━\n"
        "💎 **کانال تحلیلی مجیکس** ➔ 🆔 **@majiix1**"
    )
    return msg

def send_telegram_msg(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    res = requests.post(url, json=payload, timeout=20)
    res_data = res.json()
    if res.status_code == 200 and res_data.get("ok"):
        print("🎉 پیام با موفقیت و در قالبی فوق‌العاده شیک به کانال ارسال شد!")
    else:
        print(f"❌ خطا در ارسال تلگرام: {res_data}")
        sys.exit(1)

if __name__ == "__main__":
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ متغیرهای TG_TOKEN یا TG_CHAT_ID پیدا نشدند.")
        sys.exit(1)

    data = fetch_bahesab_calendar()
    message = build_telegram_ui(data)
    print("\n--- Message Output ---\n")
    print(message)
    print("\n-----------------------\n")
    send_telegram_msg(message)

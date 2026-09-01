import os
import sys
import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.environ.get("TG_TOKEN") or os.environ.get("TG_BOT_TOKEN")
CHAT_ID = os.environ.get("TG_CHAT_ID")

def fetch_calendar_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    url = "https://www.time.ir/"
    
    print("🌐 Fetching data from Time.ir...")
    response = requests.get(url, headers=headers, timeout=20)
    response.encoding = 'utf-8'
    
    if response.status_code != 200:
        print(f"❌ Failed to fetch page. Status: {response.status_code}")
        sys.exit(1)
        
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # استخراج تاریخ شمسی
    shamsi_day = soup.select_one(".showDate .dayName")
    shamsi_num = soup.select_one(".showDate .dayNumber")
    shamsi_month = soup.select_one(".showDate .monthName")
    shamsi_year = soup.select_one(".showDate .year")
    
    shamsi_str = ""
    if shamsi_num and shamsi_month:
        day_name = shamsi_day.get_text(strip=True) if shamsi_day else ""
        day_num = shamsi_num.get_text(strip=True)
        month_name = shamsi_month.get_text(strip=True)
        year_name = shamsi_year.get_text(strip=True) if shamsi_year else ""
        shamsi_str = f"{day_name} {day_num} {month_name} {year_name}".strip()
    
    # استخراج تاریخ میلادی و قمری
    gregorian_str = ""
    hijri_str = ""
    other_dates = soup.select(".dates .otherGregorian, .dates .otherHijri, .dates div")
    for d in other_dates:
        text = d.get_text(" ", strip=True)
        if any(month in text for month in ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]):
            gregorian_str = text
        elif any(m in text for m in ["محرم", "صفر", "ربيع", "جمادى", "رجب", "شعبان", "رمضان", "شوال", "ذو القعدة", "ذو الحجة", "ذوالقعدة", "ذوالحجة"]):
            hijri_str = text

    # استخراج برج فلکی / نماد سال (در صورت وجود)
    zodiac_el = soup.select_one(".showDate .season") or soup.select_one(".showDate .zodiac")
    zodiac_str = zodiac_el.get_text(strip=True) if zodiac_el else ""

    # استخراج مناسبت‌ها و رویدادهای روز
    events = []
    events_list = soup.select(".list-unstyled li, .eventsContainer li, ul.eventList li")
    for li in events_list:
        ev_text = li.get_text(" ", strip=True)
        # حذف متون اضافه یا تبلیغاتی
        if ev_text and len(ev_text) > 3 and not "تبلیغ" in ev_text:
            is_holiday = "eventHoliday" in li.get("class", []) or "holiday" in li.get("class", [])
            prefix = "🔴" if is_holiday else "▫️"
            events.append(f"{prefix} {ev_text}")

    # حذف تکراری‌ها در مناسبت‌ها
    events = list(dict.fromkeys(events))
    
    return {
        "shamsi": shamsi_str,
        "gregorian": gregorian_str,
        "hijri": hijri_str,
        "zodiac": zodiac_str,
        "events": events
    }

def format_telegram_message(data):
    msg = "☀️ **تقویم و رویدادهای روز**\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    if data["shamsi"]:
        msg += f"🇮🇷 **خورشیدی:** `{data['shamsi']}`\n"
    if data["gregorian"]:
        msg += f"🌐 **میلادی:** `{data['gregorian']}`\n"
    if data["hijri"]:
        msg += f"🌙 **قمری:** `{data['hijri']}`\n"
    if data["zodiac"]:
        msg += f"✨ **برج فلکی:** `{data['zodiac']}`\n"
        
    msg += "\n📌 **مناسبت‌ها و رویدادها:**\n"
    if data["events"]:
        for ev in data["events"]:
            msg += f"{ev}\n"
    else:
        msg += "▫️ _امروز مناسبت ثبت‌شده‌ای ندارد._\n"
        
    msg += "\n━━━━━━━━━━━━━━━━━━━━━\n"
    msg += "🆔 **@majiix1**"
    
    return msg

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    print("🚀 Sending text to Telegram...")
    response = requests.post(url, json=payload, timeout=20)
    res_json = response.json()
    
    if response.status_code == 200 and res_json.get("ok"):
        print("🎉 Telegram message delivered successfully!")
    else:
        print(f"❌ Telegram API Error: {res_json}")
        sys.exit(1)

if __name__ == "__main__":
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Error: TG_TOKEN/TG_BOT_TOKEN or TG_CHAT_ID is missing.")
        sys.exit(1)
        
    calendar_data = fetch_calendar_data()
    formatted_msg = format_telegram_message(calendar_data)
    print("\n--- Message Preview ---\n", formatted_msg, "\n-----------------------")
    send_to_telegram(formatted_msg)

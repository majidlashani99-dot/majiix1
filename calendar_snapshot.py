import os
import sys
import requests
from bs4 import BeautifulSoup
from datetime import datetime

BOT_TOKEN = os.environ.get("TG_TOKEN") or os.environ.get("TG_BOT_TOKEN")
CHAT_ID = os.environ.get("TG_CHAT_ID")

def get_time_ir_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    events = []
    shamsi_text = ""
    gregorian_text = ""
    hijri_text = ""
    
    try:
        resp = requests.get("https://www.time.ir/", headers=headers, timeout=15)
        resp.encoding = 'utf-8'
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # استخراج رویدادها و مناسبت‌های روز
            event_items = soup.find_all("li", class_=lambda x: x and ("event" in x.lower() or "holiday" in x.lower())) or soup.select(".list-unstyled li")
            for item in event_items:
                txt = item.get_text(" ", strip=True)
                if txt and len(txt) > 2 and "تبلیغ" not in txt and "رویدادهای" not in txt:
                    is_holiday = "holiday" in str(item.get("class", [])).lower() or "red" in str(item.get("style", "")).lower()
                    icon = "🔴" if is_holiday else "▫️"
                    events.append(f"{icon} {txt}")
                    
            # استخراج متن‌های تاریخ از المنت‌های صفحه
            all_text_elements = soup.select(".today-container, .dates, .panel-today, .showDate, div")
            for el in all_text_elements:
                t = el.get_text(" ", strip=True)
                if not shamsi_text and ("فروردین" in t or "اردیبهشت" in t or "خرداد" in t or "تیر" in t or "مرداد" in t or "شهریور" in t or "مهر" in t or "آبان" in t or "آذر" in t or "دی" in t or "بهمن" in t or "اسفند" in t):
                    for line in t.split("\n"):
                        clean = line.strip()
                        if any(m in clean for m in ["فروردین","اردیبهشت","خرداد","تیر","مرداد","شهریور","مهر","آبان","آذر","دی","بهمن","اسفند"]):
                            shamsi_text = clean
                            break
    except Exception as e:
        print(f"⚠️ Error scraping time.ir: {e}")
        
    return {
        "shamsi": shamsi_text,
        "events": list(dict.fromkeys(events))
    }

def get_complete_calendar_data():
    # دریافت اطلاعات جامع تاریخ از API بدون باگ
    api_url = "https://api.keybit.ir/time/"
    time_ir_info = get_time_ir_data()
    
    data = {}
    try:
        res = requests.get(api_url, timeout=10)
        if res.status_code == 200:
            j = res.json()
            if j.get("status") == "ok":
                date_info = j.get("date", {})
                time_info = j.get("time24", {})
                
                # تاریخ شمسی
                data["shamsi"] = date_info.get("full", {}).get("official", {}).get("usual", {}).get("fa") or time_ir_info["shamsi"]
                # تاریخ میلادی
                g = date_info.get("other", {}).get("gregorian", {})
                data["gregorian"] = f"{g.get('weekday', {}).get('name')}, {g.get('day', {}).get('name')} {g.get('month', {}).get('name')} {g.get('year', {}).get('name')}"
                # تاریخ قمری
                q = date_info.get("other", {}).get("ghamari", {})
                data["hijri"] = f"{q.get('weekday', {}).get('name')} {q.get('day', {}).get('name')} {q.get('month', {}).get('name')} {q.get('year', {}).get('name')}"
                # حیوان سال و برج
                data["animal"] = date_info.get("year", {}).get("animal", "")
                data["season"] = j.get("season", {}).get("name", {}).get("fa", "")
    except Exception as e:
        print(f"⚠️ API error fallback: {e}")
        
    # اگر API در دسترس نبود از اطلاعات جایگزین استفاده شود
    if not data.get("shamsi"):
        data["shamsi"] = time_ir_info["shamsi"] or "امروز"
        now = datetime.now()
        data["gregorian"] = now.strftime("%A, %d %B %Y")
        data["hijri"] = "تقویم هجری قمری"
        
    data["events"] = time_ir_info["events"]
    return data

def format_telegram_post(d):
    post = "☀️ **تقویم روز و مناسبت‌ها**\n"
    post += "━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    post += f"🇮🇷 **خورشیدی:** `{d.get('shamsi', '')}`\n"
    if d.get("gregorian"):
        post += f"🌐 **میلادی:** `{d.get('gregorian', '')}`\n"
    if d.get("hijri"):
        post += f"🌙 **قمری:** `{d.get('hijri', '')}`\n"
    if d.get("animal"):
        post += f"🐾 **نماد سال:** `{d.get('animal', '')}`\n"

    post += "\n📌 **مناسبت‌ها و رویدادهای امروز:**\n"
    events = d.get("events", [])
    if events:
        for ev in events:
            post += f"{ev}\n"
    else:
        post += "▫️ _مناسبت خاصی برای امروز ثبت نشده است._\n"
        
    post += "\n━━━━━━━━━━━━━━━━━━━━━\n"
    post += "🆔 **@majiix1**"
    return post

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    r = requests.post(url, json=payload, timeout=20)
    res = r.json()
    if r.status_code == 200 and res.get("ok"):
        print("🎉 Successfully sent full calendar message to Telegram!")
    else:
        print(f"❌ Telegram API Error: {res}")
        sys.exit(1)

if __name__ == "__main__":
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Missing TG_TOKEN / TG_CHAT_ID")
        sys.exit(1)
        
    calendar_data = get_complete_calendar_data()
    msg = format_telegram_post(calendar_data)
    print("\nGenerated Message Preview:\n", msg)
    send_message(msg)

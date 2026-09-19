import os
import sys
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# تنظیم انکودینگ خروجی ترمینال
sys.stdout.reconfigure(encoding='utf-8')

# تنظیمات تلگرام از متغیرهای گیت‌هاب
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def fetch_scoreyab_matches():
    url = "https://scoreyab.com/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "fa,en;q=0.9",
        "Referer": "https://www.google.com/"
    }

    response = requests.get(url, headers=headers, timeout=20)
    response.encoding = 'utf-8'
    
    if response.status_code != 200:
        raise Exception(f"خطا در دریافت سایت: کد وضعیت {response.status_code}")

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # ساختار متن خروجی
    date_str = datetime.now().strftime("%Y/%m/%d")
    message_lines = [
        "⚽️ **برنامه مسابقات فوتبال امروز**",
        f"📅 تاریخ: `{date_str}`",
        "📡 منبع: اسکوریاب\n",
        "─────────────────"
    ]

    # استخراج بازی‌ها
    # در صورت وجود تگ‌های اختصاصی یا پارس بر اساس ساختار متنی بلوک‌ها:
    text_content = soup.get_text("\n")
    lines = [l.strip() for l in text_content.split("\n") if l.strip()]

    # الگو برای تشخیص مسابقات: تیم میزبان - ساعت (HH:MM یا ۰۰:۰۰) - تیم میهمان
    time_pattern = re.compile(r"^([0-2]?[0-9]:[0-5][0-9]|[۰-۲]?[۰-۹]:[۰-۵][۰-۹])$")
    
    collected_matches = []
    
    for i in range(1, len(lines) - 1):
        # بررسی اینکه آیا خط فعلی یک زمان است
        if time_pattern.match(lines[i]):
            team_home = lines[i - 1]
            match_time = lines[i]
            team_away = lines[i + 1]
            
            # اعتبارسنجی ساده برای جلوگیری از متن‌های منو یا باگ
            if len(team_home) < 35 and len(team_away) < 35 and not any(k in team_home for k in ["لیگ", "مشاهده", "اخبار"]):
                collected_matches.append(f"▫️ **{team_home}**  ⏰ `{match_time}`  **{team_away}**")

    if not collected_matches:
        # متد جایگزین در صورتی که ساختار DOM کارت‌ها در دسترس باشد
        # استخراج بر اساس الگوهای عمومی کارت مسابقات
        containers = soup.find_all(['div', 'a'], class_=lambda c: c and any(k in c.lower() for k in ['match', 'fixture', 'game', 'event']))
        for c in containers:
            t = c.get_text(" ", strip=True)
            if ":" in t and len(t) < 80:
                collected_matches.append(f"▫️ {t}")

    # حذف موارد تکراری با حفظ ترتیب
    unique_matches = list(dict.fromkeys(collected_matches))

    if not unique_matches:
        message_lines.append("امروز مسابقه‌ای ثبت نشده است یا سایت در حال بروزرسانی می‌باشد.")
    else:
        # اضافه کردن مسابقات به پیام نهایی
        message_lines.extend(unique_matches)

    message_lines.append("\n─────────────────")
    message_lines.append("🤖 *کاری از ربات MAJIX Clean*")

    return "\n".join(message_lines)

def send_to_telegram(message_text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ متغیرهای TELEGRAM_BOT_TOKEN یا TELEGRAM_CHAT_ID تنظیم نشده‌اند.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message_text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }

    resp = requests.post(url, json=payload, timeout=20)
    if resp.status_code == 200:
        print("✅ پیام مسابقات با موفقیت به تلگرام ارسال شد.")
    else:
        # اگر مارک‌داون خطا داد، به صورت متن ساده بفرست
        payload.pop("parse_mode")
        retry_resp = requests.post(url, json=payload, timeout=20)
        if retry_resp.status_code == 200:
            print("✅ پیام به صورت متن ساده ارسال شد.")
        else:
            print(f"❌ خطا در ارسال به تلگرام: {retry_resp.text}")

if __name__ == "__main__":
    try:
        msg = fetch_scoreyab_matches()
        print("متن پیام تولید شده:\n")
        print(msg)
        print("\nدر حال ارسال به تلگرام...")
        send_to_telegram(msg)
    except Exception as e:
        print(f"❌ خطای اجرایی: {e}")
        sys.exit(1)

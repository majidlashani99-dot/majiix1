import os
import re
import sys
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

# متغیرهای محیطی از سکرت‌ها
BOT_TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")
SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL", "SPORTinoTV").strip().lstrip("@")
FILTER_TEXT = os.getenv("FILTER_TEXT", "کنداکتور").strip()

REQUEST_TIMEOUT = 30
MAX_POSTS_TO_CHECK = 15

# محدوده زمانی ایران (UTC+3:30)
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

def clean_caption(text: str) -> str:
    """
    حذف تمام آیدی‌ها و لینک‌ها بدون دستکاری به متن اصلی کپشن
    """
    if not text:
        return ""
    
    # حذف لینک‌های وب و تلگرام
    text = re.sub(r"https?://\S+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"www\.\S+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<!\w)t\.me/\S+", "", text, flags=re.IGNORECASE)
    
    # حذف کامل آیدی‌ها مثل @SPORTinoTV یا هر منشن دیگر
    text = re.sub(r"@[A-Za-z0-9_]+", "", text)
    
    # حذف خطوط خالی اضافی که ناشی از پاک شدن آیدی‌ها شده است
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines).strip()

def is_today_post(time_elem) -> bool:
    """بررسی تاریخ پست نسبت به تاریخ امروز ایران"""
    if not time_elem or not time_elem.get("datetime"):
        return True

    try:
        dt_str = time_elem["datetime"]
        post_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        post_dt_iran = post_dt.astimezone(IRAN_TZ)
        today_iran = datetime.now(IRAN_TZ).date()
        return post_dt_iran.date() == today_iran
    except Exception as e:
        print(f"⚠️ ارزیابی تاریخ با خطا مواجه شد: {e}")
        return True

def contains_filter(text: str) -> bool:
    """بررسی وجود کلمه کنداکتور در متن"""
    if not text or not FILTER_TEXT:
        return False
    normalized_text = re.sub(r"\s+", " ", text).strip().casefold()
    normalized_filter = re.sub(r"\s+", " ", FILTER_TEXT).strip().casefold()
    return normalized_filter in normalized_text

def extract_photo_url(message) -> str | None:
    """استخراج مستقیم تصویر پست با بالاترین کیفیت"""
    photo_elem = message.find("a", class_="tgme_widget_message_photo_wrap")
    if not photo_elem:
        return None
    style = photo_elem.get("style", "")
    match = re.search(r"background-image\s*:\s*url\(['\"]?([^'\")]+)['\"]?\)", style)
    return match.group(1).strip() if match else None

def send_telegram(method: str, payload: dict) -> bool:
    """ارسال امن پیام یا مدیا به ربات تلگرام"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        res = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        res_data = res.json()
        if res_data.get("ok"):
            print(f"✅ با موفقیت به کانال/گروه ارسال شد ({method})")
            return True
        else:
            print(f"❌ خطای دریافت پاسخ از تلگرام: {res_data}")
            return False
    except Exception as e:
        print(f"❌ خطای شبکه در ارتباط با تلگرام: {e}")
        return False

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ مقادیر TG_TOKEN یا TG_CHAT_ID در گیت‌هاب یافت نشد.")
        sys.exit(1)

    today_str = datetime.now(IRAN_TZ).strftime("%Y-%m-%d")
    print(f"📅 تاریخ فعلی پردازش (ایران): {today_str}")
    print(f"📡 کانال منبع: https://t.me/s/{SOURCE_CHANNEL}")
    print(f"🔍 فیلتر متن: «{FILTER_TEXT}»")

    url = f"https://t.me/s/{SOURCE_CHANNEL}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept-Language": "fa,en-US;q=0.9,en;q=0.8",
    }

    try:
        res = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        res.raise_for_status()
    except Exception as e:
        print(f"❌ خطا در خواندن کانال: {e}")
        sys.exit(1)

    soup = BeautifulSoup(res.text, "html.parser")
    messages = soup.select("div.tgme_widget_message_wrap")

    if not messages:
        print("⚠️ هیچ پیامی در وب‌پیج کانال دریافت نشد.")
        return

    sent_count = 0
    for msg in messages[-MAX_POSTS_TO_CHECK:]:
        time_elem = msg.find("time")
        text_elem = msg.select_one("div.tgme_widget_message_text")
        raw_text = text_elem.get_text(separator="\n", strip=True) if text_elem else ""

        # بررسی فیلتر کلمه کنداکتور
        if not contains_filter(raw_text):
            continue

        # بررسی تاریخ برای جلوگیری از ارسال روزهای قبل
        if not is_today_post(time_elem):
            print("⏳ پست کنداکتور مربوط به تاریخ گذشته است (رد شد).")
            continue

        print("🎯 کنداکتور امروز یافت شد؛ در حال ارسال...")
        
        # پاک‌سازی فقط آیدی‌ها و لینک‌ها (متن کپشن حفظ می‌شود)
        clean_text_content = clean_caption(raw_text)
        photo_url = extract_photo_url(msg)

        if photo_url:
            success = send_telegram("sendPhoto", {
                "chat_id": CHAT_ID,
                "photo": photo_url,
                "caption": clean_text_content[:1024]
            })
        else:
            success = send_telegram("sendMessage", {
                "chat_id": CHAT_ID,
                "text": clean_text_content[:4096],
                "disable_web_page_preview": True
            })

        if success:
            sent_count += 1

    print("──────────────────────────────────")
    if sent_count > 0:
        print(f"🚀 مجموعاً {sent_count} پست کنداکتور امروز با کپشن تمیز ارسال گردید.")
    else:
        print("ℹ️ در بررسی فعلی، پست کنداکتور جدیدی از امروز منتشر نشده بود.")

if __name__ == "__main__":
    main()

import os
import re
import sys
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

# متغیرهای محیطی از Secrets
BOT_TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")
SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL", "SPORTinoTV").strip().lstrip("@")
FILTER_TEXT = os.getenv("FILTER_TEXT", "کنداکتور").strip()

REQUEST_TIMEOUT = 30
MAX_POSTS_TO_CHECK = 30  # بررسی تا ۳۰ پست اخیر برای پوشش کامل صبح تا ساعت ۹:۱۷

# محدوده زمانی رسمی ایران (UTC+3:30)
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

def clean_caption(text: str) -> str:
    """حذف تمام آیدی‌ها و لینک‌ها بدون دستکاری در متن اصلی کنداکتور"""
    if not text:
        return ""
    
    # حذف لینک‌های وب و تلگرام
    text = re.sub(r"https?://\S+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"www\.\S+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<!\w)t\.me/\S+", "", text, flags=re.IGNORECASE)
    
    # حذف کامل آیدی‌ها و منشن‌ها
    text = re.sub(r"@[A-Za-z0-9_]+", "", text)
    
    # حذف خطوط خالی اضافی
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines).strip()

def is_today_post(time_elem) -> bool:
    """بررسی تاریخ انتشار پست نسبت به تاریخ امروز ایران"""
    if not time_elem or not time_elem.get("datetime"):
        return False

    try:
        dt_str = time_elem["datetime"]
        post_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        post_dt_iran = post_dt.astimezone(IRAN_TZ)
        today_iran = datetime.now(IRAN_TZ).date()
        return post_dt_iran.date() == today_iran
    except Exception as e:
        print(f"⚠️ ارزیابی تاریخ با خطا مواجه شد: {e}")
        return False

def contains_filter(text: str) -> bool:
    """بررسی دقیق وجود کلمه کلیدی کنداکتور در متن"""
    if not text or not FILTER_TEXT:
        return False
    normalized_text = re.sub(r"\s+", " ", text).strip().casefold()
    normalized_filter = re.sub(r"\s+", " ", FILTER_TEXT).strip().casefold()
    return normalized_filter in normalized_text

def extract_photo_url(message) -> str | None:
    """استخراج مستقیم آدرس تصویر با بالاترین کیفیت"""
    photo_elem = message.find("a", class_="tgme_widget_message_photo_wrap")
    if not photo_elem:
        return None
    style = photo_elem.get("style", "")
    match = re.search(r"background-image\s*:\s*url\(['\"]?([^'\")]+)['\"]?\)", style)
    return match.group(1).strip() if match else None

def send_telegram(method: str, payload: dict) -> bool:
    """ارسال امن پیام یا تصویر به ربات تلگرام"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        res = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        res_data = res.json()
        if res_data.get("ok"):
            print(f"✅ با موفقیت به مقصد ارسال شد ({method})")
            return True
        else:
            print(f"❌ خطای تلگرام: {res_data}")
            return False
    except Exception as e:
        print(f"❌ خطای اتصال به سرور تلگرام: {e}")
        return False

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ متغیرهای TG_TOKEN یا TG_CHAT_ID در گیت‌هاب تنظیم نشده‌اند.")
        sys.exit(1)

    today_str = datetime.now(IRAN_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"📅 زمان اجرای اسکریپت (افق ایران): {today_str}")
    print(f"📡 منبع: https://t.me/s/{SOURCE_CHANNEL}")
    print(f"🔍 کلمه کلیدی: «{FILTER_TEXT}»")

    url = f"https://t.me/s/{SOURCE_CHANNEL}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept-Language": "fa,en-US;q=0.9,en;q=0.8",
    }

    try:
        res = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        res.raise_for_status()
    except Exception as e:
        print(f"❌ خطا در دریافت وب‌پیج کانال: {e}")
        sys.exit(1)

    soup = BeautifulSoup(res.text, "html.parser")
    messages = soup.select("div.tgme_widget_message_wrap")

    if not messages:
        print("⚠️ پیامی در کانال مبدأ یافت نشد.")
        return

    sent_count = 0
    # پیمایش پست‌های اخیر به ترتیب زمان
    for msg in messages[-MAX_POSTS_TO_CHECK:]:
        time_elem = msg.find("time")
        text_elem = msg.select_one("div.tgme_widget_message_text")
        raw_text = text_elem.get_text(separator="\n", strip=True) if text_elem else ""

        # بررسی فیلتر کلمه کنداکتور
        if not contains_filter(raw_text):
            continue

        # بررسی تاریخ انتشار پست (فقط پست‌های ارسال شده در روز جاری)
        if not is_today_post(time_elem):
            print("⏳ پست کنداکتور مربوط به روزهای قبل است (رد شد).")
            continue

        print("🎯 کنداکتور جدید امروز یافت شد؛ در حال پردازش و ارسال...")
        
        # تمیزسازی متن کپشن
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
        print(f"🚀 مجموعاً {sent_count} پست کنداکتور امروز با موفقیت ارسال شد.")
    else:
        print("ℹ️ پست کنداکتور جدیدی برای امروز در کانال منتشر نشده بود.")

if __name__ == "__main__":
    main()

import os
import re
import sys
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

# دریافت مقادیر محیطی
BOT_TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")
SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL", "SPORTinoTV").strip().lstrip("@")
FILTER_TEXT = os.getenv("FILTER_TEXT", "کنداکتور").strip()

REQUEST_TIMEOUT = 30
MAX_POSTS_TO_CHECK = 30  # بررسی ۳۰ پست اخیر کانال

# محدوده زمانی رسمی ایران (UTC+3:30)
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

def normalize_text(text: str) -> str:
    """استانداردسازي حروف فارسی و عربی برای جلوگیری از خطای فیلتر"""
    if not text:
        return ""
    text = text.replace("ي", "ی").replace("ك", "ک").replace("ۀ", "ه")
    text = re.sub(r"[\u200c\u200b\u200e\u200f]", "", text) # حذف نیم‌فاصله‌های مخفی
    text = re.sub(r"\s+", " ", text)
    return text.strip().casefold()

def clean_caption(text: str) -> str:
    """حذف لینک‌ها و آیدی‌های تبلیغاتی بدون دستکاری محتوای اصلی"""
    if not text:
        return ""
    # حذف لینک‌ها
    text = re.sub(r"https?://\S+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"www\.\S+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<!\w)t\.me/\S+", "", text, flags=re.IGNORECASE)
    # حذف آیدی‌ها
    text = re.sub(r"@[A-Za-z0-9_]+", "", text)
    
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines).strip()

def is_recent_or_today(time_elem) -> bool:
    """بررسی اینکه آیا پست متعلق به امروز است یا در ۲۴ ساعت اخیر ارسال شده"""
    if not time_elem or not time_elem.get("datetime"):
        return False
    try:
        dt_str = time_elem["datetime"]
        post_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        now_utc = datetime.now(timezone.utc)
        
        # ۱. اگر در ۲۴ ساعت گذشته ارسال شده باشد
        time_diff = now_utc - post_dt
        if time_diff.total_seconds() <= 86400: # کمتر از ۲۴ ساعت
            return True
            
        # ۲. یا اگر تاریخ تقویمی امروز ایران باشد
        post_dt_iran = post_dt.astimezone(IRAN_TZ)
        today_iran = datetime.now(IRAN_TZ).date()
        return post_dt_iran.date() == today_iran
    except Exception as e:
        print(f"⚠️ خطای تحلیل تاریخ: {e}")
        return False

def contains_filter(text: str) -> bool:
    """بررسی هوشمند کلمه کنداکتور"""
    if not text:
        return False
    norm_txt = normalize_text(text)
    norm_filter = normalize_text(FILTER_TEXT)
    return norm_filter in norm_txt

def extract_photo_url(message) -> str | None:
    photo_elem = message.find("a", class_="tgme_widget_message_photo_wrap")
    if not photo_elem:
        return None
    style = photo_elem.get("style", "")
    match = re.search(r"background-image\s*:\s*url\(['\"]?([^'\")]+)['\"]?\)", style)
    return match.group(1).strip() if match else None

def send_telegram(method: str, payload: dict) -> bool:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        res = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        res_data = res.json()
        if res_data.get("ok"):
            print(f"✅ ارسال موفق ({method})")
            return True
        else:
            print(f"❌ خطای تلگرام: {res_data}")
            return False
    except Exception as e:
        print(f"❌ خطای درخواست تلگرام: {e}")
        return False

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ متغیرهای TG_TOKEN یا TG_CHAT_ID تنظیم نشده‌اند.")
        sys.exit(1)

    now_iran = datetime.now(IRAN_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"⏰ زمان اجرا: {now_iran} (افق ایران)")
    print(f"📡 منبع: https://t.me/s/{SOURCE_CHANNEL}")
    print(f"🔍 فیلتر کلمه: {FILTER_TEXT}")

    url = f"https://t.me/s/{SOURCE_CHANNEL}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "fa,en-US;q=0.9,en;q=0.8",
    }

    try:
        res = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        res.raise_for_status()
    except Exception as e:
        print(f"❌ خطا در باز کردن صفحه تلگرام: {e}")
        sys.exit(1)

    soup = BeautifulSoup(res.text, "html.parser")
    messages = soup.select("div.tgme_widget_message_wrap")

    if not messages:
        print("⚠️ هیچ پیامی در کانال یافت نشد.")
        return

    print(f"📊 تعداد پیام‌های خوانده شده از صفحه: {len(messages)}")
    sent_count = 0

    for idx, msg in enumerate(messages[-MAX_POSTS_TO_CHECK:], 1):
        time_elem = msg.find("time")
        time_str = time_elem.get("datetime") if time_elem else "نامشخص"
        text_elem = msg.select_one("div.tgme_widget_message_text")
        raw_text = text_elem.get_text(separator="\n", strip=True) if text_elem else ""

        # بررسی فیلتر
        has_word = contains_filter(raw_text)
        is_recent = is_recent_or_today(time_elem)

        if not has_word:
            continue

        if not is_recent:
            print(f"⏳ پیام شماره {idx} حاوی کلمه بود ولی قدیمی است (تاریخ: {time_str}).")
            continue

        print(f"🎯 پیام منطبق شماره {idx} پیدا شد! در حال آماده‌سازی برای ارسال...")
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
    if sent_count == 0:
        print("⚠️ هیچ پست جدیدی منطبق با شرایط در ۲۴ ساعت گذشته پیدا نشد.")
    else:
        print(f"🚀 مجموعاً {sent_count} پست با موفقیت ارسال گردید.")

if __name__ == "__main__":
    main()

import os
import re
import sys
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

# مقادیر سکرت
BOT_TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")
SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL", "SPORTinoTV").strip().lstrip("@")
FILTER_TEXT = os.getenv("FILTER_TEXT", "کنداکتور").strip()

REQUEST_TIMEOUT = 30
MAX_PAGES = 4  # خواندن تا ۴ صفحه قبل تلگرام برای پوشش کامل پست‌های امروز
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("ي", "ی").replace("ك", "ک").replace("ۀ", "ه")
    text = re.sub(r"[\u200c\u200b\u200e\u200f]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().casefold()

def clean_caption(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"https?://\S+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"www\.\S+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<!\w)t\.me/\S+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"@[A-Za-z0-9_]+", "", text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines).strip()

def is_recent_or_today(time_elem) -> bool:
    if not time_elem or not time_elem.get("datetime"):
        return False
    try:
        dt_str = time_elem["datetime"]
        post_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        now_utc = datetime.now(timezone.utc)
        
        # اگر در ۲۴ ساعت گذشته ارسال شده باشد یا تاریخ امروز ایران باشد
        if (now_utc - post_dt).total_seconds() <= 86400:
            return True
        post_dt_iran = post_dt.astimezone(IRAN_TZ)
        return post_dt_iran.date() == datetime.now(IRAN_TZ).date()
    except Exception:
        return False

def contains_filter(text: str) -> bool:
    if not text:
        return False
    norm_txt = normalize_text(text)
    norm_filter = normalize_text(FILTER_TEXT)
    # بررسی کلمه اصلی یا عبارات رایج
    return (norm_filter in norm_txt) or ("برنامه بازی" in norm_txt)

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
            print(f"✅ با موفقیت به تلگرام فرستاده شد ({method})")
            return True
        else:
            print(f"❌ خطای ارسال تلگرام: {res_data}")
            return False
    except Exception as e:
        print(f"❌ خطای ارتباط با تلگرام: {e}")
        return False

def get_channel_messages():
    """پیمایش در صفحات تلگرام برای استخراج پست‌ها حتی اگر پست‌های زیادی بعدش آمده باشد"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "fa,en-US;q=0.9,en;q=0.8",
    }
    
    all_messages = []
    base_url = f"https://t.me/s/{SOURCE_CHANNEL}"
    current_url = base_url

    for page in range(MAX_PAGES):
        try:
            print(f"📥 دریافت صفحه {page + 1}: {current_url}")
            res = requests.get(current_url, headers=headers, timeout=REQUEST_TIMEOUT)
            if res.status_code != 200:
                break
            soup = BeautifulSoup(res.text, "html.parser")
            msgs = soup.select("div.tgme_widget_message_wrap")
            if not msgs:
                break
            
            all_messages = msgs + all_messages  # به ترتیب اضافه می‌شوند
            
            # پیدا کردن شناسه اولین پیام برای برگشت به عقب
            first_msg_data = msgs[0].select_one("div.tgme_widget_message")
            if first_msg_data and first_msg_data.get("data-post"):
                post_num = first_msg_data["data-post"].split("/")[-1]
                current_url = f"{base_url}?before={post_num}"
            else:
                break
        except Exception as e:
            print(f"⚠️ خطا در صفحه {page + 1}: {e}")
            break

    return all_messages

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ متغیرهای TG_TOKEN یا TG_CHAT_ID تنظیم نشده‌اند.")
        sys.exit(1)

    now_iran = datetime.now(IRAN_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"⏰ زمان شروع: {now_iran} (ایران)")
    print(f"📡 بررسی کانال @{SOURCE_CHANNEL} برای یافتن کلمه «{FILTER_TEXT}»...")

    messages = get_channel_messages()
    print(f"📊 مجموع کل پیام‌های بررسی‌شده در صفحات: {len(messages)}")

    matched_posts = []
    for msg in messages:
        text_elem = msg.select_one("div.tgme_widget_message_text")
        raw_text = text_elem.get_text(separator="\n", strip=True) if text_elem else ""
        time_elem = msg.find("time")

        if contains_filter(raw_text) and is_recent_or_today(time_elem):
            matched_posts.append((msg, raw_text))

    if not matched_posts:
        print("⚠️ هیچ پستی با کلمه کنداکتور در ۲۴ ساعت گذشته پیدا نشد.")
        return

    print(f"🎯 تعداد {len(matched_posts)} پست منطبق پیدا شد! در حال ارسال آخرین مورد...")
    
    # آخرین پست منطبق را ارسال می‌کنیم تا تکراری نفرستد
    target_msg, raw_text = matched_posts[-1]
    clean_text_content = clean_caption(raw_text)
    photo_url = extract_photo_url(target_msg)

    if photo_url:
        send_telegram("sendPhoto", {
            "chat_id": CHAT_ID,
            "photo": photo_url,
            "caption": clean_text_content[:1024]
        })
    else:
        send_telegram("sendMessage", {
            "chat_id": CHAT_ID,
            "text": clean_text_content[:4096],
            "disable_web_page_preview": True
        })

if __name__ == "__main__":
    main()

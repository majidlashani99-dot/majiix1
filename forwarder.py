import os
import re
import requests
from bs4 import BeautifulSoup

# دریافت مقادیر از Secretهای گیت‌هاب
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SOURCE_CHANNEL = "LiveScore_plus"

def clean_text(text: str) -> str:
    """حذف لینک‌ها، آیدی‌های تلگرام (@) و فضاهای خالی اضافه"""
    if not text:
        return ""
    # حذف تمام آیدی‌های تلگرامی (مثل @LiveScore_plus)
    text = re.sub(r'@[A-Za-z0-9_]+', '', text)
    # حذف لینک‌های اینترنتی (http, https, t.me)
    text = re.sub(r'https?://\S+|www\.\S+|t\.me/\S+', '', text)
    # حذف خطوط خالی پشت سر هم
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)

def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    }
    res = requests.post(url, json=payload)
    return res.ok

def send_telegram_photo(photo_url: str, caption: str = ""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHAT_ID,
        "photo": photo_url,
        "caption": caption[:1024] if caption else ""
    }
    res = requests.post(url, json=payload)
    return res.ok

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ مقادیر TELEGRAM_BOT_TOKEN یا TELEGRAM_CHAT_ID تنظیم نشده‌اند.")
        return

    url = f"https://t.me/s/{SOURCE_CHANNEL}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print(f"📡 در حال دریافت پیام‌ها از {url} ...")
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"❌ خطا در دسترسی به صفحه تلگرام: {response.status_code}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    messages = soup.find_all("div", class_="tgme_widget_message_wrap")

    if not messages:
        print("⚠️ پیامی یافت نشد.")
        return

    # پردازش آخرین ۵ پیام کانال
    latest_messages = messages[-5:]
    print(f"🔍 تعداد {len(latest_messages)} پیام جدید برای بررسی پیدا شد.")

    for msg in latest_messages:
        # استخراج متن
        text_elem = msg.find("div", class_="tgme_widget_message_text")
        raw_text = text_elem.get_text(separator="\n") if text_elem else ""
        cleaned_text = clean_text(raw_text)

        # استخراج عکس (در صورت وجود)
        photo_elem = msg.find("a", class_="tgme_widget_message_photo_wrap")
        photo_url = None
        if photo_elem and "style" in photo_elem.attrs:
            style = photo_elem["style"]
            match = re.search(r"background-image:url\('([^']+)'\)", style)
            if match:
                photo_url = match.group(1)

        # ارسال به تلگرام
        if photo_url:
            print("📸 در حال ارسال عکس به کانال خصوصی...")
            send_telegram_photo(photo_url, caption=cleaned_text)
        elif cleaned_text:
            print("📝 در حال ارسال پیام متنی به کانال خصوصی...")
            send_telegram_message(cleaned_text)

    print("✅ تمامی پیام‌ها با موفقیت بررسی و ارسال شدند.")

if __name__ == "__main__":
    main()

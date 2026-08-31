import os
import re
import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")
SOURCE_CHANNEL = "LiveScore_plus"

def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'@[A-Za-z0-9_]+', '', text)
    text = re.sub(r'https?://\S+|www\.\S+|t\.me/\S+', '', text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)

def send_telegram(method: str, payload: dict):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    res = requests.post(url, json=payload)
    if not res.ok:
        print(f"❌ خطای تلگرام ({method}): {res.text}")
    else:
        print(f"✅ {method} با موفقیت ارسال شد.")
    return res.ok

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ مقادیر TG_TOKEN یا TG_CHAT_ID تنظیم نشده‌اند.")
        return

    url = f"https://t.me/s/{SOURCE_CHANNEL}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print(f"📡 در حال دریافت پیام‌ها از {url} ...")
    response = requests.get(url, headers=headers)
    print(f"🌐 وضعیت پاسخ سرور: {response.status_code}")
    if response.status_code != 200:
        print("❌ دسترسی به صفحه وب کانال ممکن نشد.")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    messages = soup.find_all("div", class_="tgme_widget_message_wrap")
    print(f"🔎 تعداد پیام‌های یافت‌شده: {len(messages)}")

    if not messages:
        print("⚠️ هیچ پیامی یافت نشد.")
        return

    for msg in messages[-5:]:
        text_elem = msg.find("div", class_="tgme_widget_message_text")
        cleaned = clean_text(text_elem.get_text(separator="\n") if text_elem else "")

        photo_url = None
        photo_elem = msg.find("a", class_="tgme_widget_message_photo_wrap")
        if photo_elem and photo_elem.get("style"):
            match = re.search(r"background-image:url\('([^']+)'\)", photo_elem["style"])
            if match:
                photo_url = match.group(1)

        if photo_url:
            print("📸 ارسال عکس...")
            send_telegram("sendPhoto", {"chat_id": CHAT_ID, "photo": photo_url, "caption": cleaned[:1024]})
        elif cleaned:
            print("📝 ارسال پیام متنی...")
            send_telegram("sendMessage", {"chat_id": CHAT_ID, "text": cleaned, "disable_web_page_preview": True})

    print("✅ پایان اجرا.")

if __name__ == "__main__":
    main()

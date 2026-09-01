import os
import re
import sys
import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.environ.get("TG_TOKEN") or os.environ.get("TG_BOT_TOKEN")
CHAT_ID = os.environ.get("TG_CHAT_ID")
SOURCE_CHANNEL = "jozeiateRooz"
MY_CHANNEL_ID = "@majiix1"

def get_latest_post_from_channel(channel_username):
    url = f"https://t.me/s/{channel_username}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    print(f"🌐 Fetching latest calendar post from @{channel_username}...")
    response = requests.get(url, headers=headers, timeout=20)
    response.encoding = 'utf-8'

    if response.status_code != 200:
        print(f"❌ Failed to fetch channel. HTTP Status: {response.status_code}")
        sys.exit(1)

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # پیدا کردن همه پیام‌های متنی کانال
    messages = soup.find_all("div", class_="tgme_widget_message_text")
    if not messages:
        print("❌ No messages found in the channel preview.")
        sys.exit(1)

    # انتخاب آخرین پست متنی
    latest_msg = messages[-1]

    # تبدیل تگ‌های <br> به خط جدید برای حفظ چیدمان
    for br in latest_msg.find_all("br"):
        br.replace_with("\n")

    raw_text = latest_msg.get_text()
    return raw_text

def clean_and_brand_message(text):
    # 1. حذف لینک‌های t.me و آیدی‌های مبدأ
    # جایگزینی آیدی‌های کانال مبدأ با آیدی کانال شما
    cleaned = re.sub(r'@\w+', '', text)
    cleaned = re.sub(r'https?://t\.me/\S+', '', cleaned)
    
    # حذف خطوط اضافی یا تبلیغاتی انتهای پیام در صورت وجود
    lines = [line.rstrip() for line in cleaned.split('\n')]
    
    # پاکسازی فاصله‌های خالی پشت سر هم
    final_lines = []
    prev_empty = False
    for line in lines:
        if line == "":
            if not prev_empty:
                final_lines.append(line)
                prev_empty = True
        else:
            final_lines.append(line)
            prev_empty = False

    post_content = "\n".join(final_lines).strip()

    # 2. افزودن آیدی کانال شما به انتهای پست با دیزاین شیک
    final_message = f"{post_content}\n\n🆔 {MY_CHANNEL_ID}"
    return final_message

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    }

    print("🚀 Sending formatted calendar post to Telegram...")
    res = requests.post(url, json=payload, timeout=20)
    data = res.json()

    if res.status_code == 200 and data.get("ok"):
        print("🎉 Calendar post sent successfully to your channel!")
    else:
        print(f"❌ Telegram API Error: {data}")
        sys.exit(1)

if __name__ == "__main__":
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Error: TG_TOKEN or TG_CHAT_ID is missing!")
        sys.exit(1)

    raw_post = get_latest_post_from_channel(SOURCE_CHANNEL)
    ready_post = clean_and_brand_message(raw_post)
    
    print("\n--- Final Message Output ---\n")
    print(ready_post)
    print("\n----------------------------\n")
    
    send_to_telegram(ready_post)

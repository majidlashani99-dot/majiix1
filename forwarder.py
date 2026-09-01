import os
import re
import sys
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")
SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL", "SPORTinoTV").strip().lstrip("@")
FILTER_TEXT = os.getenv("FILTER_TEXT", "کنداکتور").strip()

REQUEST_TIMEOUT = 30
MAX_PAGES = 8
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
        return True
    try:
        dt_str = time_elem["datetime"]
        post_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        now_utc = datetime.now(timezone.utc)
        
        if (now_utc - post_dt).total_seconds() <= 86400:
            return True
        post_dt_iran = post_dt.astimezone(IRAN_TZ)
        return post_dt_iran.date() == datetime.now(IRAN_TZ).date()
    except Exception:
        return True

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
            print(f"❌ خطای تلگرام: {res_data}")
            return False
    except Exception as e:
        print(f"❌ خطای درخواست تلگرام: {e}")
        return False

def get_channel_messages():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "fa,en-US;q=0.9,en;q=0.8",
    }
    
    all_messages = []
    base_url = f"https://t.me/s/{SOURCE_CHANNEL}"
    current_url = base_url
    seen_ids = set()

    for page in range(MAX_PAGES):
        try:
            print(f"📥 بررسی صفحه {page + 1}: {current_url}")
            res = requests.get(current_url, headers=headers, timeout=REQUEST_TIMEOUT)
            if res.status_code != 200:
                print(f"⚠️ دریافت کد وضعیت: {res.status_code}")
                break
            
            soup = BeautifulSoup(res.text, "html.parser")
            msgs = soup.select("div.tgme_widget_message_wrap")
            if not msgs:
                break
            
            new_msgs = []
            min_post_id = None
            
            for m in msgs:
                msg_div = m.select_one("div.tgme_widget_message")
                if not msg_div:
                    continue
                post_attr = msg_div.get("data-post", "")
                if post_attr:
                    try:
                        p_id = int(post_attr.split("/")[-1])
                        if min_post_id is None or p_id < min_post_id:
                            min_post_id = p_id
                    except ValueError:
                        pass
                
                if post_attr not in seen_ids:
                    seen_ids.add(post_attr)
                    new_msgs.append(m)
            
            all_messages = new_msgs + all_messages
            
            if min_post_id:
                current_url = f"{base_url}?before={min_post_id}"
            else:
                break
        except Exception as e:
            print(f"⚠️ خطا در دریافت صفحه {page + 1}: {e}")
            break

    return all_messages

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ مقادیر TG_TOKEN یا TG_CHAT_ID در سکرت‌ها خالی هستند!")
        sys.exit(1)

    print(f"📡 در حال بررسی کانال @{SOURCE_CHANNEL}...")
    messages = get_channel_messages()
    print(f"📊 تعداد کل پست‌های بازخوانی‌شده: {len(messages)}")

    matched_posts = []
    filter_norm = normalize_text(FILTER_TEXT)

    for msg in messages:
        raw_text = msg.get_text(separator=" ", strip=True)
        norm_text = normalize_text(raw_text)
        time_elem = msg.find("time")

        if (filter_norm in norm_text or "کنداکتور" in norm_text) and is_recent_or_today(time_elem):
            text_elem = msg.select_one("div.tgme_widget_message_text")
            extracted_text = text_elem.get_text(separator="\n", strip=True) if text_elem else raw_text
            matched_posts.append((msg, extracted_text))

    if not matched_posts:
        print("⚠️ هیچ پستی با کلمه کنداکتور در ۲۴ ساعت گذشته یافت نشد.")
        return

    print(f"🎯 تعداد {len(matched_posts)} پست کنداکتور پیدا شد! در حال آماده‌سازی برای ارسال...")
    
    target_msg, raw_text = matched_posts[-1]
    clean_text_content = clean_caption(raw_text)
    photo_url = extract_photo_url(target_msg)

    if photo_url:
        print(f"📸 تصویر پیدا شد: {photo_url}")
        send_telegram("sendPhoto", {
            "chat_id": CHAT_ID,
            "photo": photo_url,
            "caption": clean_text_content[:1024]
        })
    else:
        print("📝 ارسال به صورت متنی...")
        send_telegram("sendMessage", {
            "chat_id": CHAT_ID,
            "text": clean_text_content[:4096],
            "disable_web_page_preview": True
        })

if __name__ == "__main__":
    main()

import os
import sys
import re
import io
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.getenv("TG_TOKEN")
TARGET_CHAT_ID = os.getenv("TG_CHAT_ID", "@majiix1")
MY_CHANNEL_ID = "@majiix1"
SOURCE_CHANNEL = "tvlivefootball"
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

PERSIAN_MONTHS = [
    "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"
]

def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd

def get_today_jalali_keywords():
    now = datetime.now(IRAN_TZ)
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    month_name = PERSIAN_MONTHS[jm]
    
    day_fa = str(jd).translate(FA_DIGITS)
    day_en = str(jd)
    
    keywords = [
        f"{day_fa} {month_name}",
        f"{day_en} {month_name}"
    ]
    return keywords, f"{day_fa} {month_name} {jy}"

def clean_and_brand_caption(text: str, jalali_today: str) -> str:
    """حذف آیدی‌ها و لینک‌های کانال مبدأ و جایگزینی با آیدی کانال شما"""
    if not text:
        return f"⚽️ کنداکتور پخش زنده مسابقات ({jalali_today})\n\n🆔 {MY_CHANNEL_ID}"

    # حذف لینک‌های t.me و telegram.me
    text = re.sub(r'https?://(?:www\.)?t\.me/[a-zA-Z0-9_+/]+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'https?://(?:www\.)?telegram\.me/[a-zA-Z0-9_+/]+', '', text, flags=re.IGNORECASE)
    
    # حذف تمام آیدی‌های مبدأ (شامل @tvlivefootball و ...)
    text = re.sub(r'@[a-zA-Z0-9_]+', '', text)
    
    # پاکسازی خطوط خالی پشت سر هم
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    cleaned_body = '\n'.join(lines)
    
    # اضافه کردن آیدی نهایی شما
    final_caption = f"{cleaned_body}\n\n🆔 {MY_CHANNEL_ID}"
    
    # محدودیت تلگرام برای کپشن عکس ۱۰۲۴ کاراکتر است
    if len(final_caption) > 1020:
        cutoff = 1010 - len(f"\n...\n\n🆔 {MY_CHANNEL_ID}")
        final_caption = f"{cleaned_body[:cutoff]}\n...\n\n🆔 {MY_CHANNEL_ID}"
        
    return final_caption

def upload_and_send_photo(photo_url: str, caption: str):
    """دانلود باینری عکس و آپلود مستقیم به تلگرام"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    img_resp = requests.get(photo_url, headers=headers, timeout=30)
    
    if img_resp.status_code != 200:
        print(f"⚠️ خطا در دانلود عکس (کد {img_resp.status_code})، ارسال به صورت متنی...")
        return send_telegram_message(caption)

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    files = {
        "photo": ("conductor.jpg", io.BytesIO(img_resp.content), "image/jpeg")
    }
    data = {
        "chat_id": TARGET_CHAT_ID,
        "caption": caption
    }
    res = requests.post(url, data=data, files=files, timeout=35)
    return res.json()

def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TARGET_CHAT_ID,
        "text": text
    }
    res = requests.post(url, json=payload, timeout=25)
    return res.json()

def main():
    if not BOT_TOKEN or not TARGET_CHAT_ID:
        print("❌ ارور: متغیرهای TG_TOKEN یا TG_CHAT_ID در GitHub Secrets تنظیم نشده‌اند!")
        sys.exit(1)

    keywords, jalali_today = get_today_jalali_keywords()
    print(f"🔍 تاریخ هدف: {jalali_today} | کلمات کلیدی: {keywords}")

    url = f"https://t.me/s/{SOURCE_CHANNEL}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    response = requests.get(url, headers=headers, timeout=25)
    if response.status_code != 200:
        print(f"❌ خطا در لود کانال تلگرام: وضعیت {response.status_code}")
        sys.exit(1)

    soup = BeautifulSoup(response.text, "html.parser")
    messages = soup.select(".tgme_widget_message_wrap")

    print(f"📊 تعداد کل پیام‌های دریافت شده از صفحه: {len(messages)}")

    matched_post = None

    # جستجوی پیام از جدیدترین به قدیمی‌ترین
    for msg in reversed(messages):
        msg_elem = msg.select_one(".tgme_widget_message")
        if not msg_elem:
            continue

        raw_id = msg_elem.get("data-post", "")
        text_elem = msg.select_one(".tgme_widget_message_text")
        text = text_elem.get_text(separator="\n", strip=True) if text_elem else ""

        # استخراج عکس
        photo_elem = msg.select_one(".tgme_widget_message_photo_wrap")
        photo_url = ""
        if photo_elem:
            style = photo_elem.get("style", "")
            match = re.search(r"url\('?(.*?)'?\)", style)
            if match:
                photo_url = match.group(1)

        is_today = any(kw in text for kw in keywords)
        is_result = "نتایج" in text or "دیروز" in text
        is_conductor = ("برنامه مسابقات" in text or "پخش_زنده" in text or "پخش زنده" in text or "مسابقات مهم" in text)

        if is_today and not is_result and (is_conductor or photo_url):
            matched_post = {
                "id": raw_id,
                "text": text,
                "photo": photo_url
            }
            break

    # فال‌بک در صورت عدم تطابق نام تاریخ
    if not matched_post:
        print("⚠️ پست دقیق با تاریخ امروز پیدا نشد، بررسی آخرین پست برنامه مسابقات...")
        for msg in reversed(messages):
            msg_elem = msg.select_one(".tgme_widget_message")
            if not msg_elem:
                continue
            raw_id = msg_elem.get("data-post", "")
            text_elem = msg.select_one(".tgme_widget_message_text")
            text = text_elem.get_text(separator="\n", strip=True) if text_elem else ""
            photo_elem = msg.select_one(".tgme_widget_message_photo_wrap")
            photo_url = ""
            if photo_elem:
                match = re.search(r"url\('?(.*?)'?\)", photo_elem.get("style", ""))
                if match:
                    photo_url = match.group(1)
            
            if ("برنامه مسابقات" in text or "پخش_زنده" in text) and "نتایج" not in text:
                matched_post = {"id": raw_id, "text": text, "photo": photo_url}
                break

    if not matched_post:
        print("❌ هیچ پستی برای ارسال پیدا نشد.")
        sys.exit(1)

    print(f"🚀 در حال آماده‌سازی و ارسال پست: {matched_post['id']}")
    
    # تولید کپشن اختصاصی با آیدی @majiix1
    final_caption = clean_and_brand_caption(matched_post["text"], jalali_today)

    # ارسال به تلگرام
    if matched_post["photo"]:
        res = upload_and_send_photo(matched_post["photo"], final_caption)
    else:
        res = send_telegram_message(final_caption)

    print(f"📩 پاسخ نهایی تلگرام: {res}")
    if res.get("ok"):
        print(f"✅ پست با موفقیت به کانال {TARGET_CHAT_ID} ارسال شد!")
    else:
        print(f"❌ خطا از طرف تلگرام: {res.get('description')}")
        sys.exit(1)

if __name__ == "__main__":
    main()

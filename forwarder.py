import os
import sys
import re
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.getenv("TG_TOKEN")
TARGET_CHAT_ID = os.getenv("TG_CHAT_ID")
SOURCE_CHANNEL = "tvlivefootball"
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

# تبدیل اعداد انگلیسی به فارسی برای جستجوی دقیق در متن تاریخ کانال
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

PERSIAN_MONTHS = [
    "", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"
]

def gregorian_to_jalali(gy, gm, gd):
    """تبدیل تاریخ میلادی به هجری شمسی دقیق"""
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
    """تولید کلمات کلیدی تاریخ امروز شمسی (مثلاً: ۱۰ شهریور و 10 شهریور)"""
    now = datetime.now(IRAN_TZ)
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    month_name = PERSIAN_MONTHS[jm]
    
    day_fa = str(jd).translate(FA_DIGITS)
    day_en = str(jd)
    
    # کلمات کلیدی برای تطابق دقیق با پست‌های امروز
    keywords = [
        f"{day_fa} {month_name}",
        f"{day_en} {month_name}"
    ]
    return keywords, f"{day_fa} {month_name} {jy}"

def forward_from_channel(msg_id: int):
    """فوروارد مستقیم پیام از کانال مرجع به کانال شما"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/forwardMessage"
    payload = {
        "chat_id": TARGET_CHAT_ID,
        "from_chat_id": f"@{SOURCE_CHANNEL}",
        "message_id": msg_id
    }
    res = requests.post(url, json=payload, timeout=25)
    return res.json()

def send_photo_with_caption(photo_url: str, caption_text: str):
    """در صورت نیاز، ارسال تصویر با کپشن به عنوان روش پشتیبان"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": TARGET_CHAT_ID,
        "photo": photo_url,
        "caption": caption_text,
        "parse_mode": "HTML"
    }
    res = requests.post(url, json=payload, timeout=25)
    return res.json()

def search_and_send_today_conductor():
    keywords, jalali_today = get_today_jalali_keywords()
    print(f"🔍 در حال جستجوی کنداکتور امروز ({jalali_today}) در کانال @{SOURCE_CHANNEL}...")

    # دریافت نسخه وب کانال
    url = f"https://t.me/s/{SOURCE_CHANNEL}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    res = requests.get(url, headers=headers, timeout=25)
    if res.status_code != 200:
        print(f"❌ خطا در باز کردن کانال: وضعیت {res.status_code}")
        sys.exit(1)

    soup = BeautifulSoup(res.text, "html.parser")
    messages = soup.select(".tgme_widget_message_wrap")

    matched_posts = []

    # پیمایش پیام‌ها از جدیدترین به قدیمی‌ترین
    for msg in reversed(messages):
        msg_elem = msg.select_one(".tgme_widget_message")
        if not msg_elem:
            continue

        raw_id = msg_elem.get("data-post", "")
        if "/" not in raw_id:
            continue
        msg_id = int(raw_id.split("/")[-1])

        text_elem = msg.select_one(".tgme_widget_message_text")
        text = text_elem.get_text(separator=" ", strip=True) if text_elem else ""

        # بررسی وجود کلمات کلیدی تاریخ امروز و فیلتر کردن پست‌های نتایج دیروز
        has_today = any(kw in text for kw in keywords)
        is_result_post = "نتایج" in text or "دیروز" in text

        # اولویت با پست برنامه بازی‌ها یا پخش زنده امروز است
        if has_today and not is_result_post:
            if "برنامه مسابقات" in text or "پخش_زنده" in text or "پخش زنده" in text or "کنداکتور" in text:
                # استخراج عکس در صورت وجود
                photo_elem = msg.select_one(".tgme_widget_message_photo_wrap")
                photo_url = ""
                if photo_elem and "background-image" in photo_elem.get("style", ""):
                    match = re.search(r"url\('?(.*?)'?\)", photo_elem["style"])
                    if match:
                        photo_url = match.group(1)

                matched_posts.append({
                    "id": msg_id,
                    "text": text,
                    "photo": photo_url
                })

    if not matched_posts:
        print(f"⚠️ پستی با تاریخ امروز ({jalali_today}) پیدا نشد.")
        return False

    # ارسال پست کنداکتور پیدا شده
    target_post = matched_posts[0]
    print(f"🎯 پست هدف پیدا شد (Message ID: {target_post['id']})")
    
    # فوروارد کردن پست اصلی
    result = forward_from_channel(target_post["id"])
    
    if result.get("ok"):
        print("✅ پیام/جدول بازی‌های امروز با موفقیت فوروارد شد!")
        return True
    else:
        print(f"⚠️ فوروارد با محدودیت روبه‌رو شد ({result.get('description')})، تلاش برای ارسال مستقیم عکس/متن...")
        if target_post["photo"]:
            send_photo_with_caption(target_post["photo"], f"💠 <b>کنداکتور مسابقات امروز ({jalali_today})</b>\n\n🆔 @Doroudcity")
            print("✅ تصویر جدول با موفقیت ارسال شد.")
            return True
        else:
            print("❌ ارسال ناموفق بود.")
            return False

def main():
    if not BOT_TOKEN or not TARGET_CHAT_ID:
        print("❌ متغیرهای TG_TOKEN یا TG_CHAT_ID تنظیم نشده‌اند.")
        sys.exit(1)

    success = search_and_send_today_conductor()
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()

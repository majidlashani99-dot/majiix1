import os
import requests
from bs4 import BeautifulSoup
import jdatetime
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

URL = "https://moj3.ir/price/"
IMG_FILE = "Gold_Dollar_Report.png"

def fix(text):
    """رفع مشکل جدانویسی و برعکس شدن حروف فارسی"""
    if not text:
        return ""
    # تنظیمات دقیق reshaper برای اتصال کامل کاراکترهای فارسی
    reshaped_text = arabic_reshaper.reshape(str(text))
    bidi_text = get_display(reshaped_text)
    return bidi_text

def fetch_table():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    print(f"در حال دریافت قیمت‌ها از {URL} ...")
    try:
        r = requests.get(URL, headers=headers, timeout=25)
        r.raise_for_status()
    except Exception as e:
        print(f"خطا در اتصال به سایت: {e}")
        return [], []

    soup = BeautifulSoup(r.text, 'html.parser')
    table = soup.find('table')
    if not table:
        print("خطا: هیچ جدولی در صفحه پیدا نشد.")
        return [], []

    headers_row = []
    rows = []
    all_tr = table.find_all('tr')
    for tr in all_tr:
        cells = tr.find_all(['th', 'td'])
        texts = [c.get_text(strip=True) for c in cells]
        if not texts:
            continue
        if tr.find('th') and not headers_row:
            headers_row = texts
        else:
            rows.append(texts)

    print(f"{len(rows)} ردیف داده استخراج شد.")
    return headers_row, rows

def download_font():
    """دانلود فونت وزیرمتن برای ساخت عکس زیبا"""
    base = "https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/"
    for name in ["Vazirmatn-Bold.ttf", "Vazirmatn-Regular.ttf"]:
        if not os.path.exists(name):
            print(f"در حال دانلود فونت {name}...")
            f = requests.get(base + name)
            with open(name, "wb") as out:
                out.write(f.content)

def make_image(headers_row, rows, date_text):
    download_font()

    W = 920
    ROW_H = 58
    HEADER_H = 62
    TITLE_H = 120
    H = TITLE_H + HEADER_H + (ROW_H * len(rows)) + 40

    bg = (15, 23, 42)          # پس‌زمینه سرمه‌ای تیره
    header_bg = (2, 132, 199)  # هدر آبی
    row_bg1 = (30, 41, 59)
    row_bg2 = (24, 33, 50)
    text_light = (241, 245, 249)
    accent = (250, 204, 21)    # طلایی

    img = Image.new('RGB', (W, H), bg)
    draw = ImageDraw.Draw(img)

    f_title = ImageFont.truetype("Vazirmatn-Bold.ttf", 32)
    f_header = ImageFont.truetype("Vazirmatn-Bold.ttf", 22)
    f_cell = ImageFont.truetype("Vazirmatn-Regular.ttf", 21)
    f_date = ImageFont.truetype("Vazirmatn-Regular.ttf", 18)

    # سرتیتر و تاریخ
    draw.text((W // 2, 45), fix("قیمت لحظه‌ای طلا، سکه و ارز"), font=f_title, fill=accent, anchor="mm")
    draw.text((W // 2, 85), fix(f"{date_text}  |  منبع: moj3.ir"), font=f_date, fill=(148, 163, 184), anchor="mm")

    # ردیف هدر
    y = TITLE_H
    draw.rectangle([25, y, W - 25, y + HEADER_H], fill=header_bg)
    draw.text((W - 50, y + HEADER_H // 2), fix("نام دارایی"), font=f_header, fill=text_light, anchor="rm")
    draw.text((W // 2, y + HEADER_H // 2), fix("قیمت (تومان)"), font=f_header, fill=text_light, anchor="mm")
    draw.text((80, y + HEADER_H // 2), fix("تغییرات"), font=f_header, fill=text_light, anchor="lm")

    # ردیف‌های داده‌ها
    y += HEADER_H
    for idx, row in enumerate(rows):
        color = row_bg1 if idx % 2 == 0 else row_bg2
        draw.rectangle([25, y, W - 25, y + ROW_H], fill=color)
        
        if len(row) >= 1:
            # نام دارایی (راست‌چین)
            draw.text((W - 50, y + ROW_H // 2), fix(row[0]), font=f_cell, fill=accent, anchor="rm")
            
        if len(row) >= 2:
            # قیمت (وسط‌چین)
            draw.text((W // 2, y + ROW_H // 2), fix(row[1]), font=f_cell, fill=text_light, anchor="mm")
        
        # درصد تغییرات (چپ‌چین با رنگ مشخص)
        change = next((c for c in row[2:] if '%' in c), "")
        if change:
            c_color = (74, 222, 128) if '+' in change else (248, 113, 113)
            # در صورتی که تغییرات 0 یا بدون علامت باشه رنگ خنثی
            if '+' not in change and '-' not in change:
                c_color = (148, 163, 184)
            draw.text((80, y + ROW_H // 2), fix(change), font=f_cell, fill=c_color, anchor="lm")

        y += ROW_H

    img.save(IMG_FILE)
    print(f"تصویر با موفقیت ساخته شد: {IMG_FILE}")
    return IMG_FILE

def send_to_telegram(image_file, date_text):
    bot_token = os.environ.get("TG_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")
    if not bot_token or not chat_id:
        print("خطا: TG_TOKEN یا TG_CHAT_ID تنظیم نشده است.")
        return

    caption = (
        f"<b>💰 قیمت لحظه‌ای طلا، سکه و ارز</b>\n\n"
        f"📅 {date_text}\n\n"
        f"📊 منبع: موج سوم (moj3.ir)\n"
        f"🆔 @Doroudcity"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    with open(image_file, 'rb') as photo:
        res = requests.post(
            url,
            data={'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'},
            files={'photo': photo}
        )

    if res.status_code == 200:
        print("✅ عکس قیمت‌ها با موفقیت به تلگرام ارسال شد.")
    else:
        print(f"خطای تلگرام:\n{res.text}")

if __name__ == "__main__":
    days = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یک‌شنبه"]
    months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
    today = jdatetime.date.today()
    date_text = f"{days[today.weekday()]} {today.day} {months[today.month - 1]} {today.year}"

    headers_row, rows = fetch_table()
    if rows:
        img = make_image(headers_row, rows, date_text)
        send_to_telegram(img, date_text)
    else:
        print("داده‌ای برای ارسال وجود ندارد.")

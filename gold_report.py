import os
import requests
from bs4 import BeautifulSoup
import jdatetime
import pytz
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper

URL = "https://moj3.ir/price/"
IMG_FILE = "Gold_Dollar_Report.png"

# تنظیمات پیشرفته برای اتصال صحیح تمام حروف و ارقام فارسی
reshaper_config = {
    'delete_harakat': False,
    'support_ligatures': True,
    'language': 'Persian'
}
reshaper = arabic_reshaper.ArabicReshaper(configuration=reshaper_config)

def fix(text):
    """رفع مشکل جدانویسی حروف فارسی"""
    if not text:
        return ""
    return reshaper.reshape(str(text))

def get_persian_date():
    """محاسبه دقیق تاریخ و روز هفته بر مبنای افق زمانی تهران"""
    tehran_tz = pytz.timezone('Asia/Tehran')
    now_tehran = jdatetime.datetime.now(tehran_tz)
    
    # ترتیب صحیح در jdatetime: شنبه = 0، جمعه = 6
    days = ["شنبه", "یک‌شنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]
    months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
    
    day_name = days[now_tehran.weekday()]
    month_name = months[now_tehran.month - 1]
    
    date_text = f"{day_name} {now_tehran.day} {month_name} {now_tehran.year}"
    return date_text

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
    """دانلود فونت وزیرمتن"""
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
    H = TITLE_H + HEADER_H + (ROW_H * len(rows)) + 30

    bg = (15, 23, 42)          "{len(rows)} ردیف داده استخراج شد.")
    return headers_row, rows

def download_font():
    """دانلود فونت وزیرمتن"""
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
    H = TITLE_H + HEADER_H + (ROW_H * len(rows)) + 30

    bg = (15, 23, 42)          # پس‌زمینه سرمه‌ای تیره
    header_bg = (2, 132, 199)  # هدر آبی
    row_bg1 = (30, 41, 59)
    row_bg2 = (24, 33, 50)
    text_light = (241, 245, 249)
    accent = (250, 204, 21)    # طلایی

    img = Image.new('RGB', (W, H), bg)
    draw = ImageDraw.Draw(img)

    ((W - 50, y + HEADER_H // 2), fix("نام دارایی"), font=f_header, fill=text_light, anchor="rm", direction="rtl")
    draw.text((W // 2, y + HEADER_H // 2), fix("قیمت (تومان)"), font=f_header, fill=text_light, anchor="mm", direction="rtl")
    draw.text((60, y + HEADER_H // 2), fix("تغییرات"), font=f_header, fill=text_light, anchor="lm")

    # ردیف‌های داده‌ها
    y += HEADER_H
    for idx, row in enumerate(rows):
        color = row_bg1 if idx % 2 == 0 else row_bg2
        draw.rectangle([25, y, W - 25, y + ROW_H], fill=color)
        
        if len(row) >= 1:
            # نام دارایی (راست‌چین)
            draw.text((W - 50, y + ROW_H // 2), fix(row[0]), font=f_cell, fill=accent, anchor="rm", direction="rtl")
            
        if len(row) >= 2:
            # قیمت (وسط‌چین)
            draw.text((W // 2, y + ROW_H // 2), str(row[1]), font=f_cell, fill=text_light, anchor="mm")
        
        # درصد تغییرات (چپ‌چین)
        change = next((c for c in row[2:] if '%' in c), "")
        if change:
            c_color = (74, 222, 128) if '+' in change else (248, 113, 113)
            if '+' not in change and '-' not in change:
                c_color = (148, 163, 184)
            draw.text((60, y + ROW_H // 2), str(change), font=f_cell, fill=c_color, anchor="lm")

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

    # کپشن ساده و مرتب
    caption = (
        f"<b>💰 قیمت لحظه‌ای طلا، سکه و ارز</b>\n\n"
        f"📅 {date_text}"
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
    date_text = get_persian_date()
    headers_row, rows = fetch_table()
    if rows:
        img = make_image(headers_row, rows, date_text)
        send_to_telegram(img, date_text)
    else:
        print("داده‌ای برای ارسال وجود ندارد.")

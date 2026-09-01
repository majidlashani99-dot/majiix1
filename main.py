import os
import requests
from bs4 import BeautifulSoup
import jdatetime
import pytz

# کتابخانه‌های PDF و فارسی
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from bidi.algorithm import get_display

def fix_text(text):
    """اصلاح متون فارسی برای نمایش صحیح در PDF بدون حروف مقطع"""
    if not text:
        return ""
    reshaped = arabic_reshaper.reshape(str(text))
    return get_display(reshaped)

def get_persian_date():
    """دریافت دقیق تاریخ و روز هفته بر اساس ساعت و تقویم تهران"""
    tehran_tz = pytz.timezone('Asia/Tehran')
    # تبدیل تاریخ روز جاری به تقویم شمسی بر مبنای افق تهران
    now_tehran = jdatetime.datetime.now(tehran_tz)
    
    # اسامی استاندارد روزهای هفته در jdatetime (شنبه = 0 تا جمعه = 6)
    days = ["شنبه", "یک‌شنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"]
    months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
    
    day_name = days[now_tehran.weekday()]
    month_name = months[now_tehran.month - 1]
    
    date_text_str = f"{day_name} {now_tehran.day} {month_name} {now_tehran.year}"
    date_num_str = now_tehran.strftime("%Y/%m/%d")
    
    return date_text_str, date_num_str

def fetch_data():
    url = "https://ledc.ir/%D8%AE%D8%A7%D9%85%D9%88%D8%B4%DB%8C%D9%87%D8%A7%DB%8C-%D8%A8%D8%B1%D9%86%D8%A7%D9%85%D9%87-%D8%B1%DB%8C%D8%B2%DB%8C-%D8%B4%D8%AF%D9%87"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    print(f"در حال دریافت اطلاعات از:\n{url}...")
    try:
        response = requests.get(url, headers=headers, timeout=25)
        response.raise_for_status()
    except Exception as e:
        print(f"خطا در اتصال به سایت: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    rows_data = []
    headers_saved = False

    # لیست شهرهای متفرقه جهت جلوگیری از تداخل
    other_cities = ["ازنا", "بروجرد", "خرم آباد", "خرم‌آباد", "الیگودرز", "کوهدشت", "پلدختر", "الشتر", "نورآباد", "چگنی"]

    # جستجوی تمام جداول
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        for tr in rows:
            tds = tr.find_all(['td', 'th'])
            row_text = [td.get_text(strip=True) for td in tds]
            
            if not row_text or len(row_text) < 3:
                continue

            # استخراج و ذخیره هدر اصلی جدول در صورت وجود
            if not headers_saved and any(h in row_text for h in ["شهرستان", "تاریخ", "ساعت", "منطقه", "فیدر"]):
                rows_data.append(row_text)
                headers_saved = True
                continue

            # فیلتر اختصاصی: حتماً کلمه «دورود» وجود داشته باشد و شامل سایر شهرها نباشد
            is_doroud = any("دورود" in text for text in row_text)
            has_conflict = any(any(city in text for city in other_cities) for text in row_text)
            
            if is_doroud and not has_conflict:
                rows_data.append(row_text)

    return rows_data

def generate_pdf(data, date_text_str, filename="Doroud_Outage_Report.pdf"):
    # دانلود فونت فارسی Vazirmatn در صورت عدم وجود
    font_url = "https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/Vazirmatn-Regular.ttf"
    if not os.path.exists("Vazirmatn.ttf"):
        print("در حال دانلود فونت فارسی Vazirmatn...")
        r = requests.get(font_url)
        with open("Vazirmatn.ttf", "wb") as f:
            f.write(r.content)

    pdfmetrics.registerFont(TTFont('Vazirmatn', 'Vazirmatn.ttf'))

    # ساخت فایل PDF افقی (Landscape)
    doc = SimpleDocTemplate(
        filename,
        pagesize=landscape(letter),
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Normal'],
        fontName='Vazirmatn',
        fontSize=14,
        leading=20,
        alignment=1, # وسط چین
        textColor=colors.HexColor("#1e293b")
    )
    
    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontName='Vazirmatn',
        fontSize=9,
        leading=13,
        alignment=1, # وسط چین
        textColor=colors.HexColor("#0f172a")
    )

    elements = []

    # تیتر گزارش
    title_p = Paragraph(fix_text(f"برنامه خاموشی‌های برق شهرستان دورود - {date_text_str}"), title_style)
    elements.append(title_p)
    elements.append(Spacer(1, 15))

    # اگر فقط هدر بود یا کلاً دیتایی نبود
    if len(data) <= 1:
        empty_msg = Paragraph(fix_text("هیچ برنامه خاموشی جدیدی برای شهرستان دورود در تاریخ امروز ثبت نشده است."), title_style)
        elements.append(empty_msg)
    else:
        table_rows = []
        for row in data:
            formatted_row = [Paragraph(fix_text(cell), cell_style) for cell in row]
            # معکوس کردن ستون‌ها جهت چیدمان درست راست به چپ (RTL)
            table_rows.append(formatted_row[::-1])

        report_table = Table(table_rows, repeatRows=1)
        report_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0284c7")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(report_table)

    doc.build(elements)
    print(f"فایل با موفقیت ساخته شد: {filename}")
    return filename

def send_to_telegram(pdf_file, date_text_str, date_num_str):
    bot_token = os.environ.get("TG_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")

    if not bot_token or not chat_id:
        print("خطا: مقادیر TG_TOKEN یا TG_CHAT_ID در سکرت‌ها تنظیم نشده‌اند.")
        return

    # پیام زیر فایل (کپشن کاملاً تمیز بدون آیدی کانال)
    caption = (
        f"⚡️ <b>برنامه خاموشی برق شهرستان دورود</b>\n\n"
        f"📅 تاریخ: <b>{date_text_str}</b> ({date_num_str})\n\n"
        f"⚠️ لطفاً جهت جلوگیری از آسیب به وسایل برقی، تمهیدات لازم را در ساعات اعلامی در نظر داشته باشید."
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    with open(pdf_file, 'rb') as doc:
        files = {'document': doc}
        data = {
            'chat_id': chat_id,
            'caption': caption,
            'parse_mode': 'HTML'
        }
        res = requests.post(url, data=data, files=files)
        if res.status_code == 200:
            print("✅ فایل و گزارش با موفقیت به تلگرام ارسال شد.")
        else:
            print(f"خطای تلگرام:\n{res.text}")

if __name__ == "__main__":
    date_text, date_num = get_persian_date()
    rows = fetch_data()
    pdf_path = generate_pdf(rows, date_text)
    send_to_telegram(pdf_path, date_text, date_num)

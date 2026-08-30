import os
import sys
import requests
from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from bidi.algorithm import get_display

# --- ۱. تنظیمات تلگرام و سایت ---
TG_TOKEN = os.environ.get("TG_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")
SITE_URL = "https://www.ledc.ir"

def reshape_fa(text):
    """اصلاح حروف و راست‌چین کردن متن فارسی"""
    if not text:
        return ""
    reshaped_text = arabic_reshaper.reshape(str(text))
    return get_display(reshaped_text)

def download_persian_font():
    """دانلود فونت فارسی استاندارد Vazirmatn برای نمایش درست در سرور اوبونتو گیت‌هاب"""
    font_url = "https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/fonts/ttf/Vazirmatn-Regular.ttf"
    font_path = "Vazirmatn.ttf"
    if not os.path.exists(font_path):
        print("در حال دانلود فونت فارسی...")
        r = requests.get(font_url, timeout=30)
        with open(font_path, "wb") as f:
            f.write(r.content)
    pdfmetrics.registerFont(TTFont("Vazir", font_path))

def fetch_data():
    """استخراج اطلاعات خاموشی دورود از سایت توزیع برق لرستان"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    items = []
    try:
        res = requests.get(SITE_URL, headers=headers, timeout=20)
        res.encoding = 'utf-8'
        soup = BeautifulSoup(res.text, "html.parser")
        
        # استخراج عناوین و محتواهای مرتبط با خاموشی یا اطلاعیه‌ها
        elements = soup.find_all(["p", "div", "td", "li", "span"])
        for el in elements:
            txt = el.get_text().strip()
            if any(k in txt for k in ["دورود", "خاموشی", "برنامه", "قطعی"]) and len(txt) > 15:
                if txt not in items and len(items) < 25:
                    items.append(txt)
    except Exception as e:
        print(f"خطا در دریافت داده: {e}")
        
    if not items:
        items = ["امروز اطلاعیه خاموشی جدیدی برای شهرستان دورود در سامانه توزیع برق ثبت نشده است."]
    return items

def generate_pdf(items, filename="Doroud_Outage_Report.pdf"):
    """تولید PDF شیک با ساپورت کامل فارسی RTL"""
    download_persian_font()
    
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        rightMargin=20,
        leftMargin=20,
        topMargin=25,
        bottomMargin=25
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        fontName='Vazir',
        fontSize=16,
        leading=22,
        alignment=1, # وسط چین
        textColor=colors.HexColor("#1A365D")
    )
    
    body_style = ParagraphStyle(
        'BodyStyle',
        fontName='Vazir',
        fontSize=11,
        leading=18,
        alignment=2, # راست چین
        textColor=colors.HexColor("#2D3748")
    )
    
    story = []
    
    # تیتر گزارش
    title_text = reshape_fa("⚡️ گزارش خاموشی‌های برنامه‌ریزی‌شده شهرستان دورود")
    story.append(Paragraph(title_text, title_style))
    story.append(Spacer(1, 15))
    
    # ساخت جدول داده‌ها
    table_data = []
    for idx, item in enumerate(items, 1):
        reshaped_item = reshape_fa(f"{idx}- {item}")
        table_data.append([Paragraph(reshaped_item, body_style)])
        
    t = Table(table_data, colWidths=[520])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F7FAFC")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    
    story.append(t)
    doc.build(story)
    print(f"فایل PDF فارسی با نام {filename} با موفقیت ساخته شد.")
    return filename

def send_to_telegram(pdf_file):
    """ارسال فایل PDF به تلگرام با مدیریت دقیق خطا"""
    if not TG_TOKEN or not TG_CHAT_ID:
        print("خطا: مقادیر TG_TOKEN یا TG_CHAT_ID در سکرت‌ها تعریف نشده‌اند!")
        sys.exit(1)
        
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendDocument"
    caption = "⚡️ گزارش روزانه خاموشی برنامه‌ریزی‌شده شهرستان دورود"
    
    with open(pdf_file, "rb") as doc:
        files = {"document": doc}
        data = {
            "chat_id": TG_CHAT_ID,
            "caption": caption
        }
        print("در حال ارسال فایل به سرورهای تلگرام...")
        res = requests.post(url, data=data, files=files, timeout=40)
        
    res_data = res.json()
    if res_data.get("ok"):
        print("✅ فایل با موفقیت در تلگرام ارسال شد!")
    else:
        print(f"❌ خطا از طرف تلگرام: {res_data}")
        sys.exit(1)

if __name__ == "__main__":
    data = fetch_data()
    pdf_path = generate_pdf(data)
    send_to_telegram(pdf_path)

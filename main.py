import os
import sys
import requests
from bs4 import BeautifulSoup
import arabic_reshaper
from bidi.algorithm import get_display

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def fix_text(text: str) -> str:
    """اصلاح متون فارسی و راست‌به‌چپ برای موتور ReportLab"""
    if not text:
        return ""
    try:
        reshaped_text = arabic_reshaper.reshape(str(text))
        return get_display(reshaped_text)
    except Exception:
        return str(text)

def download_font():
    """دانلود فونت فارسی استاندارد در صورت عدم وجود"""
    font_path = "Vazirmatn-Regular.ttf"
    if not os.path.exists(font_path):
        print("در حال دانلود فونت فارسی Vazirmatn...")
        url = "https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/Vazirmatn-Regular.ttf"
        res = requests.get(url, timeout=30)
        with open(font_path, "wb") as f:
            f.write(res.content)
    pdfmetrics.registerFont(TTFont("Vazirmatn", font_path))

def fetch_doroud_outages():
    """دریافت اطلاعیه‌ها از سایت توزیع برق لرستان"""
    url = "https://ledc.ir"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    
    records = []
    try:
        response = requests.get(url, headers=headers, timeout=25, verify=False)
        response.encoding = "utf-8"
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            # استخراج تمام تیترها و متون مهم مرتبط
            elements = soup.find_all(["p", "div", "h2", "h3", "li", "span"])
            for el in elements:
                text = el.get_text(strip=True)
                if len(text) > 15 and ("دورود" in text or "خاموشی" in text or "برق" in text or "برنامه" in text):
                    if text not in records:
                        records.append(text)
    except Exception as e:
        print(f"خطا در برقراری ارتباط با سرور: {e}")
        
    if not records:
        records.append("در حال حاضر برنامه خاموشی جدیدی برای شهرستان دورود در سامانه درج نشده است.")
        
    return records

def generate_pdf(data_list, output_filename="Doroud_Outage_Report.pdf"):
    """ساخت فایل PDF چندصفحه‌ای با صفحه‌بندی پایدار"""
    download_font()
    
    # حاشیه استاندارد
    doc = SimpleDocTemplate(
        output_filename,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'PersianTitle',
        parent=styles['Normal'],
        fontName='Vazirmatn',
        fontSize=16,
        leading=22,
        alignment=1,  # وسط‌چین
        textColor=colors.HexColor("#1a365d")
    )
    
    body_style = ParagraphStyle(
        'PersianBody',
        parent=styles['Normal'],
        fontName='Vazirmatn',
        fontSize=10,
        leading=16,
        alignment=2,  # راست‌چین
        textColor=colors.HexColor("#2d3748"),
        wordWrap='RTL'
    )
    
    meta_style = ParagraphStyle(
        'PersianMeta',
        parent=styles['Normal'],
        fontName='Vazirmatn',
        fontSize=8,
        leading=12,
        alignment=1,
        textColor=colors.HexColor("#718096")
    )

    story = []
    
    # عنوان گزارش
    story.append(Paragraph(fix_text("گزارش وضعیت و اطلاعیه‌های برق شهرستان دورود"), title_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3182ce"), spaceAfter=12))
    
    # درج اطلاعیه‌ها به صورت پاراگراف‌های مجزا
    for idx, item in enumerate(data_list, 1):
        # تمیزکاری متن‌های بیش از حد طولانی برای جلوگیری از سرریز صفحه
        cleaned_item = item.strip()
        if len(cleaned_item) > 600:
            cleaned_item = cleaned_item[:600] + "..."
            
        entry_text = f"<b>{idx}.</b> {cleaned_item}"
        story.append(Paragraph(fix_text(entry_text), body_style))
        story.append(Spacer(1, 8))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=8))
        
    story.append(Spacer(1, 15))
    story.append(Paragraph(fix_text("تهیه شده توسط سیستم هوشمند مانیتورینگ دورود"), meta_style))
    
    doc.build(story)
    print(f"فایل با موفقیت تولید شد: {output_filename}")
    return output_filename

def send_telegram(file_path):
    """ارسال فایل PDF تولیدشده به تلگرام"""
    bot_token = os.environ.get("TG_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("توکن تلگرام یا شناسه چت تنظیم نشده است. مرحله ارسال نادیده گرفته شد.")
        return

    telegram_api_url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    caption_text = fix_text("📄 گزارش جدید خاموشی و اطلاعیه‌های برق دورود")
    
    with open(file_path, "rb") as doc_file:
        files = {"document": doc_file}
        data = {"chat_id": chat_id, "caption": "📄 گزارش جدید خاموشی و اطلاعیه‌های برق شهرستان دورود"}
        
        try:
            res = requests.post(telegram_api_url, data=data, files=files, timeout=40)
            if res.status_code == 200:
                print("گزارش با موفقیت در تلگرام ارسال شد.")
            else:
                print(f"خطای تلگرام ({res.status_code}): {res.text}")
        except Exception as e:
            print(f"خطا در ارتباط با سرور تلگرام: {e}")

if __name__ == "__main__":
    data = fetch_doroud_outages()
    pdf_path = generate_pdf(data)
    send_telegram(pdf_path)

import os
import re
import urllib3
import requests
from bs4 import BeautifulSoup
import arabic_reshaper
from bidi.algorithm import get_display

from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OUTAGE_URL = "https://ledc.ir/%D8%AE%D8%A7%D9%85%D9%88%D8%B4%DB%8C%D9%87%D8%A7%DB%8C-%D8%A8%D8%B1%D9%86%D8%A7%D9%85%D9%87-%D8%B1%DB%8C%D8%B2%DB%8C-%D8%B4%D8%AF%D9%87"

def fix_text(text: str) -> str:
    """اصلاح متون فارسی و معکوس‌سازی مناسب جهت نمایش در ReportLab"""
    if not text:
        return ""
    try:
        reshaped = arabic_reshaper.reshape(str(text).strip())
        return get_display(reshaped)
    except Exception:
        return str(text)

def download_font():
    """دانلود فونت فارسی وزیرمتن برای ساخت PDF"""
    font_path = "Vazirmatn-Regular.ttf"
    if not os.path.exists(font_path):
        print("در حال دانلود فونت فارسی Vazirmatn...")
        url = "https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/Vazirmatn-Regular.ttf"
        res = requests.get(url, timeout=30)
        with open(font_path, "wb") as f:
            f.write(res.content)
    pdfmetrics.registerFont(TTFont("Vazirmatn", font_path))

def fetch_doroud_outages():
    """استخراج جدول خاموشی‌های اختصاصی شهرستان دورود"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    
    table_rows = []
    detected_date = ""
    
    try:
        print(f"در حال دریافت اطلاعات از {OUTAGE_URL}...")
        response = requests.get(OUTAGE_URL, headers=headers, timeout=35, verify=False)
        response.encoding = "utf-8"
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # یافتن تمام جدول‌های صفحه
        tables = soup.find_all("table")
        for table in tables:
            for tr in table.find_all("tr"):
                cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
                if not cells:
                    continue
                
                row_str = " ".join(cells)
                
                # پیدا کردن ردیف‌های مربوط به دورود
                if "دورود" in row_str:
                    # ساختار ردیف‌های جدول در سایت:
                    # [مناطق, نام فیدر, شهرستان, ساعت قطع, تاریخ] یا برعکس
                    table_rows.append(cells)
                    if not detected_date:
                        match = re.search(r'\d{4}/\d{2}/\d{2}', row_str)
                        if match:
                            detected_date = match.group(0)

    except Exception as e:
        print(f"خطا در اسکرپ داده‌ها: {e}")

    return table_rows, detected_date

def generate_pdf(data_rows, outage_date, output_path="Doroud_Outage_Report.pdf"):
    """تولید فایل PDF در سایز A4 افقی با طراحی استاندارد"""
    download_font()
    
    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(A4),
        rightMargin=25,
        leftMargin=25,
        topMargin=25,
        bottomMargin=25
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'MainTitle',
        parent=styles['Normal'],
        fontName='Vazirmatn',
        fontSize=15,
        leading=20,
        alignment=1,
        textColor=colors.HexColor("#1A365D")
    )
    
    sub_style = ParagraphStyle(
        'SubTitle',
        parent=styles['Normal'],
        fontName='Vazirmatn',
        fontSize=10,
        leading=14,
        alignment=1,
        textColor=colors.HexColor("#4A5568")
    )
    
    header_cell_style = ParagraphStyle(
        'HeaderCell',
        parent=styles['Normal'],
        fontName='Vazirmatn',
        fontSize=9,
        leading=13,
        alignment=1,
        textColor=colors.white
    )
    
    body_cell_style = ParagraphStyle(
        'BodyCell',
        parent=styles['Normal'],
        fontName='Vazirmatn',
        fontSize=8,
        leading=12,
        alignment=2,
        textColor=colors.HexColor("#2D3748"),
        wordWrap='RTL'
    )
    
    center_cell_style = ParagraphStyle(
        'CenterCell',
        parent=body_cell_style,
        alignment=1
    )

    story = []
    story.append(Paragraph(fix_text("برنامه مدیریت اضطراری بار و خاموشی‌های برق شهرستان دورود"), title_style))
    story.append(Spacer(1, 4))
    
    date_display = outage_date if outage_date else "روز جاری"
    story.append(Paragraph(fix_text(f"تاریخ اعمال: {date_display}"), sub_style))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3182CE"), spaceAfter=10))

    if not data_rows:
        story.append(Paragraph(fix_text("در حال حاضر خاموشی برنامه‌ریزی‌شده‌ای برای دورود در سامانه ثبت نشده است."), sub_style))
    else:
        # عناوین ستون‌ها (جهت نمایش فارسی راست‌به‌چپ در PDF)
        # ستون‌ها: مناطق و آدرس‌ها | نام فیدر | شهرستان | ساعت قطع | تاریخ
        header_row = [
            Paragraph(fix_text("مناطق و آدرس‌های مسیر تغذیه فیدر"), header_cell_style),
            Paragraph(fix_text("نام فیدر"), header_cell_style),
            Paragraph(fix_text("شهرستان"), header_cell_style),
            Paragraph(fix_text("ساعت قطع"), header_cell_style),
            Paragraph(fix_text("تاریخ"), header_cell_style),
        ]
        
        table_content = [header_row]
        
        for row in data_rows:
            # همگام‌سازی تعداد ستون‌ها
            if len(row) >= 5:
                c_desc = Paragraph(fix_text(row[0]), body_cell_style)
                c_feeder = Paragraph(fix_text(row[1]), center_cell_style)
                c_city = Paragraph(fix_text(row[2]), center_cell_style)
                c_time = Paragraph(fix_text(row[3]), center_cell_style)
                c_date = Paragraph(fix_text(row[4]), center_cell_style)
                table_content.append([c_desc, c_feeder, c_city, c_time, c_date])
            elif len(row) == 4:
                c_desc = Paragraph(fix_text(row[0]), body_cell_style)
                c_feeder = Paragraph(fix_text(row[1]), center_cell_style)
                c_city = Paragraph(fix_text("دورود"), center_cell_style)
                c_time = Paragraph(fix_text(row[2]), center_cell_style)
                c_date = Paragraph(fix_text(row[3]), center_cell_style)
                table_content.append([c_desc, c_feeder, c_city, c_time, c_date])
        
        # عرض ستون‌ها متناسب با صفحه A4 افقی (کل عرض حدود 790 پوینت)
        col_widths = [430, 95, 75, 100, 90]
        
        styled_table = Table(table_content, colWidths=col_widths, repeatRows=1)
        styled_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1A365D")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(styled_table)
        
    doc.build(story)
    print(f"فایل با موفقیت ساخته شد: {output_path}")
    return output_path

def send_telegram(file_path):
    """ارسال مستقیم فایل به تلگرام"""
    bot_token = os.environ.get("TG_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("توکن تلگرام یا شناسه چت یافت نشد.")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    caption = "⚡️ جدول زمان‌بندی خاموشی‌های برق شهرستان دورود"
    
    with open(file_path, "rb") as f:
        files = {"document": f}
        data = {"chat_id": chat_id, "caption": caption}
        try:
            res = requests.post(url, data=data, files=files, timeout=50)
            if res.status_code == 200:
                print("فایل با موفقیت به تلگرام فرستاده شد.")
            else:
                print(f"خطای تلگرام: {res.text}")
        except Exception as e:
            print(f"خطا در ارسال به تلگرام: {e}")

if __name__ == "__main__":
    outage_data, current_date = fetch_doroud_outages()
    pdf_file = generate_pdf(outage_data, current_date)
    send_telegram(pdf_file)

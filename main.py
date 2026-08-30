import os
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

OUTAGE_URL = "https://ledc.ir/%d8%ae%d8%a7%d9%85%d9%88%d8%b4%db%8c%d9%87%d8%a7%db%8c-%d8%a8%d8%b1%d9%86%d8%a7%d9%85%d9%87-%d8%b1%db%8c%d8%8%b1%db%8c%d8%b2%db%8c%87"
KEYWORDS = ["دورود"]

def fix_text(text: str) -> str:
    """اصلاح متن فارسی برای ReportLab"""
    if not text:
        return ""
    try:
        return get_display(arabic_reshaper.reshape(str(text)))
    except Exception:
        return str(text)

def download_font():
    font_path = "Vazirmatn-Regular.ttf"
    if not os.path.exists(font_path):
        print("در حال دانلود فونت فارسی Vazirmatn...")
        url = "https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/Vazirmatn-Regular.ttf"
        with open(font_path, "wb") as f:
            f.write(requests.get(url, timeout=30).content)
    pdfmetrics.registerFont(TTFont("Vazirmatn", font_path))

def fetch_outages():
    """خواندن جدول خاموشی‌های برنامه‌ریزی‌شده از سایت برق لرستان"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/115.0"}
    rows_out = []
    update_date = ""
    try:
        res = requests.get(OUTAGE_URL, headers=headers, timeout=30, verify=False)
        res.encoding = "utf-8"
        soup = BeautifulSoup(res.text, "html.parser")

        # تاریخ بروزرسانی (اولین متنی که الگوی تاریخ دارد)
        import re
        for txt in soup.stripped_strings:
            m = re.search(r'\d{2}/\d{1,2}/\d{1,2}', txt)
            if m:
                update_date = m.group(0)
                break

        # پیدا کردن جدول(های) خاموشی
        tables = soup.find_all("table")
        for table in tables:
            for tr in table.find_all("tr"):
                cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
                if not cells:
                    continue
                row_text = " ".join(cells)
                # فقط ردیف‌های مرتبط با دورود (یا هدر جدول)
                if any(k in row_text for k in KEYWORDS) or "ساعت" in row_text or "فیدر" in row_text:
                    rows_out.append(cells)
    except Exception as e:
        print(f"خطا در دریافت سایت: {e}")

    if not rows_out:
        rows_out = [["ساعت قطع", "نام فیدر", "مناطق"], ["-", "-", "در حال حاضر جدول خاموشی برای دورود یافت نشد."]]
    return rows_out, update_date

def generate_pdf(rows, update_date, output="Doroud_Outage_Report.pdf"):
    download_font()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4),
                            rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()

    title_s = ParagraphStyle('T', parent=styles['Normal'], fontName='Vazirmatn', fontSize=16,
                             leading=22, alignment=1, textColor=colors.HexColor("#1a365d"))
    cell_s = ParagraphStyle('C', parent=styles['Normal'], fontName='Vazirmatn', fontSize=9,
                            leading=14, alignment=2, wordWrap='RTL', textColor=colors.HexColor("#2d3748"))
    head_s = ParagraphStyle('H', parent=cell_s, fontSize=10, alignment=1,
                            textColor=colors.white)
    meta_s = ParagraphStyle('M', parent=styles['Normal'], fontName='Vazirmatn', fontSize=8,
                            leading=12, alignment=1, textColor=colors.HexColor("#718096"))

    story = []
    story.append(Paragraph(fix_text("برنامه خاموشی‌های برق شهرستان دورود"), title_s))
    if update_date:
        story.append(Spacer(1, 4))
        story.append(Paragraph(fix_text(f"آخرین بروزرسانی: {update_date}"), meta_s))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3182ce"), spaceAfter=10))

    # ساخت جدول با پاراگراف‌های داخل سلول (شکستن خودکار در صفحات بعدی)
    table_data = []
    n_cols = max(len(r) for r in rows)
    for i, r in enumerate(rows):
        r = r + [""] * (n_cols - len(r))
        style = head_s if i == 0 else cell_s
        table_data.append([Paragraph(fix_text(c), style) for c in r])

    col_widths = [doc.width * w for w in (0.15, 0.15, 0.70)][:n_cols]
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1a365d")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#a0aec0")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#edf2f7")]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t)

    story.append(Spacer(1, 12))
    story.append(Paragraph(fix_text("تهیه شده توسط سیستم هوشمند مانیتورینگ دورود"), meta_s))
    doc.build(t and story)
    print(f"فایل تولید شد: {output}")
    return output

def send_telegram(file_path):
    token = os.environ.get("TG_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")
    if not token or not chat_id:
        print("سکرت‌های تلگرام تنظیم نشده‌اند.")
        return
    try:
        with open(file_path, "rb") as f:
            res = requests.post(
                f"https://api.telegram.org/bot{token}/sendDocument",
                data={"chat_id": chat_id, "caption": "📄 برنامه خاموشی‌های برق شهرستان دورود"},
                files={"document": f}, timeout=60)
        print("ارسال موفق" if res.status_code == 200 else f"خطای تلگرام: {res.text}")
    except Exception as e:
        print(f"خطا در ارسال: {e}")

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()
    rows, upd = fetch_outages()
    pdf = generate_pdf(rows, upd)
    send_telegram(pdf)

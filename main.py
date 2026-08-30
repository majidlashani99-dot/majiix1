# -*- coding: utf-8 -*-
import os
import requests
from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import arabic_reshaper
from bidi.algorithm import get_display

TELEGRAM_TOKEN = os.environ.get('TG_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TG_CHAT_ID')
URL = "http://ledc.ir/"

def scrape_outages(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=25)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        table = soup.find('table')
        if not table:
            print("جدول خاموشی‌ها در صفحه اصلی پیدا نشد.")
            return []

        outages = []
        rows = table.find_all('tr')
        for row in rows[1:]:
            cols = row.find_all('td')
            if len(cols) >= 4:
                region = cols[0].text.strip()
                address = cols[1].text.strip()
                start_time = cols[2].text.strip()
                end_time = cols[3].text.strip()
                outages.append({
                    'region': region,
                    'address': address,
                    'start_time': start_time,
                    'end_time': end_time
                })
        return outages
    except Exception as e:
        print(f"خطا در دریافت اطلاعات سایت: {e}")
        return []

def create_pdf_report(outages, filename="outage_report.pdf"):
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    styles = getSampleStyleSheet()
    style_normal = styles['Normal']

    # رسم عنوان
    title_raw = "گزارش خاموشی‌های برق شهرستان دورود"
    title_text = get_display(arabic_reshaper.reshape(title_raw))
    p_title = Paragraph(f"<font size=16><b>{title_text}</b></font>", styles['Heading1'])
    p_title.wrapOn(c, width - 2*inch, inch)
    p_title.drawOn(c, inch, height - 1.2*inch)

    y_position = height - 2.0*inch

    if not outages:
        no_data_raw = "امروز برنامه خاموشی جدیدی در سایت ثبت نشده است یا در دسترس نیست."
        no_data_text = get_display(arabic_reshaper.reshape(no_data_raw))
        p_no_data = Paragraph(no_data_text, style_normal)
        p_no_data.wrapOn(c, width - 2*inch, height)
        p_no_data.drawOn(c, inch, y_position)
    else:
        for outage in outages:
            region_text = get_display(arabic_reshaper.reshape(f"منطقه: {outage['region']}"))
            address_text = get_display(arabic_reshaper.reshape(f"آدرس: {outage['address']}"))
            time_text = get_display(arabic_reshaper.reshape(f"زمان: از {outage['start_time']} تا {outage['end_time']}"))

            p_region = Paragraph(f"<b>{region_text}</b>", style_normal)
            p_address = Paragraph(address_text, style_normal)
            p_time = Paragraph(time_text, style_normal)

            p_region.wrapOn(c, width - 2*inch, inch)
            p_region.drawOn(c, inch, y_position)
            y_position -= (p_region.height + 0.15*inch)

            p_address.wrapOn(c, width - 2*inch, inch)
            p_address.drawOn(c, inch, y_position)
            y_position -= (p_address.height + 0.15*inch)

            p_time.wrapOn(c, width - 2*inch, inch)
            p_time.drawOn(c, inch, y_position)
            y_position -= (p_time.height + 0.35*inch)

            if y_position < inch:
                c.showPage()
                y_position = height - inch

    try:
        c.save()
        print(f"فایل PDF با موفقیت ایجاد شد: {filename}")
        return filename
    except Exception as e:
        print(f"خطا در ایجاد فایل PDF: {e}")
        return None

def send_pdf_to_telegram(pdf_path):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("خطا: مقادیر TG_TOKEN یا TG_CHAT_ID در سکرت‌ها تنظیم نشده‌اند.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    caption = "⚡️ گزارش روزانه برنامه خاموشی برق دورود"

    try:
        with open(pdf_path, 'rb') as f:
            files = {'document': f}
            data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption}
            response = requests.post(url, data=data, files=files, timeout=30)
            
        res_json = response.json()
        if res_json.get("ok"):
            print("فایل PDF با موفقیت به تلگرام ارسال شد!")
        else:
            print(f"پاسخ تلگرام با خطا مواجه شد: {res_json}")
    except Exception as e:
        print(f"خطا در ارتباط مستقیم با API تلگرام: {e}")

if __name__ == "__main__":
    print("--- شروع فرآیند دریافت و ارسال گزارش ---")
    outages = scrape_outages(URL)
    pdf = create_pdf_report(outages)
    if pdf and os.path.exists(pdf):
        send_pdf_to_telegram(pdf)
    print("--- پایان عملیات ---")

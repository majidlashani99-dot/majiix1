main.py# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import arabic_reshaper
from bidi.algorithm import get_display
import os
import telegram

TELEGRAM_TOKEN = os.environ.get('TG_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TG_CHAT_ID')
URL = "http://ledc.ir/"

def scrape_outages(url):
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        table = soup.find('table')
        if not table:
            print("جدول خاموشی‌ها پیدا نشد.")
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
    except requests.exceptions.RequestException as e:
        print(f"خطا در درخواست به سایت: {e}")
        return []
    except Exception as e:
        print(f"خطای ناشناخته در پردازش: {e}")
        return []

def create_pdf_report(outages, filename="outage_report.pdf"):
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    styles = getSampleStyleSheet()
    style_arabic = styles['Normal']

    title_text = "گزارش خاموشی‌های برق شهرستان دورود"
    reshaped_title = arabic_reshaper.reshape(title_text)
    bidi_title = get_display(reshaped_title)
    p_title = Paragraph(bidi_title, styles['h1'])
    p_title.wrapOn(c, width - 2*inch, inch)
    p_title.drawOn(c, inch, height - inch - p_title.height)

    y_position = height - 2*inch

    if not outages:
        no_data_text = "امروز خاموشی ثبت نشده یا جدول در دسترس نیست."
        reshaped_no_data = arabic_reshaper.reshape(no_data_text)
        bidi_no_data = get_display(reshaped_no_data)
        p_no_data = Paragraph(bidi_no_data, style_arabic)
        p_no_data.wrapOn(c, width - 2*inch, height)
        p_no_data.drawOn(c, inch, y_position)
    else:
        for outage in outages:
            region_text = f"منطقه: {outage['region']}"
            address_text = f"آدرس: {outage['address']}"
            time_text = f"زمان: از {outage['start_time']} تا {outage['end_time']}"

            reshaped_region = arabic_reshaper.reshape(region_text)
            bidi_region = get_display(reshaped_region)
            p_region = Paragraph(bidi_region, style_arabic)

            reshaped_address = arabic_reshaper.reshape(address_text)
            bidi_address = get_display(reshaped_address)
            p_address = Paragraph(bidi_address, style_arabic)

            reshaped_time = arabic_reshaper.reshape(time_text)
            bidi_time = get_display(reshaped_time)
            p_time = Paragraph(bidi_time, style_arabic)

            p_region.wrapOn(c, width - 2*inch, inch)
            p_region.drawOn(c, inch, y_position)
            y_position -= p_region.height + 0.2*inch

            p_address.wrapOn(c, width - 2*inch, inch)
            p_address.drawOn(c, inch, y_position)
            y_position -= p_address.height + 0.2*inch

            p_time.wrapOn(c, width - 2*inch, inch)
            p_time.drawOn(c, inch, y_position)
            y_position -= p_time.height + 0.5*inch

            if y_position < inch:
                c.showPage()
                y_position = height - inch

    try:
        c.save()
        print(f"فایل PDF ساخته شد: {filename}")
        return filename
    except Exception as e:
        print(f"خطا در ساخت PDF: {e}")
        return None

def send_pdf_to_telegram(pdf_path):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("توکن تلگرام یا چت آیدی تنظیم نشده است.")
        return

    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        with open(pdf_path, 'rb') as f:
            bot.send_document(chat_id=TELEGRAM_CHAT_ID, document=f, caption="⚡ گزارش روزانه خاموشی برق دورود")
        print("فایل به تلگرام ارسال شد.")
    except Exception as e:
        print(f"خطا در ارسال به تلگرام: {e}")

if __name__ == "__main__":
    print("شروع پردازش...")
    outages_data = scrape_outages(URL)
    pdf_filename = create_pdf_report(outages_data)
    if pdf_filename:
        send_pdf_to_telegram(pdf_filename)
    print("پایان.")

import os
import sys
import asyncio
import requests
from playwright.async_api import async_playwright

BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
CHAT_ID = os.environ.get("TG_CHAT_ID")
OUTPUT_IMAGE = "calendar_today.png"

async def capture_calendar_box():
    print("🌐 Launching headless browser...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # تنظیم ابعاد دسکتاپ و Scale Factor برای خروجی باکیفیت
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            device_scale_factor=2,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        print("⏳ Loading Time.ir...")
        await page.goto("https://www.time.ir/", wait_until="networkidle", timeout=60000)

        # پیدا کردن کادر اصلی تاریخ و تقویم
        # این سلکتورها باکس سفید بالای تایم دات آی‌آر را هدف می‌گیرند
        selectors = [
            ".today-container",
            ".dayDateWrapper",
            ".wrapper.today-wrapper",
            "#ctl00_cphTop_pnlToday",
            ".panel-today"
        ]
        
        target_element = None
        for sel in selectors:
            el = await page.query_selector(sel)
            if el:
                target_element = el
                print(f"🎯 Target element found with selector: {sel}")
                break
        
        if not target_element:
            # اگر سلکتور خاصی مچ نشد، بخش هدر تاریخ را برمی‌دارد
            print("⚠️ Specific selector not found, attempting generic container...")
            target_element = await page.query_selector("div.dates") or await page.query_selector("section.today")

        if target_element:
            await target_element.screenshot(path=OUTPUT_IMAGE)
            print(f"✅ Screenshot saved successfully as {OUTPUT_IMAGE}")
        else:
            print("📸 Taking top viewport screenshot as fallback...")
            await page.screenshot(path=OUTPUT_IMAGE, clip={"x": 150, "y": 80, "width": 980, "height": 320})
            
        await browser.close()

def send_to_telegram():
    if not os.path.exists(OUTPUT_IMAGE):
        print("❌ Image file does not exist!")
        sys.exit(1)

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    caption = "🗓 **تقویم و اوقات امروز**\n\n🆔 @majiix1"

    print("🚀 Sending snapshot to Telegram...")
    with open(OUTPUT_IMAGE, "rb") as img:
        files = {"photo": img}
        data = {
            "chat_id": CHAT_ID,
            "caption": caption,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, files=files, data=data, timeout=30)
        
    res_json = response.json()
    if response.status_code == 200 and res_json.get("ok"):
        print("🎉 Telegram message delivered successfully!")
    else:
        print(f"❌ Telegram API Error: {res_json}")
        sys.exit(1)

if __name__ == "__main__":
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Error: TG_BOT_TOKEN or TG_CHAT_ID is missing in environment variables.")
        sys.exit(1)
        
    asyncio.run(capture_calendar_box())
    send_to_telegram()

import os
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

API_KEY = os.getenv("FOOTBALL_API_KEY", "85fae27dba354c5fb14c947161c86847")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TEMPLATE_PATH = "template.png"
OUTPUT_PATH = "today_matches.png"

# مختصات مرکز سطرهای مسابقات روی پوستر (Y-Centers)
ROW_Y = [455, 562, 666, 771, 876, 981, 1086, 1191, 1296]

def get_matches():
    url = "https://api.football-data.org/v4/matches"
    headers = {"X-Auth-Token": API_KEY}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200:
            print(f"API Error: Status {res.status_code}")
            return []
        data = res.json()
        matches = []
        for m in data.get("matches", []):
            home = m["homeTeam"].get("shortName") or m["homeTeam"].get("name", "")
            away = m["awayTeam"].get("shortName") or m["awayTeam"].get("name", "")
            
            # تبدیل ساعت مسابقه به وقت تهران (UTC + 3:30)
            utc_dt = datetime.strptime(m["utcDate"], "%Y-%m-%dT%H:%M:%SZ")
            total_minutes = utc_dt.hour * 60 + utc_dt.minute + 210
            tehran_h = (total_minutes // 60) % 24
            tehran_m = total_minutes % 60
            match_time = f"{tehran_h:02d}:{tehran_m:02d}"
            
            matches.append({"home": home[:12], "away": away[:12], "time": match_time})
            if len(matches) >= 9:
                break
        return matches
    except Exception as e:
        print(f"Fetch Error: {e}")
        return []

def draw_poster(matches):
    if not os.path.exists(TEMPLATE_PATH):
        print("Template image not found!")
        return False
    
    img = Image.open(TEMPLATE_PATH).convert("RGBA")
    draw = ImageDraw.Draw(img)
    
    try:
        font_team = ImageFont.truetype("arial.ttf", 26)
        font_time = ImageFont.truetype("arialbd.ttf", 28)
    except:
        font_team = ImageFont.load_default()
        font_time = font_team

    for i, m in enumerate(matches):
        y = ROW_Y[i]
        # تیم میزبان (چپ)
        draw.text((290, y), m["home"], fill=(255, 255, 255), font=font_team, anchor="mm")
        # ساعت بازی (وسط - طلایی)
        draw.text((511, y), m["time"], fill=(245, 205, 120), font=font_time, anchor="mm")
        # تیم میهمان (راست)
        draw.text((720, y), m["away"], fill=(255, 255, 255), font=font_team, anchor="mm")
        
    img.convert("RGB").save(OUTPUT_PATH, quality=95)
    print("Poster created successfully!")
    return True

def send_telegram():
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram credentials missing!")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    with open(OUTPUT_PATH, "rb") as photo:
        files = {"photo": photo}
        data = {"chat_id": CHAT_ID, "caption": "⚽ پوستر اختصاصی بازی‌های امروز"}
        res = requests.post(url, data=data, files=files)
        print(f"Telegram response: {res.status_code}")

if __name__ == "__main__":
    matches = get_matches()
    if matches:
        if draw_poster(matches):
            send_telegram()
    else:
        print("No matches found for today or API limit reached.")
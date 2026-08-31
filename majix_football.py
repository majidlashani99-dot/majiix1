import os
import re
import json
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper

# تنظیمات و شناسه‌های لیگ‌های ۵ گانه اروپا در ورزش۳
TARGET_LEAGUES = {
    "league-page-1": "لیگ برتر انگلیس",
    "league-page-5": "لالیگا اسپانیا",
    "league-page-7": "بوندسلیگا آلمان",
    "league-page-8": "سری آ ایتالیا",
    "league-page-10": "لیگ ۱ فرانسه",
}

STATE_FILE = "state/football_message_id.json"
OUTPUT_IMAGE = "output/football_report.png"

def reshape_fa(text: str) -> str:
    """اصلاح حروف فارسی متصل برای رندر تصویری"""
    if not text:
        return ""
    return arabic_reshaper.reshape(str(text))

def fetch_and_parse_matches():
    url = "https://www.varzesh3.com/livescore"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=25)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, "lxml")
    except Exception as e:
        print(f"Error fetching data: {e}")
        return []
    
    data = []
    
    for league_id, league_name in TARGET_LEAGUES.items():
        league_box = soup.find(id=league_id)
        if not league_box:
            continue
            
        matches = []
        text_lines = league_box.get_text(separator="\n").split("\n")
        text_lines = [line.strip() for line in text_lines if line.strip()]
        
        current_time = ""
        current_status = ""
        for line in text_lines:
            if re.match(r'^\d{2}:\d{2}$', line):
                current_time = line
            elif any(k in line for k in ["نتیجه نهایی", "پایان", "نیمه", "'", "+", "لغو"]):
                current_status = line
            elif " - " in line and len(line) > 5 and not re.match(r'^\d+\s*-\s*\d+$', line):
                teams = line.split(" - ")
                if len(teams) == 2:
                    matches.append({
                        "time": current_time or "22:00",
                        "home": teams[0].strip(),
                        "away": teams[1].strip(),
                        "status": current_status or "برگزار نشده"
                    })
                    current_status = ""
            elif re.match(r'^(.+?)\s+(\d+\s*-\s*\d+)\s+(.+?)$', line):
                m = re.match(r'^(.+?)\s+(\d+\s*-\s*\d+)\s+(.+?)$', line)
                matches.append({
                    "time": current_time or "امروز",
                    "home": m.group(1).strip(),
                    "away": m.group(3).strip(),
                    "score": m.group(2).strip(),
                    "status": current_status or "نتیجه"
                })
                current_status = ""

        if matches:
            data.append({
                "league": league_name,
                "matches": matches
            })
            
    return data

def render_image(leagues_data):
    os.makedirs("output", exist_ok=True)
    width = 1080
    
    # محاسبه ارتفاع پویا بر اساس تعداد مسابقات
    total_matches = sum(len(lg["matches"]) for lg in leagues_data)
    height = 280 + (len(leagues_data) * 70) + (total_matches * 60) + 120
    height = max(height, 800)
    
    img = Image.new("RGB", (width, height), color="#0D0D0D")
    draw = ImageDraw.Draw(img)
    
    # انتخاب فونت سیستم
    font_path = "/usr/share/fonts/truetype/vazirmatn/Vazirmatn-Bold.ttf"
    if not os.path.exists(font_path):
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        
    try:
        title_font = ImageFont.truetype(font_path, 38)
        league_font = ImageFont.truetype(font_path, 28)
        text_font = ImageFont.truetype(font_path, 24)
        sub_font = ImageFont.truetype(font_path, 20)
    except:
        title_font = league_font = text_font = sub_font = ImageFont.load_default()

    # هدر برند MAJIX با تم طلایی
    draw.rectangle([(0, 0), (width, 160)], fill="#141414")
    draw.line([(0, 160), (width, 160)], fill="#D4AF37", width=3)
    
    header_title = reshape_fa("⚽ جدول و ساعت بازی‌های امشب | MAJIX")
    draw.text((width // 2, 70), header_title, fill="#D4AF37", font=title_font, anchor="mm")
    
    header_sub = reshape_fa("۵ لیگ معتبر اروپا (انگلیس، اسپانیا، آلمان، ایتالیا، فرانسه)")
    draw.text((width // 2, 120), header_sub, fill="#888888", font=sub_font, anchor="mm")
    
    y = 190
    for lg in leagues_data:
        # کادر عنوان لیگ
        draw.rectangle([(40, y), (width - 40, y + 45)], fill="#1E1E1E", outline="#D4AF37", width=1)
        league_title = reshape_fa(f"🏆 {lg['league']}")
        draw.text((width - 60, y + 22), league_title, fill="#D4AF37", font=league_font, anchor="rm")
        y += 60
        
        # ردیف‌های بازی
        for m in lg["matches"]:
            draw.rectangle([(50, y), (width - 50, y + 50)], fill="#141414")
            
            # زمان
            t_text = m.get("time", "")
            draw.text((80, y + 25), t_text, fill="#E6C657", font=text_font, anchor="lm")
            
            # نام تیم‌ها یا نتیجه
            teams_str = f"{m.get('home', '')}  VS  {m.get('away', '')}"
            if "score" in m:
                teams_str = f"{m.get('home', '')}  {m.get('score')}  {m.get('away', '')}"
            
            draw.text((width // 2 + 50, y + 25), reshape_fa(teams_str), fill="#FFFFFF", font=text_font, anchor="mm")
            
            # وضعیت بازی
            status_str = reshape_fa(m.get("status", ""))
            draw.text((width - 80, y + 25), status_str, fill="#999999", font=sub_font, anchor="rm")
            
            y += 58
        y += 20
        
    # فوتر
    footer_text = reshape_fa("MAJIX • بروزرسانی خودکار هر شب ساعت ۲۲:۰۰")
    draw.text((width // 2, height - 40), footer_text, fill="#666666", font=sub_font, anchor="mm")
    
    img.save(OUTPUT_IMAGE, "PNG")
    print(f"Report image generated at {OUTPUT_IMAGE}")

def send_or_edit_telegram():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("Telegram tokens missing! Check secrets.")
        return

    os.makedirs("state", exist_ok=True)
    msg_id = None
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                msg_id = json.load(f).get("message_id")
        except:
            msg_id = None

    caption = "⚽ **برنامه و نتایج بازی‌های امشب (۵ لیگ معتبر اروپا)**\n🟡 برند MAJIX • آپدیت هر شب ساعت ۲۲:۰۰"
    
    # ادیت پیام قبلی برای جلوگیری از اسپم کانال
    if msg_id:
        url = f"https://api.telegram.org/bot{token}/editMessageMedia"
        try:
            with open(OUTPUT_IMAGE, "rb") as photo:
                media_payload = {
                    "type": "photo",
                    "media": "attach://photo",
                    "caption": caption,
                    "parse_mode": "Markdown"
                }
                files = {"photo": photo}
                data = {
                    "chat_id": chat_id,
                    "message_id": msg_id,
                    "media": json.dumps(media_payload)
                }
                res = requests.post(url, data=data, files=files, timeout=30)
                if res.status_code == 200:
                    print("Successfully updated existing message.")
                    return
                else:
                    print(f"Edit failed: {res.text}. Sending a fresh message instead.")
        except Exception as e:
            print(f"Error editing: {e}")

    # ارسال به صورت پیام تازه
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    with open(OUTPUT_IMAGE, "rb") as photo:
        files = {"photo": photo}
        data = {
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": "Markdown"
        }
        res = requests.post(url, data=data, files=files, timeout=30)
        res_json = res.json()
        if res_json.get("ok"):
            new_msg_id = res_json["result"]["message_id"]
            with open(STATE_FILE, "w") as f:
                json.dump({"message_id": new_msg_id}, f)
            print(f"Fresh message sent! ID: {new_msg_id}")
        else:
            print(f"Telegram API Error: {res.text}")

if __name__ == "__main__":
    leagues_data = fetch_and_parse_matches()
    if not leagues_data:
        leagues_data = [{
            "league": "۵ لیگ معتبر اروپا",
            "matches": [{"time": "22:00", "home": "امشب مسابقه‌ای در جدول ثبت نشده", "away": "-", "status": "بدون بازی"}]
        }]
    render_image(leagues_data)
    send_or_edit_telegram()

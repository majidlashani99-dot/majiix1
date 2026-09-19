import os, re, sys, logging
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
URL = "https://www.varzesh3.com/livescore"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "fa,en;q=0.9"
}

# فقط لیگ‌های مشخص شده توسط مجید
TARGET_LEAGUES = {
    "انگلیس": {"icon": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "name": "لیگ برتر / حذفی انگلیس"},
    "اسپانیا": {"icon": "🇪🇸", "name": "لالیگا / کوپا دل ری"},
    "قهرمانان": {"icon": "🌟", "name": "لیگ قهرمانان اروپا"},
    "کنفرانس": {"icon": "🇪🇺", "name": "لیگ کنفرانس اروپا"},
    "اروپا": {"icon": "🇪🇺", "name": "لیگ اروپا"},
    "ایران": {"icon": "🇮🇷", "name": "لیگ برتر / جام حذفی ایران"},
    "آسیا": {"icon": "🌏", "name": "لیگ قهرمانان و نخبگان آسیا"}
}

def match_target_league(title):
    for key, data in TARGET_LEAGUES.items():
        if key in title:
            # فیلتر برای اینکه ورزش‌های غیرفوتبالی حذف شوند
            if not any(sport in title for sport in ["بسکتبال", "والیبال", "فوتسال", "هندبال", "تنیس"]):
                return data["name"], data["icon"]
    return None, None

def fetch_matches():
    r = requests.get(URL, headers=HEADERS, timeout=25)
    r.raise_for_status()
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    
    schedule = {}
    lines = [l.strip() for l in soup.get_text(separator="\n").split("\n") if l.strip()]
    
    current_league = None
    league_icon = "⚽️"
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # تشخیص نام لیگ یا بخش مسابقات
        l_name, l_icon = match_target_league(line)
        if l_name:
            current_league = l_name
            league_icon = l_icon
            schedule.setdefault(f"{league_icon} {current_league}", [])
            i += 1
            continue
            
        # اگر نام لیگ دیگری آمد که در لیست ما نبود، لیگ فعلی ریست می‌شود
        if any(w in line for w in ["لیگ", "جام", "سری آ", "بوندسلیگا", "لوشامپیونا"]) and not l_name:
            current_league = None
            i += 1
            continue

        if current_league:
            # جستجوی ساعت مسابقه (مثلا 22:30)
            time_match = re.search(r"^(\d{1,2}:\d{2})$", line)
            if time_match and i + 1 < len(lines):
                match_time = time_match.group(1)
                next_line = lines[i+1]
                
                # بررسی اینکه آیا خط بعدی نتیجه نهایی است یا بازی است
                if "نتیجه نهایی" in next_line:
                    i += 2
                    continue
                    
                if "-" in next_line or " - " in next_line:
                    teams = next_line.split("-")
                    if len(teams) >= 2:
                        team_a = teams[0].strip()
                        team_b = teams[1].strip()
                        # پاکسازی اعداد گل در صورت درج
                        team_a = re.sub(r"\d+", "", team_a).strip()
                        team_b = re.sub(r"\d+", "", team_b).strip()
                        
                        entry = f"▫️ {team_a} 🆚 {team_b} | ⏰ {match_time}"
                        key = f"{league_icon} {current_league}"
                        if entry not in schedule[key]:
                            schedule[key].append(entry)
                        i += 2
                        continue
                        
                # حالت دیگر: تیم اول - تیم دوم در همان خط با ساعت
            elif " - " in line and any(c.isdigit() for c in line) and ":" in line:
                m_time = re.search(r"(\d{1,2}:\d{2})", line)
                if m_time:
                    t_str = m_time.group(1)
                    clean_line = line.replace(t_str, "").replace("نتیجه نهایی", "").strip()
                    teams = clean_line.split("-")
                    if len(teams) >= 2:
                        team_a = re.sub(r"\d+", "", teams[0]).strip()
                        team_b = re.sub(r"\d+", "", teams[1]).strip()
                        entry = f"▫️ {team_a} 🆚 {team_b} | ⏰ {t_str}"
                        key = f"{league_icon} {current_league}"
                        if entry not in schedule[key]:
                            schedule[key].append(entry)
        i += 1
        
    # حذف کلیدهای خالی
    return {k: v for k, v in schedule.items() if len(v) > 0}

def build_message(matches_dict):
    tehran_now = datetime.now(timezone(timedelta(hours=3, minutes=30)))
    weekdays = {0: "دوشنبه", 1: "سه‌شنبه", 2: "چهارشنبه", 3: "پنج‌شنبه", 4: "جمعه", 5: "شنبه", 6: "یکشنبه"}
    
    lines = [
        "⚽️ <b>برنامه و ساعت بازی‌های مهم فوتبال</b>",
        f"📅 <b>{weekdays.get(tehran_now.weekday(), '')} {tehran_now.strftime('%Y/%m/%d')}</b>",
        "━━━━━━━━━━━━━━━━━━"
    ]
    
    if not matches_dict:
        lines.append("\n⚠️ <i>امروز در لیگ‌های منتخب (ایران، اسپانیا، انگلیس، لیگ قهرمانان و آسیا) مسابقه‌ای برگزار نمی‌شود.</i>")
    else:
        for league_title, matches in matches_dict.items():
            lines.append(f"\n<b>{league_title}</b>")
            for m in matches:
                lines.append(m)
                
    lines.extend([
        "\n━━━━━━━━━━━━━━━━━━",
        "💠 <b>MAJIX Suite</b>",
        "🆔 @majiix1"
    ])
    return "\n".join(lines)

def send_telegram(text):
    if not TG_TOKEN or not TG_CHAT_ID:
        logging.error("Telegram credentials missing.")
        sys.exit(1)
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    res = requests.post(url, json=payload, timeout=20)
    if res.status_code != 200:
        logging.error(f"Telegram API Error: {res.text}")
        sys.exit(1)
    logging.info("Football Report broadcasted successfully!")

if __name__ == "__main__":
    data = fetch_matches()
    msg = build_message(data)
    send_telegram(msg)
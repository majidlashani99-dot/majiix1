import os
import sys
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")

REQUEST_TIMEOUT = 25
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

def get_today_matches():
    """دریافت لیست بازی‌ها و کنداکتور پخش زنده از وبسایت ورزش ۳ یا فوتبالی"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "fa,en-US;q=0.9,en;q=0.8",
    }
    
    matches_list = []
    
    # منبع مستقیم کنداکتور پخش زنده
    url = "https://www.varzesh3.com/livescore"
    
    try:
        res = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            
            # استخراج رویدادهای زنده و مهم روز
            stages = soup.select(".match-item")
            for item in stages:
                try:
                    time_elem = item.select_one(".match-time")
                    home_team = item.select_one(".home-team")
                    away_team = item.select_one(".away-team")
                    league_elem = item.find_previous(class_="league-title")
                    
                    time_str = time_elem.get_text(strip=True) if time_elem else ""
                    home_str = home_team.get_text(strip=True) if home_team else ""
                    away_str = away_team.get_text(strip=True) if away_team else ""
                    league_str = league_elem.get_text(strip=True) if league_elem else "سایر رقابت‌ها"
                    
                    if home_str and away_str and ":" in time_str:
                        matches_list.append({
                            "league": league_str,
                            "time": time_str,
                            "match": f"{home_str} 🆚 {away_str}"
                        })
                except Exception:
                    continue
    except Exception as e:
        print(f"⚠️ خطا در دریافت زنده از منبع اصلی: {e}")
        
    return matches_list

def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    res = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
    return res.json()

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ TG_TOKEN یا TG_CHAT_ID تنظیم نشده است!")
        sys.exit(1)
        
    today_fa = datetime.now(IRAN_TZ).strftime("%Y/%m/%d")
    matches = get_today_matches()
    
    caption = f"💠 <b>کنداکتور پخش زنده مسابقات امروز</b> 💠\n"
    caption += f"📅 تاریخ: <code>{today_fa}</code>\n"
    caption += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    if matches:
        current_league = ""
        for m in matches[:15]: # ۱۵ بازی مهم روز
            if m['league'] != current_league:
                current_league = m['league']
                caption += f"🏆 <b>{current_league}</b>\n"
            caption += f"⏰ ساعت <b>{m['time']}</b> | {m['match']}\n"
        caption += "\n━━━━━━━━━━━━━━━━━━━━\n"
        caption += "📡 <i>پخش از شبکه‌های ورزشی و پلتفرم‌های اینترنتی</i>\n"
        caption += "🆔 @Doroudcity"
    else:
        # در صورت نبود رویداد مستقیم یا تغییر ساختار
        caption += "⚽️ برای امروز مسابقه حساس با پخش زنده سراسری ثبت نشده است یا در حال به‌روزرسانی می‌باشد.\n"

    print("🚀 در حال ارسال به تلگرام...")
    result = send_telegram_message(caption)
    if result.get("ok"):
        print("✅ پیام کنداکتور با موفقیت ارسال شد!")
    else:
        print(f"❌ خطا در ارسال: {result}")

if __name__ == "__main__":
    main()

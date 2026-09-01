import os
import sys
import re
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

# دریافت متغیرهای محیطی تلگرام
BOT_TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")
REQUEST_TIMEOUT = 30
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))

# نگاشت آیکون‌ها و پرچم‌ها برای لیگ‌ها و تورنمنت‌های معتبر
LEAGUE_ICONS = {
    "ایران": "🇮🇷",
    "برتر ایران": "🇮🇷",
    "خلیج فارس": "🇮🇷",
    "انگلیس": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "اسپانیا": "🇪🇸",
    "ایتالیا": "🇮🇹",
    "آلمان": "🇩🇪",
    "فرانسه": "🇫🇷",
    "قهرمانان اروپا": "⭐️",
    "چمپیونزلیگ": "⭐️",
    "لیگ اروپا": "🏆",
    "عربستان": "🇸🇦",
    "پرتغال": "🇵🇹",
    "هلند": "🇳🇱",
    "ترکیه": "🇹🇷",
    "جهان": "🌍",
    "آسیا": "🌏"
}

def get_league_badge(league_name: str) -> str:
    """انتخاب آیکون و پرچم مناسب براساس نام لیگ"""
    for key, icon in LEAGUE_ICONS.items():
        if key in league_name:
            return f"{icon} <b>{league_name}</b>"
    return f"🏆 <b>{league_name}</b>"

def fetch_varzesh3_conductor():
    """استخراج مستقیم جدول پخش و بازی‌های روز از مرجع ورزش۳"""
    url = "https://www.varzesh3.com/livescore"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "fa,en-US;q=0.9,en;q=0.8",
    }
    
    matches_by_league = {}
    
    try:
        res = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if res.status_code != 200:
            print(f"⚠️ دریافت کد وضعیت غیر از ۲۰۰: {res.status_code}")
            return matches_by_league
            
        soup = BeautifulSoup(res.text, "html.parser")
        
        # دسته‌بندی مسابقات بر اساس لیگ
        league_containers = soup.select(".league-stage, .match-group, .live-score-league")
        
        # رویکرد چندگانه برای استخراج رویدادها
        if not league_containers:
            # حالت ساختار ردیفی
            items = soup.select(".match-item, .item-match, tr.match")
            for item in items:
                try:
                    time_elem = item.select_one(".match-time, .time, .col-time")
                    home_elem = item.select_one(".home-team, .team-home, .home, .team-right")
                    away_elem = item.select_one(".away-team, .team-away, .away, .team-left")
                    
                    time_str = time_elem.get_text(strip=True) if time_elem else ""
                    home_name = home_elem.get_text(strip=True) if home_elem else ""
                    away_name = away_elem.get_text(strip=True) if away_elem else ""
                    
                    league_parent = item.find_previous(["h3", "h4", "div"], class_=re.compile(r"league|title|header"))
                    league_title = league_parent.get_text(strip=True) if league_parent else "سایر مسابقات مهم"
                    
                    if home_name and away_name and ":" in time_str:
                        if league_title not in matches_by_league:
                            matches_by_league[league_title] = []
                        matches_by_league[league_title].append({
                            "time": time_str,
                            "home": home_name,
                            "away": away_name
                        })
                except Exception:
                    continue
        else:
            for container in league_containers:
                title_elem = container.select_one(".league-name, .league-title, .title")
                league_title = title_elem.get_text(strip=True) if title_elem else "سایر مسابقات"
                
                matches = []
                for row in container.select(".match-item, .match-row"):
                    time_elem = row.select_one(".match-time, .time")
                    home_elem = row.select_one(".home-team, .team-home")
                    away_elem = row.select_one(".away-team, .team-away")
                    
                    if time_elem and home_elem and away_elem:
                        t = time_elem.get_text(strip=True)
                        h = home_elem.get_text(strip=True)
                        a = away_elem.get_text(strip=True)
                        if ":" in t:
                            matches.append({"time": t, "home": h, "away": a})
                
                if matches:
                    matches_by_league[league_title] = matches

    except Exception as e:
        print(f"❌ خطا در پردازش اطلاعات مسابقات: {e}")
        
    return matches_by_league

def get_persian_date_header() -> str:
    """ایجاد فرمت تاریخ شمسی/میلادی به روز"""
    now = datetime.now(IRAN_TZ)
    # تقویم روز هفته
    weekdays_fa = {
        0: "دوشنبه",
        1: "سه‌شنبه",
        2: "چهارشنبه",
        3: "پنج‌شنبه",
        4: "جمعه",
        5: "شنبه",
        6: "یک‌شنبه"
    }
    day_fa = weekdays_fa.get(now.weekday(), "")
    date_str = now.strftime("%Y/%m/%d")
    time_str = now.strftime("%H:%M")
    return f"📅 <b>{day_fa}</b> | <code>{date_str}</code> | ⏰ ساعت <code>{time_str}</code>"

def format_telegram_message(data: dict) -> str:
    """طراحی تمیز، مدرن و خوانا برای ارسال به تلگرام"""
    header = "💠 <b>جدول و کنداکتور پخش زنده مسابقات امروز</b> 💠\n"
    date_header = get_persian_date_header() + "\n"
    separator = "━" * 25 + "\n\n"
    
    if not data:
        body = (
            "⚽️ <b>امروز رویداد ورزشی با پخش زنده سراسری ثبت نشده است.</b>\n\n"
            "📌 <i>لیست بازی‌ها به محض شروع پوشش زنده به‌روزرسانی می‌شود.</i>\n\n"
        )
    else:
        body = ""
        for league, matches in list(data.items())[:8]:  # نمایش ۸ لیگ اصلی روز
            body += f"{get_league_badge(league)}\n"
            for m in matches[:6]:  # حداکثر ۶ مسابقه در هر لیگ
                body += f"  ▫️ <code>{m['time']}</code>  <b>{m['home']}</b> 🆚 <b>{m['away']}</b>\n"
            body += "\n"

    footer = (
        "━" * 25 + "\n"
        "📺 <b>پخش مستقیم از شبکه‌های ورزشی و پلتفرم‌های پخش زنده</b>\n"
        "⚡️ <i>طراحی و گزارش خودکار توسط MAJIX</i>\n"
        "🆔 @Doroudcity"
    )
    
    return header + date_header + separator + body + footer

def send_telegram_html(message_text: str):
    """ارسال مستقیم به ربات تلگرام با پارس مود HTML"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    res = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
    return res.json()

def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ مقادیر TG_TOKEN یا TG_CHAT_ID در متغیرهای مخفی تنظیم نشده است!")
        sys.exit(1)

    print("🔍 در حال بررسی و دریافت جدول پخش زنده مسابقات روز...")
    matches_data = fetch_varzesh3_conductor()
    print(f"📊 تعداد لیگ‌های دریافت شده: {len(matches_data)}")
    
    formatted_msg = format_telegram_message(matches_data)
    
    print("🚀 در حال ارسال پیام کنداکتور به تلگرام...")
    result = send_telegram_html(formatted_msg)
    
    if result.get("ok"):
        print("✅ پیام جدول پخش مسابقات با موفقیت ارسال شد!")
    else:
        print(f"❌ خطا در ارسال پیام تلگرام: {result}")
        sys.exit(1)

if __name__ == "__main__":
    main()

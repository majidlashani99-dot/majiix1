# -*- coding: utf-8 -*-
import os
import re
import requests
from bs4 import BeautifulSoup

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TARGET_LEAGUES = [
    {"pattern": r"اسپانیا|لالیگا", "name": "🇪🇸 لالیگا اسپانیا", "order": 1},
    {"pattern": r"لیگ برتر انگلیس", "name": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 لیگ برتر انگلیس", "order": 2},
    {"pattern": r"جام اتحادیه انگلیس|جام حذفی انگلیس|fa cup", "name": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 جام اتحادیه / حذفی انگلیس", "order": 3},
    {"pattern": r"قهرمانان اروپا|ucl|champions league", "name": "🌟 لیگ قهرمانان اروپا", "order": 4},
    {"pattern": r"لیگ اروپا|europa league", "name": "🇪🇺 لیگ اروپا", "order": 5},
    {"pattern": r"کنفرانس", "name": "🇪🇺 لیگ کنفرانس اروپا", "order": 6},
    {"pattern": r"نخبگان آسیا|قهرمانان آسیا|acl", "name": "🌏 لیگ نخبگان / قهرمانان آسیا", "order": 7},
    {"pattern": r"ایران|خلیج فارس|جام حذفی ایران", "name": "🇮🇷 لیگ برتر / فوتبال ایران", "order": 8}
]

def fetch_varzesh3_raw_text():
    url = "https://www.varzesh3.com/livescore"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fa,en;q=0.9"
    }
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n")

def parse_matches(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    date_regex = re.compile(r'(1[34]\d{2}/\d{2}/\d{2})$')
    score_regex = re.compile(r'^(.+?)\s+(\d+)\s*-\s*(\d+)\s+(.+)$')
    match_regex = re.compile(r'^(.+?)\s+-\s+(.+)$')
    time_regex = re.compile(r'^(\d{2}:\d{2})(نتیجه نهایی)?$')

    events = []
    current_league = None
    pending_time = None

    for line in lines:
        t_match = time_regex.match(line)
        if t_match:
            pending_time = t_match.group(1)
            continue

        d_match = date_regex.search(line)
        if d_match:
            league_name = date_regex.sub('', line).strip()
            current_league = {
                "league": league_name,
                "date": d_match.group(1),
                "matches": []
            }
            events.append(current_league)
            pending_time = None
            continue

        if current_league is not None:
            s_match = score_regex.match(line)
            if s_match:
                current_league["matches"].append({
                    "time": pending_time or "پایان",
                    "status": "FT",
                    "home": s_match.group(1).strip(),
                    "home_score": s_match.group(2),
                    "away_score": s_match.group(3),
                    "away": s_match.group(4).strip()
                })
                pending_time = None
                continue

            m_match = match_regex.match(line)
            if m_match:
                if not re.search(r'هفته|نیمه|گروه|پایانی|رفت|برگشت', m_match.group(1)):
                    current_league["matches"].append({
                        "time": pending_time or "ساعت نامشخص",
                        "status": "UPCOMING",
                        "home": m_match.group(1).strip(),
                        "away": m_match.group(2).strip()
                    })
                    pending_time = None

    return events

def get_target_meta(league_name):
    for target in TARGET_LEAGUES:
        if re.search(target["pattern"], league_name, re.IGNORECASE):
            return target
    return None

def build_telegram_report(events):
    filtered_events = []
    for ev in events:
        meta = get_target_meta(ev["league"])
        if meta and ev["matches"]:
            filtered_events.append((meta["order"], meta["name"], ev["date"], ev["matches"]))

    if not filtered_events:
        return None

    filtered_events.sort(key=lambda x: x[0])
    
    msg = "⚽️ <b>کنداکتور مسابقات فوتبال و پخش زنده</b> ⚽️\n"
    msg += "───────────────────────\n"

    for _, name, date_str, matches in filtered_events:
        msg += f"\n📌 <b>{name}</b>  📅 <code>{date_str}</code>\n"
        for m in matches:
            if m["status"] == "FT":
                msg += f"  ✅ <b>{m['home']}</b> <b>{m['home_score']} - {m['away_score']}</b> <b>{m['away']}</b> <i>(پایان)</i>\n"
            else:
                msg += f"  ⏳ <code>{m['time']}</code>  <b>{m['home']}</b> 🆚 <b>{m['away']}</b>\n"

    msg += "\n───────────────────────\n"
    msg += "🤖 <i>Majiix Automation Hub</i>"
    return msg

def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ توکن یا چت‌آیدی تلگرام تنظیم نشده است. خروجی در ترمینال:")
        print(text)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    print("✅ پیام با موفقیت به تلگرام ارسال شد.")

if __name__ == "__main__":
    print("🌐 در حال استخراج مسابقات زنده از ورزش ۳...")
    raw_text = fetch_varzesh3_raw_text()
    events = parse_matches(raw_text)
    report = build_telegram_report(events)

    if report:
        send_telegram_message(report)
    else:
        print("ℹ️ هیچ مسابقه‌ای برای لیگ‌های هدف پیدا نشد.")

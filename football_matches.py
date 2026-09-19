import os, re, sys, logging
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
URL = "https://www.varzesh3.com/livescore"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36", "Accept-Language": "fa,en;q=0.9"}

ICONS = {"ایران":"🇮🇷","انگلیس":"🏴󠁧󠁢󠁥󠁮󠁧󠁿","اسپانیا":"🇪🇸","ایتالیا":"🇮🇹","آلمان":"🇩🇪","فرانسه":"🇫🇷","اروپا":"🇪🇺","قهرمانان":"🌟","آسیا":"🌏","ترکیه":"🇹🇷","عربستان":"🇸🇦","هلند":"🇳🇱","دوستانه":"🤝"}

def icon(n):
    for k,v in ICONS.items():
        if k in n: return v
    return "⚽️"

def fetch():
    r = requests.get(URL, headers=HEADERS, timeout=25)
    r.raise_for_status()
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    schedule = {}
    containers = soup.select(".league-stage, .match-group, .live-score-league, .stage-wrapper, .league-matches")
    for c in containers:
        t = c.select_one(".league-name, .stage-title, .league-title, h3, h4, .title")
        lg = t.get_text(strip=True) if t else "مسابقات فوتبال"
        if any(s in lg for s in ["بسکتبال","والیبال","هندبال","کشتی"]): continue
        rows = c.select(".match-item, .item-match, .match-row, tr")
        lst = []
        for row in rows:
            tm = row.select_one(".match-time, .time, .start-time, .scheduled-time")
            h = row.select_one(".team-home, .home-team, .team-a, .host")
            a = row.select_one(".team-away, .away-team, .team-b, .guest")
            if tm and (h or a):
                mt = tm.get_text(strip=True); mh = h.get_text(strip=True) if h else ""; ma = a.get_text(strip=True) if a else ""
                if ":" in mt and mh and ma:
                    lst.append(f"▫️ {mh} 🆚 {ma} | ⏰ {mt}")
        if lst: schedule[lg] = lst
    if not schedule:
        lines = [l.strip() for l in soup.get_text(separator="\n").split("\n") if l.strip()]
        cur = "سایر مسابقات معتبر"
        for line in lines:
            if any(w in line for w in ["لیگ","جام","لالیگا","سری آ","بوندسلیگا"]) and len(line) < 40 and not any(s in line for s in ["بسکتبال","والیبال","فوتسال"]):
                cur = line; schedule.setdefault(cur, [])
            m = re.search(r"(\d{1,2}:\d{2})", line)
            if m and "-" in line:
                mt = m.group(1)
                tp = line.replace(mt, "").replace("نتیجه نهایی", "").strip()
                parts = [x.strip() for x in tp.split("-") if x.strip()]
                if len(parts) >= 2:
                    entry = f"▫️ {parts[0]} 🆚 {parts[1]} | ⏰ {mt}"
                    schedule.setdefault(cur, [])
                    if entry not in schedule[cur]: schedule[cur].append(entry)
    return schedule

def build(s):
    now = datetime.now(timezone(timedelta(hours=3, minutes=30)))
    wd = {0:"دوشنبه",1:"سه‌شنبه",2:"چهارشنبه",3:"پنج‌شنبه",4:"جمعه",5:"شنبه",6:"یکشنبه"}
    msg = ["⚽️ <b>برنامه و ساعت بازی‌های مهم فوتبال امروز</b>", f"📅 <b>{wd.get(now.weekday(),'')} {now.strftime('%Y/%m/%d')}</b>", "━━━━━━━━━━━━━━━━━━"]
    if not s:
        msg.append("\n⚠️ <i>امروز بازی مهمی در کنداکتور ثبت نشده است.</i>")
    else:
        for lg, ms in list(s.items())[:10]:
            msg.append(f"\n{icon(lg)} <b>{lg}</b>")
            msg.extend(ms[:8])
    msg += ["\n━━━━━━━━━━━━━━━━━━", "💠 <b>MAJIX Suite</b>", "🆔 @majiix1"]
    return "\n".join(msg)

def send(text):
    if not TG_TOKEN or not TG_CHAT_ID:
        logging.error("Missing TG_TOKEN/TG_CHAT_ID"); sys.exit(1)
    r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", json={"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=20)
    if r.status_code != 200:
        logging.error(r.text); sys.exit(1)
    logging.info("Sent OK!")

if __name__ == "__main__":
    try:
        send(build(fetch()))
    except Exception as e:
        logging.exception(e); sys.exit(1)
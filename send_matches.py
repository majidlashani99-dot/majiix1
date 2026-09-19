#!/usr/bin/env python3
"""
Majix Daily Football Bot
------------------------
هر روز برنامه بازی‌های فوتبال را از اسکوریاب (scoreyab.com) می‌خواند
و یک پیام مرتب و زیبا در کانال تلگرام می‌فرستد.

ترتیب کار:
  1) خواندن صفحه اصلی اسکوریاب (منبع اصلی)
  2) اگر سایت در دسترس نبود یا چیزی پیدا نشد -> API-Football با FOOTBALL_API_KEY (پشتیبان)
  3) ارسال به تلگرام با TG_TOKEN و TG_CHAT_ID

متغیرهای محیطی:
  TG_TOKEN          توکن ربات تلگرام            (اجباری)
  TG_CHAT_ID        آیدی کانال                  (اجباری)
  FOOTBALL_API_KEY  کلید API-Football           (اختیاری، برای پشتیبان)
  DRY_RUN=1         فقط چاپ کن، نفرست (برای تست)
"""
from __future__ import annotations

import html
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

# ───────────────────────────── تنظیمات ─────────────────────────────
SOURCE_URL = "https://scoreyab.com/"
API_FOOTBALL_URL = "https://v3.football.api-sports.io/fixtures"
TZ = ZoneInfo("Asia/Tehran")
MAX_MESSAGE_LEN = 3800  # سقف تلگرام ۴۰۹۶ است؛ کمی حاشیه امن
FOOTER = "🕒 ساعت‌ها به وقت تهران\n📡 منبع: اسکوریاب  •  ⚽ Majix"

ENGLAND = "\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F"

# شناسه لیگ (همان عدد آخر آدرس لیگ در اسکوریاب) -> (پرچم، نام فارسی)
LEAGUES: dict[int, tuple[str, str]] = {
    290: ("🇮🇷", "لیگ برتر خلیج فارس"),
    39: (ENGLAND, "لیگ برتر انگلیس"),
    140: ("🇪🇸", "لالیگا"),
    135: ("🇮🇹", "سری آ ایتالیا"),
    78: ("🇩🇪", "بوندسلیگا آلمان"),
    61: ("🇫🇷", "لیگ ۱ فرانسه"),
    2: ("🏆", "لیگ قهرمانان اروپا"),
    3: ("🏆", "لیگ اروپا"),
    848: ("🏆", "لیگ کنفرانس اروپا"),
    88: ("🇳🇱", "اردیویسه هلند"),
    94: ("🇵🇹", "لیگ برتر پرتغال"),
    203: ("🇹🇷", "سوپرلیگ ترکیه"),
    307: ("🇸🇦", "لیگ برتر عربستان"),
    253: ("🇺🇸", "ام‌ال‌اس"),
    45: (ENGLAND, "جام حذفی انگلیس"),
    48: (ENGLAND, "جام اتحادیه انگلیس"),
    143: ("🇪🇸", "کوپا دل ری"),
    1: ("🌍", "جام جهانی"),
    4: ("🌍", "یورو"),
    5: ("🌍", "لیگ ملت‌های اروپا"),
    9: ("🌎", "کوپا آمریکا"),
}

WEEKDAYS = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

RLM = "\u200f"  # علامت راست‌به‌چپ؛ چیدمان پیام را درست نگه می‌دارد

_FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_EN_TO_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_FLAG_RE = re.compile("[\U0001F1E6-\U0001F1FF]")
_TIME_RE = re.compile(r"^(?:[01]?\d|2[0-3]):[0-5]\d$")
_LEAGUE_HREF_RE = re.compile(r"/football/league/[^/?#]+-(\d+)/?$")
_TEAM_HREF_RE = re.compile(r"/football/team/")


@dataclass(frozen=True)
class Match:
    league_id: Optional[int]
    league: str
    kickoff: str  # "HH:MM" (انگلیسی)
    home: str
    away: str


def log(msg: str) -> None:
    print(msg, flush=True)


def to_en(text: str) -> str:
    return text.translate(_FA_TO_EN)


def to_fa(text: str) -> str:
    return text.translate(_EN_TO_FA)


# ─────────────────────────── تاریخ شمسی ───────────────────────────
def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (
        355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100
        + (gy2 + 399) // 400 + gd + g_d_m[gm - 1]
    )
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return jy, jm, jd


def jalali_label(d: date) -> str:
    jy, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
    weekday = WEEKDAYS[(d.weekday() + 2) % 7]  # دوشنبه=0 در پایتون -> شنبه=0 در تقویم ایرانی
    return to_fa(f"{weekday} {jd} {MONTHS[jm - 1]} {jy}")


# ─────────────────────── منبع ۱: اسکوریاب ───────────────────────
def fetch_scoreyab_html() -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.5",
    }
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            resp = requests.get(SOURCE_URL, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.content.decode("utf-8", errors="replace")
        except requests.RequestException as exc:
            last_error = exc
            log(f"⚠️  تلاش {attempt}/3 برای اسکوریاب ناموفق بود: {type(exc).__name__}")
            time.sleep(5 * attempt)
    raise RuntimeError(f"دریافت اسکوریاب ناموفق بود: {last_error}")


def parse_scoreyab(page: str) -> list[Match]:
    """
    ساختار صفحه را با ترتیب لینک‌ها می‌خواند (نه با کلاس‌های CSS که ممکن است عوض شوند):
      لینک لیگ  ->  [تیم میزبان، ساعت، تیم میهمان]  ->  ...
    """
    soup = BeautifulSoup(page, "html.parser")
    matches: list[Match] = []
    seen: set[tuple] = set()

    league_id: Optional[int] = None
    league_name = ""
    home: Optional[str] = None
    kickoff: Optional[str] = None

    for el in soup.find_all(True):
        href = el.get("href", "") if el.name == "a" else ""

        # ۱) سرتیتر لیگ
        m = _LEAGUE_HREF_RE.search(href)
        if m:
            league_id = int(m.group(1))
            name = _FLAG_RE.sub("", el.get_text(" ", strip=True)).strip()
            league_name = name or LEAGUES.get(league_id, ("", "سایر مسابقات"))[1]
            home = kickoff = None
            continue

        # ۲) تیم
        if el.name == "a" and _TEAM_HREF_RE.search(href):
            team = el.get_text(" ", strip=True)
            if not team:
                continue
            if home is None or kickoff is None:
                home, kickoff = team, None  # ردیف جدید (یا ردیفی که ساعت نداشت)
            else:
                key = (league_id, home, team, kickoff)
                if key not in seen and league_name:
                    seen.add(key)
                    matches.append(Match(league_id, league_name, kickoff, home, team))
                home = kickoff = None
            continue

        # ۳) ساعت شروع (المانی که فقط ساعت دارد، مثل ۱۵:۰۰)
        if home is not None and kickoff is None:
            text = el.string
            if text:
                clean = to_en(text.strip())
                if _TIME_RE.match(clean):
                    kickoff = clean.zfill(5)

    return matches


def get_from_scoreyab() -> list[Match]:
    return parse_scoreyab(fetch_scoreyab_html())


# ─────────────────── منبع ۲ (پشتیبان): API-Football ───────────────────
def get_from_api_football(api_key: str, today: date) -> list[Match]:
    resp = requests.get(
        API_FOOTBALL_URL,
        headers={"x-apisports-key": api_key},
        params={"date": today.isoformat(), "timezone": "Asia/Tehran"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        raise RuntimeError(f"API-Football error: {data['errors']}")
    return parse_api_football(data)


def parse_api_football(data: dict) -> list[Match]:
    found: list[Match] = []
    for item in data.get("response", []):
        league_id = item["league"]["id"]
        if league_id not in LEAGUES:
            continue
        if item["fixture"]["status"]["short"] not in ("NS", "TBD"):
            continue
        start = datetime.fromisoformat(item["fixture"]["date"]).astimezone(TZ)
        found.append(
            Match(
                league_id=league_id,
                league=LEAGUES[league_id][1],
                kickoff=start.strftime("%H:%M"),
                home=item["teams"]["home"]["name"],
                away=item["teams"]["away"]["name"],
            )
        )
    return found


# ───────────────────────── ساخت پیام ─────────────────────────
def league_block(name: str, league_id: Optional[int], items: list[Match]) -> str:
    flag = LEAGUES.get(league_id, ("⚽", ""))[0] if league_id else "⚽"
    lines = [f"{RLM}{flag} <b>{html.escape(name)}</b>"]
    for m in sorted(items, key=lambda x: x.kickoff):
        lines.append(
            f"{RLM}⏰ <code>{to_fa(m.kickoff)}</code>  "
            f"{html.escape(m.home)} ⚔️ {html.escape(m.away)}"
        )
    return "\n".join(lines)


def footer_text() -> str:
    return "\n".join(f"{RLM}{line}" for line in FOOTER.split("\n"))


def build_messages(matches: list[Match], today: date) -> list[str]:
    title = f"{RLM}⚽️ <b>برنامه بازی‌های امروز</b>\n{RLM}📅 {jalali_label(today)}"
    divider = f"{RLM}〰️〰️〰️〰️〰️〰️〰️〰️"
    footer = f"{divider}\n{footer_text()}"

    # گروه‌بندی به ترتیب اولین نمایش لیگ‌ها
    groups: dict[tuple[Optional[int], str], list[Match]] = {}
    for m in matches:
        groups.setdefault((m.league_id, m.league), []).append(m)
    blocks = [league_block(name, lid, items) for (lid, name), items in groups.items()]

    messages: list[str] = []
    current = f"{title}\n{divider}"
    limit = MAX_MESSAGE_LEN - len(footer) - 2

    for block in blocks:
        if len(current) + len(block) + 2 > limit:
            messages.append(current)
            current = f"{RLM}⚽️ <b>ادامه برنامه امروز</b>\n{divider}"
        current += f"\n\n{block}"
    messages.append(current)
    messages[-1] += f"\n\n{footer}"
    return messages


def build_empty_message(today: date) -> str:
    return (
        f"{RLM}⚽️ <b>برنامه بازی‌های امروز</b>\n"
        f"{RLM}📅 {jalali_label(today)}\n\n"
        f"{RLM}😴 امروز بازی مهمی برنامه‌ریزی نشده است.\n\n"
        + footer_text()
    )


# ───────────────────────── ارسال به تلگرام ─────────────────────────
def send_telegram(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    for attempt in range(1, 4):
        resp = requests.post(url, json=payload, timeout=30)
        if resp.ok:
            return
        if resp.status_code == 429:
            wait = resp.json().get("parameters", {}).get("retry_after", 5)
            log(f"⏳ محدودیت تلگرام؛ {wait} ثانیه صبر می‌کنم...")
            time.sleep(wait + 1)
            continue
        raise RuntimeError(f"Telegram {resp.status_code}: {resp.text}")
    raise RuntimeError("ارسال به تلگرام پس از ۳ تلاش ناموفق بود")


# ───────────────────────────── اجرا ─────────────────────────────
def main() -> int:
    token = os.environ.get("TG_TOKEN", "").strip()
    chat_id = os.environ.get("TG_CHAT_ID", "").strip()
    api_key = os.environ.get("FOOTBALL_API_KEY", "").strip()
    dry_run = os.environ.get("DRY_RUN") == "1"

    if not dry_run and not (token and chat_id):
        log("❌ TG_TOKEN و TG_CHAT_ID باید در Secrets ریپازیتوری تنظیم شوند.")
        return 1

    today = datetime.now(TZ).date()
    log(f"📅 تاریخ امروز (تهران): {today.isoformat()}")

    matches: list[Match] = []
    confirmed_empty = False  # یعنی یک منبع سالم پاسخ داد و واقعاً بازی‌ای نبود

    try:
        matches = get_from_scoreyab()
        log(f"✅ اسکوریاب: {len(matches)} بازی")
    except Exception as exc:  # noqa: BLE001
        log(f"⚠️  منبع اصلی خطا داد: {exc}")

    if not matches and api_key:
        try:
            matches = get_from_api_football(api_key, today)
            confirmed_empty = not matches
            log(f"✅ API-Football (پشتیبان): {len(matches)} بازی")
        except Exception as exc:  # noqa: BLE001
            log(f"⚠️  منبع پشتیبان هم خطا داد: {exc}")

    if not matches and not confirmed_empty:
        log("❌ هیچ بازی‌ای دریافت نشد؛ برای جلوگیری از پیام اشتباه، چیزی ارسال نشد.")
        return 1

    messages = build_messages(matches, today) if matches else [build_empty_message(today)]

    for i, text in enumerate(messages, 1):
        if dry_run:
            log(f"\n──────── پیام {i}/{len(messages)} ({len(text)} کاراکتر) ────────\n{text}")
        else:
            send_telegram(token, chat_id, text)
            log(f"📨 پیام {i}/{len(messages)} ارسال شد")
            time.sleep(1)

    return 0


if __name__ == "__main__":
    sys.exit(main())

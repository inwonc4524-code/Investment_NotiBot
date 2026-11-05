# -*- coding: utf-8 -*-
"""
주식·ETF 테마 뉴스 알림 봇
- 내가 정한 테마(반도체, AI, 2차전지 …)의 한국·미국·세계 뉴스를 모아서
  휴대폰(ntfy 앱)으로 테마별 요약 알림을 보냅니다.
- 이미 보낸 기사는 seen.json 에 기록해서 다시 보내지 않습니다.
- 영어 기사 제목은 한국어로 번역해서 보여줍니다.

★ 테마를 바꾸고 싶으면 아래 '1) 내 관심 테마' 부분만 고치면 됩니다.
"""
import json
import os
import re
import sys
import time
import email.utils
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
import xml.etree.ElementTree as ET

import requests

# ─────────────────────────────────────────────
# 1) 내 관심 테마
#    name : 알림에 보일 테마 이름
#    kr   : 한국 뉴스 검색어 (한글)
#    en   : 미국·세계 뉴스 검색어 (영어)
#    검색어는 여러 개 넣을 수 있고, 하나라도 들어간 기사를 찾습니다.
#    etfs : 이 테마와 연결된 내 ETF (알림 맨 위에 표시)
# ─────────────────────────────────────────────
THEMES = [
    {"name": "🇺🇸 미국 S&P500",
     "etfs": "TIGER 미국S&P500",
     "kr": ["S&P500", "뉴욕증시", "미국 증시", "연준 금리"],
     "en": ["S&P 500", "Wall Street stocks", "Federal Reserve rate", "US stock market"]},
    {"name": "🧬 나스닥 바이오",
     "etfs": "TIGER 미국나스닥바이오",
     "kr": ["나스닥 바이오", "미국 바이오주", "바이오 ETF", "FDA 승인"],
     "en": ["biotech stocks", "Nasdaq Biotechnology", "IBB ETF", "XBI", "FDA approval"]},
    {"name": "🔋 2차전지",
     "etfs": "TIGER 2차전지테마 · KODEX 2차전지산업 · TIGER 2차전지소재Fn",
     "kr": ["2차전지", "이차전지", "LG에너지솔루션", "에코프로비엠", "포스코퓨처엠", "양극재", "리튬 가격"],
     "en": ["EV battery", "lithium price", "battery makers", "CATL", "cathode materials"]},
    {"name": "⚡ 전고체배터리·ESS",
     "etfs": "KODEX 전고체배터리ESS TOP2플러스",
     "kr": ["전고체 배터리", "전고체 전지", "ESS 배터리", "에너지저장장치", "삼성SDI 전고체"],
     "en": ["solid-state battery", "energy storage system", "ESS battery", "grid-scale storage"]},
    {"name": "🏭 AI 전력",
     "etfs": "ACE 코리아AI전력TOP10",
     "kr": ["AI 전력", "전력기기", "변압기 수출", "HD현대일렉트릭", "효성중공업", "LS ELECTRIC", "두산에너빌리티"],
     "en": ["AI power demand", "data center power", "transformer shortage", "power grid investment"]},
]

# ─────────────────────────────────────────────
# 2) 어느 지역 뉴스를 볼지
#    필요 없는 지역은 줄 앞에 # 을 붙이면 꺼집니다.
# ─────────────────────────────────────────────
REGIONS = [
    {"key": "kr", "label": "🇰🇷 한국", "words": "kr", "hl": "ko", "gl": "KR", "ceid": "KR:ko"},
    {"key": "us", "label": "🇺🇸 미국", "words": "en", "hl": "en-US", "gl": "US", "ceid": "US:en"},
    {"key": "world", "label": "🌍 세계", "words": "en", "hl": "en-GB", "gl": "GB", "ceid": "GB:en"},
]

# ─────────────────────────────────────────────
# 3) 기타 설정
# ─────────────────────────────────────────────
MAX_PER_REGION = 3        # 테마 하나에서 지역별로 최대 몇 개까지 보낼지
# "each"   = 기사 하나당 알림 하나 (알림을 누르면 그 기사로 바로 이동)
# "digest" = 테마마다 알림 하나에 기사 목록을 모아서 (알림 수가 적음)
NOTIFY_MODE = "each"
MAX_AGE_HOURS = 24        # 이보다 오래된 기사는 무시
TRANSLATE_EN = True       # 영어 제목을 한국어로 번역 (False 로 바꾸면 원문 그대로)
SHOW_ORIGINAL_EN = False  # True 로 바꾸면 번역 아래 영어 원문 제목도 함께 표시
KEEP_DAYS = 7             # 보낸 기사 기록을 며칠 동안 보관할지

# 이런 단어가 제목에 있으면 제외 (광고성·무관한 기사 걸러내기)
EXCLUDE = re.compile(r"리딩방|무료\s*추천|급등주\s*추천|카톡방|sponsored|press release", re.I)

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
REPORT_MODE = os.environ.get("REPORT_MODE", "") == "true"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen.json")
KST = timezone(timedelta(hours=9))
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Investment-NotiBot/1.0)"}


# ─────────────────────────────────────────────
# 뉴스 가져오기
# ─────────────────────────────────────────────
def build_query(words):
    parts = []
    for w in words:
        w = w.strip()
        if not w:
            continue
        parts.append(f'"{w}"' if " " in w else w)
    return "(" + " OR ".join(parts) + ")"


def search_url(region, words, when="1d", rss=True):
    q = build_query(words) + (f" when:{when}" if when else "")
    path = "rss/search" if rss else "search"
    return (f"https://news.google.com/{path}?q={quote(q)}"
            f"&hl={region['hl']}&gl={region['gl']}&ceid={region['ceid']}")


def parse_rss(xml_text):
    """구글 뉴스 RSS → [{title, source, link, published}]"""
    items = []
    root = ET.fromstring(xml_text)
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        src_el = it.find("source")
        source = (src_el.text or "").strip() if src_el is not None and src_el.text else ""
        # 구글 뉴스 제목 끝의 " - 언론사" 떼기
        if source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)].strip()
        elif not source and " - " in title:
            title, source = title.rsplit(" - ", 1)
        pub = None
        pd = it.findtext("pubDate")
        if pd:
            try:
                pub = email.utils.parsedate_to_datetime(pd)
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
            except Exception:
                pub = None
        if title and link:
            items.append({"title": title, "source": source, "link": link, "published": pub})
    return items


def fetch_news(region, words):
    url = search_url(region, words)
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return parse_rss(r.text)
        except Exception as e:
            print(f"  ! {region['label']} 가져오기 실패 ({attempt + 1}/3): {e}")
            time.sleep(3)
    return None


# ─────────────────────────────────────────────
# 번역 (실패하면 원문 그대로)
# ─────────────────────────────────────────────
_translate_cache = {}


def translate_ko(text):
    if not TRANSLATE_EN or not text or re.search(r"[가-힣]", text):
        return text
    if text in _translate_cache:
        return _translate_cache[text]
    try:
        r = requests.get("https://translate.googleapis.com/translate_a/single",
                         params={"client": "gtx", "sl": "auto", "tl": "ko", "dt": "t", "q": text},
                         headers=HEADERS, timeout=15)
        r.raise_for_status()
        out = "".join(seg[0] for seg in r.json()[0] if seg and seg[0]).strip()
        result = out or text
    except Exception as e:
        print(f"  ! 번역 실패: {e}")
        result = text
    _translate_cache[text] = result
    time.sleep(0.2)
    return result


# ─────────────────────────────────────────────
# 기록 (중복 방지)
# ─────────────────────────────────────────────
def title_key(title):
    return re.sub(r"[^0-9a-z가-힣]", "", title.lower())[:80]


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) and "seen" in data else {"seen": {}}
    except Exception:
        return {"seen": {}}


def save_state(state):
    cutoff = time.time() - KEEP_DAYS * 86400
    state["seen"] = {k: v for k, v in state["seen"].items() if v >= cutoff}
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=0, sort_keys=True)


# ─────────────────────────────────────────────
# 휴대폰 알림
# ─────────────────────────────────────────────
def notify(title, message, click=None, actions=None, tags=None, priority=3):
    if not NTFY_TOPIC:
        print("[NTFY_TOPIC 없음 — 알림 대신 화면에 출력]\n" + title + "\n" + message + "\n")
        return True
    body = {"topic": NTFY_TOPIC, "title": title, "message": message[:3900], "priority": priority}
    if click:
        body["click"] = click
    if actions:
        body["actions"] = actions[:3]
    if tags:
        body["tags"] = tags
    for attempt in range(3):
        try:
            r = requests.post("https://ntfy.sh/", data=json.dumps(body).encode("utf-8"),
                              headers={"Content-Type": "application/json"}, timeout=20)
            r.raise_for_status()
            return True
        except Exception as e:
            print(f"  ! 알림 전송 실패 ({attempt + 1}/3): {e}")
            time.sleep(3)
    return False


# ─────────────────────────────────────────────
# 실행
# ─────────────────────────────────────────────
def main():
    state = load_state()
    seen = state["seen"]
    now = datetime.now(timezone.utc)
    oldest = now - timedelta(hours=MAX_AGE_HOURS)
    report = []
    sent_total = 0
    failed = []

    for theme in THEMES:
        name = theme["name"]
        print(f"■ {name}")
        actions = []
        new_keys = []
        theme_items = []
        for region in REGIONS:
            words = theme.get(region["words"]) or []
            if not words:
                continue
            actions.append({"action": "view", "label": region["label"],
                            "url": search_url(region, words, rss=False)})
            items = fetch_news(region, words)
            if items is None:
                failed.append(f"{name}/{region['label']}")
                continue
            items.sort(key=lambda x: x["published"] or now, reverse=True)
            picked = []
            for it in items:
                if it["published"] and it["published"] < oldest:
                    continue
                if EXCLUDE.search(it["title"]):
                    continue
                k = title_key(it["title"])
                if not k or k in seen or k in new_keys:
                    continue
                new_keys.append(k)
                picked.append(it)
                if len(picked) >= MAX_PER_REGION:
                    break
            print(f"  {region['label']}: 검색 {len(items)}건 → 새 기사 {len(picked)}건")
            for it in picked:
                it["region"] = region
                it["key"] = title_key(it["title"])
                it["show"] = translate_ko(it["title"]) if region["words"] == "en" else it["title"]
                when = it["published"].astimezone(KST).strftime("%m/%d %H:%M") if it["published"] else ""
                it["meta"] = " · ".join(x for x in [it["source"], when] if x)
            theme_items.extend(picked)

        report.append(f"{name}: {len(theme_items)}건")
        if not theme_items:
            continue

        if NOTIFY_MODE == "each":
            # 오래된 기사부터 보내서, 휴대폰에서는 가장 최신 기사가 맨 위에 오게 함
            theme_items.sort(key=lambda x: x["published"] or now)
            for it in theme_items:
                msg = it["show"]
                if SHOW_ORIGINAL_EN and it["show"] != it["title"]:
                    msg += f"\n({it['title']})"
                if it["meta"]:
                    msg += f"\n{it['meta']}"
                ok = notify(f"{name} · {it['region']['label']}", msg, click=it["link"],
                            actions=[{"action": "view", "label": "기사 열기", "url": it["link"]}],
                            tags=["newspaper"])
                if ok:
                    seen[it["key"]] = time.time()
                    sent_total += 1
                time.sleep(0.5)
        else:
            sections = []
            for region in REGIONS:
                rows = [it for it in theme_items if it["region"] is region]
                if rows:
                    sections.append(region["label"] + "\n" + "\n".join(
                        f"• {it['show']}" + (f" — {it['meta']}" if it["meta"] else "") for it in rows))
            head = f"보유: {theme['etfs']}\n\n" if theme.get("etfs") else ""
            ok = notify(f"{name} 뉴스 {len(theme_items)}건", head + "\n\n".join(sections),
                        click=actions[0]["url"] if actions else None, actions=actions, tags=["newspaper"])
            if ok:
                for it in theme_items:
                    seen[it["key"]] = time.time()
                sent_total += len(theme_items)
                time.sleep(1)

    save_state(state)
    stamp = datetime.now(KST).strftime("%m/%d %H:%M")
    print(f"완료 {stamp} — 새 기사 {sent_total}건")

    if REPORT_MODE:
        msg = "\n".join(report)
        if failed:
            msg += "\n\n가져오기 실패: " + ", ".join(failed)
        notify(f"✅ 뉴스 봇 점검 ({stamp})", msg + f"\n\n총 새 기사 {sent_total}건", tags=["white_check_mark"], priority=2)

    # 전부 실패했다면 GitHub에서 빨간불로 보이게
    total_regions = sum(1 for t in THEMES for r in REGIONS if t.get(r["words"]))
    if total_regions and len(failed) == total_regions:
        sys.exit(1)


if __name__ == "__main__":
    main()

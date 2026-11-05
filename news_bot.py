# -*- coding: utf-8 -*-
"""
주식·ETF 테마 뉴스 알림 봇
- 내가 정한 테마(반도체, AI, 2차전지 …)의 한국·미국·세계 뉴스를 모아서
  휴대폰(ntfy 앱)으로 테마별 요약 알림을 보냅니다.
- 이미 보낸 기사는 seen.json 에 기록해서 다시 보내지 않습니다.
- 한국어가 아닌 기사(영어·중국어 등)는 제목을 번역하고, 누르면 기사 전체가 한국어로 번역되어 열립니다. 원문 링크는 카드 맨 아래에 있어요.
- 알림은 한 번만 오고, 누르면 기사 목록 페이지가 열립니다 (기사마다 눌러서 원문으로 이동).

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
#    zh   : 홍콩·대만 뉴스 검색어 (중국어 번체)
#    검색어는 여러 개 넣을 수 있고, 하나라도 들어간 기사를 찾습니다.
#    etfs : 이 테마와 연결된 내 ETF (알림 맨 위에 표시)
# ─────────────────────────────────────────────
THEMES = [
    {"name": "🇺🇸 미국 S&P500",
     "etfs": "TIGER 미국S&P500",
     "kr": ["S&P500", "뉴욕증시", "미국 증시", "연준 금리"],
     "en": ["S&P 500", "Wall Street stocks", "Federal Reserve rate", "US stock market"],
     "zh": ["美股", "標普500", "聯準會", "美聯儲", "華爾街"]},
    {"name": "🧬 나스닥 바이오",
     "etfs": "TIGER 미국나스닥바이오",
     "kr": ["나스닥 바이오", "미국 바이오주", "바이오 ETF", "FDA 승인"],
     "en": ["biotech stocks", "Nasdaq Biotechnology", "IBB ETF", "XBI", "FDA approval"],
     "zh": ["生技股", "生物科技股", "納斯達克生技", "FDA 批准"]},
    {"name": "🔋 2차전지",
     "etfs": "TIGER 2차전지테마 · KODEX 2차전지산업 · TIGER 2차전지소재Fn",
     "kr": ["2차전지", "이차전지", "LG에너지솔루션", "에코프로비엠", "포스코퓨처엠", "양극재", "리튬 가격"],
     "en": ["EV battery", "lithium price", "battery makers", "CATL", "cathode materials"],
     "zh": ["電池股", "鋰電池", "寧德時代", "鋰價", "正極材料"]},
    {"name": "⚡ 전고체배터리·ESS",
     "etfs": "KODEX 전고체배터리ESS TOP2플러스",
     "kr": ["전고체 배터리", "전고체 전지", "ESS 배터리", "에너지저장장치", "삼성SDI 전고체"],
     "en": ["solid-state battery", "energy storage system", "ESS battery", "grid-scale storage"],
     "zh": ["固態電池", "全固態電池", "儲能", "儲能系統"]},
    {"name": "🏭 AI 전력",
     "etfs": "ACE 코리아AI전력TOP10",
     "kr": ["AI 전력", "전력기기", "변압기 수출", "HD현대일렉트릭", "효성중공업", "LS ELECTRIC", "두산에너빌리티"],
     "en": ["AI power demand", "data center power", "transformer shortage", "power grid investment"],
     "zh": ["AI 電力", "重電股", "變壓器", "資料中心 電力", "電網"]},
    {"name": "🤖 로봇",
     "etfs": "",
     "kr": ["로봇 관련주", "휴머노이드", "레인보우로보틱스", "두산로보틱스", "로봇 ETF", "협동로봇"],
     "en": ["humanoid robot", "robotics stocks", "Tesla Optimus", "BOTZ ETF", "Figure AI", "industrial robots"],
     "zh": ["人形機器人", "機器人概念股", "機器人股", "優必選"]},
]

# ─────────────────────────────────────────────
# 2) 어느 지역 뉴스를 볼지
#    필요 없는 지역은 줄 앞에 # 을 붙이면 꺼집니다.
# ─────────────────────────────────────────────
REGIONS = [
    {"key": "kr", "label": "🇰🇷 한국", "words": "kr", "hl": "ko", "gl": "KR", "ceid": "KR:ko"},
    {"key": "us", "label": "🇺🇸 미국", "words": "en", "hl": "en-US", "gl": "US", "ceid": "US:en"},
    {"key": "world", "label": "🌍 세계", "words": "en", "hl": "en-GB", "gl": "GB", "ceid": "GB:en"},
    {"key": "hk", "label": "🇭🇰 홍콩", "words": "zh", "hl": "zh-HK", "gl": "HK", "ceid": "HK:zh-Hant"},
    {"key": "tw", "label": "🇹🇼 대만", "words": "zh", "hl": "zh-TW", "gl": "TW", "ceid": "TW:zh-Hant"},
]

# ─────────────────────────────────────────────
# 3) 기타 설정
# ─────────────────────────────────────────────
MAX_PER_REGION = 10       # 테마 하나에서 지역별로 최대 몇 개의 소식을 모을지 (화제성 높은 순)
MAX_AGE_HOURS = 24        # 이보다 오래된 기사는 무시
TRANSLATE_EN = True       # 영어 제목을 한국어로 번역 (False 로 바꾸면 원문 그대로)
KEEP_DAYS = 7             # 보낸 기사 기록을 며칠 동안 보관할지
PAGE_DAYS = 3             # 뉴스 목록 페이지에 며칠치 기사를 보여줄지
# 제목이 이만큼 비슷하면 같은 소식으로 묶음 (0~1, 낮을수록 더 많이 묶음)
SIMILAR = 0.3

# 이런 단어가 제목에 있으면 제외 (광고성·무관한 기사 걸러내기)
EXCLUDE = re.compile(r"리딩방|무료\s*추천|급등주\s*추천|카톡방|sponsored|press release", re.I)

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
REPORT_MODE = os.environ.get("REPORT_MODE", "") == "true"
HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "seen.json")
NEWS_FILE = os.path.join(HERE, "docs", "news.json")
PAGE_FILE = os.path.join(HERE, "docs", "index.html")
MD_FILE = os.path.join(HERE, "NEWS.md")
SUMMARY_FILE = os.path.join(HERE, ".summary.json")
REPO = os.environ.get("GITHUB_REPOSITORY", "inwonc4524-code/Investment_NotiBot")
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
# 외국어 기사: 구글 뉴스 주소 → 실제 기사 주소 → 한국어 번역 링크
# ─────────────────────────────────────────────
def is_korean(text):
    return bool(re.search(r"[가-힣]", text or ""))


def decode_gnews(link):
    """news.google.com/rss/articles/... 주소에서 실제 언론사 기사 주소를 알아냄 (실패하면 None)"""
    m = re.search(r"news\.google\.com/(?:rss/)?(?:articles|read)/([^?/]+)", link or "")
    if not m:
        return link if link and "news.google.com" not in link else None
    gid = m.group(1)
    cookies = {"CONSENT": "YES+cb.20240101-00-p0.en+FX+000", "SOCS": "CAESEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg"}
    try:
        r = requests.get(f"https://news.google.com/rss/articles/{gid}", headers=HEADERS,
                         cookies=cookies, timeout=20)
        sg = re.search(r'data-n-a-sg="([^"]+)"', r.text)
        ts = re.search(r'data-n-a-ts="([^"]+)"', r.text)
        if not (sg and ts):
            return None
        inner = json.dumps(["garturlreq",
                            [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None,
                              None, None, 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
                            gid, int(ts.group(1)), sg.group(1)])
        req = json.dumps([[["Fbv4je", inner, None, "generic"]]])
        r = requests.post("https://news.google.com/_/DotsSplashUi/data/batchexecute",
                          data={"f.req": req}, cookies=cookies, timeout=20,
                          headers=dict(HEADERS, **{"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}))
        part = r.text.split("\n\n", 1)[1]
        data = json.loads(part)
        url = json.loads(data[0][2])[1]
        return url if isinstance(url, str) and url.startswith("http") else None
    except Exception as e:
        print(f"  ! 기사 주소 찾기 실패: {e}")
        return None


def translated_link(url):
    """구글 번역으로 기사 전체를 한국어로 보여주는 주소"""
    return "https://translate.google.com/translate?sl=auto&tl=ko&hl=ko&u=" + quote(url, safe="")


def add_real_urls(items, limit=200):
    """외국어 기사에 실제 주소(url) 붙이기"""
    done = ok = 0
    for n in items:
        if is_korean(n["title"]) or n.get("url") or n.get("url_tried", 0) >= 2 or done >= limit:
            continue
        done += 1
        u = decode_gnews(n["link"])
        if u:
            n["url"] = u
            ok += 1
        else:
            n["url_tried"] = n.get("url_tried", 0) + 1
        time.sleep(0.4)
    if done:
        print(f"외국어 기사 원문 주소 찾기: {ok}/{done}건 성공")


# ─────────────────────────────────────────────
# 기록 (중복 방지)
# ─────────────────────────────────────────────
def title_key(title):
    return re.sub(r"[^0-9a-z가-힣\u4e00-\u9fff\u3400-\u4dbf]", "", title.lower())[:80]


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
# 같은 소식 묶기 (화제성 = 같은 소식을 보도한 언론사 수)
# ─────────────────────────────────────────────
_STOP = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "as", "at", "by", "is", "are",
         "with", "from", "after", "its", "it", "be", "will", "says", "say", "new", "over"}


def _words(title):
    return {w for w in re.findall(r"[a-z0-9가-힣\u4e00-\u9fff]+", title.lower()) if w not in _STOP and len(w) > 1}


def _bigrams(title):
    s = re.sub(r"[^0-9a-z가-힣\u4e00-\u9fff\u3400-\u4dbf]", "", title.lower())
    return {s[i:i + 2] for i in range(len(s) - 1)}


def same_story(a, b):
    wa, wb = _words(a), _words(b)
    if min(len(wa), len(wb)) >= 3 and len(wa & wb) / min(len(wa), len(wb)) >= 0.6:
        return True
    ba, bb = _bigrams(a), _bigrams(b)
    return bool(ba and bb) and 2 * len(ba & bb) / (len(ba) + len(bb)) >= SIMILAR


def cluster(items):
    """비슷한 제목끼리 묶기. items 는 최신순이어야 함 → 묶음의 첫 기사가 가장 최신"""
    groups = []
    for it in items:
        for g in groups:
            if any(same_story(it["title"], m["title"]) for m in g[:6]):
                g.append(it)
                break
        else:
            groups.append([it])
    return groups


def n_sources(group):
    return len({(m["source"] or m["link"]).lower() for m in group})


# ─────────────────────────────────────────────
# 뉴스 목록 페이지 만들기
# ─────────────────────────────────────────────
def esc(t):
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def load_news():
    try:
        with open(NEWS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_news(news):
    os.makedirs(os.path.dirname(NEWS_FILE), exist_ok=True)
    with open(NEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(news, f, ensure_ascii=False, indent=0)


def build_pages(news, run_id, updated):
    by_theme = {t["name"]: [] for t in THEMES}
    for n in news:
        by_theme.setdefault(n["theme"], []).append(n)
    etfs = {t["name"]: t.get("etfs", "") for t in THEMES}

    # ① 예쁜 페이지 (GitHub Pages)
    nav = "".join(f'<a href="#t{i}">{esc(name)} <b>{len(items)}</b></a>'
                  for i, (name, items) in enumerate(by_theme.items()))
    body = []
    for i, (name, items) in enumerate(by_theme.items()):
        body.append(f'<section id="t{i}"><div class="sh"><h2>{esc(name)}</h2>'
                    f'<div class="ss"><button class="c on" onclick="srt(\'c\',this)">🔥 화제순</button>'
                    f'<button class="p" onclick="srt(\'p\',this)">🕒 최신순</button></div></div>')
        if etfs.get(name):
            body.append(f'<p class="etf">보유: {esc(etfs[name])}</p>')
        if not items:
            body.append('<p class="none">최근 기사 없음</p>')
        body.append('<div class="list">')
        for n in items:
            new = ' <span class="new">NEW</span>' if n.get("run") == run_id else ""
            orig = (f'<div class="orig">{esc(n["title"])}</div>'
                    if n["show"] != n["title"] else "")
            c = n.get("count", 1)
            hot = (f'<span class="hot{" big" if c >= 5 else ""}">🔥 언론 {c}곳</span>' if c > 1 else "")
            foreign = not is_korean(n["title"])
            real = n.get("url") or n["link"]
            # 외국어 기사: 누르면 한국어 번역본, 맨 아래에 원문 링크
            main = translated_link(n["url"]) if foreign and n.get("url") else real
            tr = '<span class="tr">한국어 번역</span>' if foreign and n.get("url") else ""
            foot = (f'<a class="src" href="{esc(real)}" target="_blank" rel="noopener">원문 보기 ↗ {esc(n["source"])}</a>'
                    if foreign else "")
            body.append(
                f'<div class="card" data-c="{c}" data-p="{int(n["pub"])}">'
                f'<a class="main" href="{esc(main)}" target="_blank" rel="noopener">'
                f'<div class="meta">{hot}{esc(n["region"])} · {esc(n["source"])} · {esc(n["time"])}{new}</div>'
                f'<div class="title">{esc(n["show"])}{tr}</div>{orig}</a>{foot}</div>')
        body.append("</div></section>")
    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#262624">
<title>투자 테마 뉴스</title>
<style>
@font-face{{font-family:'ChosunIlboMyungjo';src:url('https://cdn.jsdelivr.net/gh/projectnoonnu/noonfonts_one@1.0/Chosunilbo_myungjo.woff') format('woff');font-weight:normal;font-display:swap}}
:root{{color-scheme:dark;--bg:#262624;--card:#30302e;--card2:#3a3a37;--text:#faf9f5;--sub:#a6a39a;--line:#3e3e3a;--acc:#d97757}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 'ChosunIlboMyungjo',Georgia,"Noto Serif KR",serif;-webkit-font-smoothing:antialiased}}
header{{padding:22px 16px 10px;max-width:760px;margin:auto}}
h1{{font:600 22px/1.3 'ChosunIlboMyungjo',Georgia,serif;margin:0 0 4px;letter-spacing:-.2px}}
.upd{{color:var(--sub);font-size:12.5px}}
.sort{{display:flex;gap:6px;padding:4px 16px 8px;max-width:760px;margin:auto}}
.sort button{{border:1px solid var(--line);background:transparent;color:var(--sub);border-radius:8px;padding:5px 12px;font:inherit;font-size:13px}}
.sort button.on,.ss button.on{{background:var(--card2);border-color:var(--card2);color:var(--text)}}
.sh{{display:flex;align-items:flex-end;justify-content:space-between;gap:8px;margin:26px 4px 2px}}.sh h2{{margin:0}}
.ss{{display:flex;gap:4px;flex:none}}.ss button{{border:1px solid var(--line);background:transparent;color:var(--sub);border-radius:7px;padding:3px 8px;font:inherit;font-size:12px}}
nav{{position:sticky;top:0;z-index:1;display:flex;gap:6px;overflow-x:auto;padding:10px 16px;background:rgba(38,38,36,.94);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}}
nav a{{flex:none;padding:6px 12px;border-radius:999px;background:var(--card);color:var(--text);text-decoration:none;font-size:13px}}
nav b{{color:var(--acc);font-weight:600}}
main{{padding:4px 12px 48px;max-width:760px;margin:auto}}
section{{scroll-margin-top:56px}}
h2{{font:600 17px/1.3 'ChosunIlboMyungjo',Georgia,serif;margin:26px 4px 2px}}
.etf{{margin:0 4px 10px;color:var(--sub);font-size:12px}}
.card{{background:var(--card);border-radius:12px;margin:8px 0;overflow:hidden;transition:background .15s}}
.card:hover{{background:var(--card2)}}
.main{{display:block;padding:12px 14px;color:var(--text);text-decoration:none}}.main:active{{opacity:.75}}
.tr{{margin-left:6px;padding:0 5px;border:1px solid var(--line);border-radius:4px;color:var(--sub);font-size:11px;vertical-align:2px;white-space:nowrap}}
.src{{display:block;padding:8px 14px;border-top:1px solid var(--line);color:var(--acc);font-size:12.5px;text-decoration:none}}
.src:active{{opacity:.7}}
.meta{{color:var(--sub);font-size:12px}}
.title{{font-weight:500;margin-top:3px}}
.orig{{color:var(--sub);font-size:12px;margin-top:3px}}
.new{{margin-left:4px;color:var(--acc);font-size:11px;font-weight:700;letter-spacing:.3px}}
.none{{color:var(--sub);margin:4px}}
.hot{{display:inline-block;margin-right:6px;padding:0 6px;border-radius:4px;background:rgba(217,119,87,.16);color:var(--acc);font-weight:600}}
.hot.big{{background:var(--acc);color:#1f1e1d}}
</style></head><body>
<header><h1>📰 투자 테마 뉴스</h1><div class="upd">업데이트 {esc(updated)} · 최근 {PAGE_DAYS}일 · 외국어 기사는 누르면 한국어 번역본으로 열려요<br>🔥 언론 N곳 = 같은 소식을 보도한 언론사 수 (많을수록 화제)</div></header>
<div class="sort"><button class="c on" onclick="srt('c')">🔥 전체 화제순</button><button class="p" onclick="srt('p')">🕒 전체 최신순</button></div>
<nav>{nav}</nav><main>{''.join(body)}</main>
<script>
function srt(k,btn){{
  // btn 이 있으면 그 테마만, 없으면 전체 테마 정렬
  var secs = btn ? [btn.closest('section')] : [].slice.call(document.querySelectorAll('section'));
  secs.forEach(function(sec){{
    var l=sec.querySelector('.list'); if(!l) return;
    var a=[].slice.call(l.children);
    a.sort(function(x,y){{
      var c=(+y.dataset.c)-(+x.dataset.c), p=(+y.dataset.p)-(+x.dataset.p);
      return k==='c' ? (c||p) : (p||c);
    }});
    a.forEach(function(e){{l.appendChild(e);}});
    sec.querySelectorAll('.ss button').forEach(function(b){{b.classList.toggle('on', b.classList.contains(k));}});
  }});
  if(!btn) document.querySelectorAll('.sort button').forEach(function(b){{b.classList.toggle('on', b.classList.contains(k));}});
}}
</script></body></html>"""
    os.makedirs(os.path.dirname(PAGE_FILE), exist_ok=True)
    with open(PAGE_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    # ② 예비 페이지 (GitHub Pages 를 안 켰을 때 GitHub 화면에서 바로 보기)
    md = [f"# 📰 투자 테마 뉴스\n\n업데이트 {updated} · 최근 {PAGE_DAYS}일\n"]
    for name, items in by_theme.items():
        md.append(f"\n## {name}\n")
        if etfs.get(name):
            md.append(f"보유: {etfs[name]}\n")
        for n in items:
            new = " 🆕" if n.get("run") == run_id else ""
            t = n["show"].replace("[", "(").replace("]", ")")
            hot = f"🔥{n.get('count', 1)} " if n.get("count", 1) > 1 else ""
            if not is_korean(n["title"]) and n.get("url"):
                md.append(f"- {hot}[{t}]({translated_link(n['url'])}) — {n['region']} · {n['source']} · {n['time']}{new} · [원문 보기 ↗]({n['url']})")
            else:
                md.append(f"- {hot}[{t}]({n.get('url') or n['link']}) — {n['region']} · {n['source']} · {n['time']}{new}")
    with open(MD_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")


# ─────────────────────────────────────────────
# 1단계: 뉴스 모으기 + 페이지 만들기
# ─────────────────────────────────────────────
def collect():
    state = load_state()
    seen = state["seen"]
    now = datetime.now(timezone.utc)
    oldest = now - timedelta(hours=MAX_AGE_HOURS)
    run_id = now.strftime("%Y%m%d%H%M")
    new_items = []
    counts = {}
    failed = []
    taken = set()           # 이번에 고른 기사 (테마끼리도 중복 안 되게)

    # 페이지에 이미 있는 기사 (최근 PAGE_DAYS 일) — 같은 소식 보도가 늘면 화제성 숫자만 올려줌
    cutoff = time.time() - PAGE_DAYS * 86400
    old_news = [n for n in load_news() if n.get("pub", 0) >= cutoff]
    key_to_old = {}
    for n in old_news:
        for k in n.get("keys") or [n["key"]]:
            key_to_old[k] = n

    for theme in THEMES:
        name = theme["name"]
        print(f"■ {name}")
        counts[name] = 0
        groups_by_region = {}
        fetched = {}
        for region in REGIONS:
            words = theme.get(region["words"]) or []
            if not words:
                continue
            items = fetch_news(region, words)
            if items is None:
                failed.append(f"{name}/{region['label']}")
                continue
            items = [it for it in items
                     if not (it["published"] and it["published"] < oldest)
                     and not EXCLUDE.search(it["title"]) and title_key(it["title"])]
            items.sort(key=lambda x: x["published"] or now, reverse=True)
            fetched[region["key"]] = len(items)
            groups_by_region[region["key"]] = cluster(items)

        # 뒤 지역의 소식이 앞 지역(예: 세계→미국, 대만→홍콩)과 같으면 앞 지역 쪽으로 합침
        # (화제성 숫자에는 더해짐)
        merged = {}
        earlier = []
        for region in REGIONS:
            groups = groups_by_region.get(region["key"])
            if groups is None:
                continue
            left = []
            for g in groups:
                target = next((eg for eg in earlier
                               if any(same_story(g[0]["title"], m["title"]) for m in eg[:6])), None)
                if target is not None:
                    target.extend(g)
                    merged[region["key"]] = merged.get(region["key"], 0) + 1
                else:
                    left.append(g)
            groups_by_region[region["key"]] = left
            earlier.extend(left)

        for region in REGIONS:
            groups = groups_by_region.get(region["key"])
            if groups is None:
                continue
            # 화제성(보도한 언론사 수) 높은 순 → 같으면 최신순
            groups.sort(key=lambda g: (n_sources(g), max((m["published"] or now) for m in g)), reverse=True)
            picked = 0
            for g in groups:
                keys = list(dict.fromkeys(title_key(m["title"]) for m in g))
                cnt = n_sources(g)
                old = next((key_to_old[k] for k in keys if k in key_to_old), None)
                if old is not None:   # 이미 보낸 소식 → 숫자만 갱신
                    if cnt > old.get("count", 1):
                        old["count"] = cnt
                    old["keys"] = list(dict.fromkeys((old.get("keys") or [old["key"]]) + keys))[:60]
                    for k in keys:
                        seen[k] = time.time()
                        key_to_old[k] = old
                    continue
                if any(k in seen or k in taken for k in keys):
                    continue
                if picked >= MAX_PER_REGION:
                    continue
                rep = g[0]
                show = translate_ko(rep["title"])   # 한국어가 아닌 제목은 모두 번역
                pub = rep["published"] or now
                new_items.append({
                    "key": keys[0], "keys": keys[:60], "count": cnt,
                    "theme": name, "region": region["label"], "title": rep["title"],
                    "show": show, "source": rep["source"], "link": rep["link"],
                    "pub": pub.timestamp(), "time": pub.astimezone(KST).strftime("%m/%d %H:%M"),
                    "run": run_id})
                taken.update(keys)
                picked += 1
            counts[name] += picked
            extra = f", 앞 지역과 겹친 소식 {merged[region['key']]}건은 합침" if merged.get(region["key"]) else ""
            print(f"  {region['label']}: 기사 {fetched.get(region['key'], 0)}건 → 소식 {len(groups)}개 → 새 소식 {picked}개{extra}")

    # 기록 저장
    for n in new_items:
        for k in n["keys"]:
            seen[k] = time.time()
    save_state(state)

    # 페이지용 기사 목록: 테마 순서 → 화제성 높은 순 → 최신순
    news = old_news + new_items
    add_real_urls(news)
    order = {t["name"]: i for i, t in enumerate(THEMES)}
    news.sort(key=lambda n: (order.get(n["theme"], 99), -n.get("count", 1), -n["pub"]))
    save_news(news)
    updated = datetime.now(KST).strftime("%m/%d %H:%M")
    build_pages(news, run_id, updated)

    # 알림 단계에 넘겨줄 요약 (테마별 가장 화제인 새 소식)
    top = {}
    for n in sorted(new_items, key=lambda n: (-n["count"], -n["pub"])):
        if n["theme"] not in top:
            top[n["theme"]] = n["show"] + (f" (언론 {n['count']}곳)" if n["count"] > 1 else "")
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump({"counts": counts, "top": top, "failed": failed, "updated": updated,
                   "total": len(new_items)}, f, ensure_ascii=False)
    print(f"완료 {updated} — 새 소식 {len(new_items)}개")

    total_regions = sum(1 for t in THEMES for r in REGIONS if t.get(r["words"]))
    if total_regions and len(failed) == total_regions:
        sys.exit(1)


# ─────────────────────────────────────────────
# 2단계: 알림 한 번 보내기
# ─────────────────────────────────────────────
def send_summary():
    try:
        with open(SUMMARY_FILE, encoding="utf-8") as f:
            sm = json.load(f)
    except Exception:
        print("요약 파일 없음 — 알림 생략")
        return
    page = os.environ.get("PAGE_URL", "").strip()
    if not page:  # GitHub Pages 를 아직 안 켰으면 GitHub 화면의 예비 페이지로
        page = f"https://github.com/{REPO}/blob/main/NEWS.md"
    page += ("&" if "?" in page else "?") + "t=" + str(int(time.time()))

    total = sm["total"]
    if total == 0 and not REPORT_MODE:
        print("새 기사 없음 — 알림 생략")
        return
    lines = []
    for name, c in sm["counts"].items():
        if c:
            first = sm["top"].get(name, "")
            lines.append(f"{name} {c}개\n  🔥 {first}")
    if not lines:
        lines.append("새 소식이 없어요.")
    if sm["failed"]:
        lines.append("\n⚠️ 가져오기 실패: " + ", ".join(sm["failed"]))
    notify(f"📰 투자 뉴스 {total}개 ({sm['updated']})", "\n".join(lines), click=page,
           actions=[{"action": "view", "label": "뉴스 목록 열기", "url": page}],
           tags=["newspaper"], priority=3)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "notify":
        send_summary()
    else:
        collect()

# -*- coding: utf-8 -*-
"""
주식·ETF 테마 뉴스 알림 봇
- 내가 정한 테마(반도체, AI, 2차전지 …)의 한국·미국·세계 뉴스를 모아서
  휴대폰(ntfy 앱)으로 테마별 요약 알림을 보냅니다.
- 이미 보낸 기사는 seen.json 에 기록해서 다시 보내지 않습니다.
- 한국어가 아닌 기사(영어·중국어 등)는 제목을 한국어로 번역해서 보여줍니다.
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
MAX_PER_REGION = 6        # 한 번 실행할 때 테마·지역별로 최대 몇 개의 소식을 모을지 (화제성 높은 순)
SHOW_PER_THEME = 8        # 목록 페이지에서 테마마다 처음에 보여줄 기사 수 (나머지는 '더보기')
MAX_AGE_HOURS = 24        # 이보다 오래된 기사는 무시
TRANSLATE_EN = True       # 영어 제목을 한국어로 번역 (False 로 바꾸면 원문 그대로)
KEEP_DAYS = 7             # 보낸 기사 기록을 며칠 동안 보관할지
PAGE_DAYS = 3             # 뉴스 목록 페이지에 며칠치 기사를 보여줄지
# 제목이 이만큼 비슷하면 같은 소식으로 묶음 (0~1, 낮을수록 더 많이 묶음)
SIMILAR = 0.3

# 이런 단어가 제목에 있으면 제외 (광고성·무관한 기사 걸러내기)
EXCLUDE = re.compile(r"리딩방|무료\s*추천|급등주\s*추천|카톡방|sponsored|press release", re.I)

# ─────────────────────────────────────────────
# 믿을 만한 언론사만 (나라별)
#   - 점(.)이 들어간 건 사이트 주소, 아니면 언론사 이름
#   - 목록에 없는 곳의 기사는 가져오지 않습니다. 추가·삭제는 여기서.
# ─────────────────────────────────────────────
TRUSTED = {
    "kr": [
        "연합뉴스", "yna.co.kr", "연합인포맥스", "einfomax.co.kr",
        "한국경제", "hankyung.com", "매일경제", "mk.co.kr", "서울경제", "sedaily.com",
        "머니투데이", "mt.co.kr", "이데일리", "edaily.co.kr", "파이낸셜뉴스", "fnnews.com",
        "아시아경제", "asiae.co.kr", "헤럴드경제", "heraldcorp.com",
        "조선일보", "조선비즈", "Chosunbiz", "chosun.com", "중앙일보", "joongang.co.kr", "동아일보", "donga.com",
        "한겨레", "hani.co.kr", "경향신문", "khan.co.kr", "한국일보", "hankookilbo.com",
        "뉴스1", "news1.kr", "뉴시스", "newsis.com",
        "KBS", "kbs.co.kr", "MBC", "imbc.com", "SBS", "sbs.co.kr", "SBS Biz", "sbsbiz", "YTN", "ytn.co.kr",
        "전자신문", "etnews.com", "디지털타임스", "dt.co.kr",
    ],
    "us": [
        "Reuters", "reuters.com", "Bloomberg", "bloomberg.com", "Wall Street Journal", "WSJ", "wsj.com",
        "CNBC", "cnbc.com", "AP News", "Associated Press", "apnews.com",
        "New York Times", "nytimes.com", "Washington Post", "washingtonpost.com",
        "Financial Times", "ft.com", "MarketWatch", "marketwatch.com", "Barron's", "barrons.com",
        "Yahoo Finance", "finance.yahoo.com", "Fortune", "fortune.com", "Axios", "axios.com",
        "Investor's Business Daily", "investors.com", "NPR", "npr.org", "CNN", "cnn.com",
        "Fox Business", "foxbusiness.com", "Politico", "politico.com", "Los Angeles Times", "latimes.com",
    ],
    "world": [
        "Reuters", "reuters.com", "Bloomberg", "bloomberg.com", "Financial Times", "ft.com",
        "The Economist", "economist.com", "BBC", "bbc.com", "bbc.co.uk",
        "The Guardian", "theguardian.com", "The Telegraph", "telegraph.co.uk", "The Times", "thetimes.co.uk",
        "Nikkei Asia", "asia.nikkei.com", "South China Morning Post", "scmp.com",
        "Al Jazeera", "aljazeera.com", "Deutsche Welle", "dw.com", "Sky News", "news.sky.com",
        "CNBC", "cnbc.com", "AP News", "apnews.com", "Wall Street Journal", "wsj.com",
    ],
    "hk": [
        "南華早報", "South China Morning Post", "SCMP", "scmp.com", "明報", "mingpao.com",
        "經濟日報", "hket.com", "信報", "hkej.com", "香港電台", "RTHK", "rthk.hk",
        "星島", "stheadline.com", "now新聞", "news.now.com", "TVB", "無綫新聞", "tvb.com",
        "經濟通", "etnet", "etnet.com.hk", "AASTOCKS", "aastocks.com", "香港01", "hk01.com",
    ],
    "tw": [
        "中央社", "CNA", "cna.com.tw", "經濟日報", "money.udn.com", "聯合新聞網", "udn.com",
        "工商時報", "ctee.com.tw", "自由時報", "自由財經", "ltn.com.tw",
        "中時新聞網", "中國時報", "chinatimes.com", "公視", "pts.org.tw",
        "天下雜誌", "cw.com.tw", "商業周刊", "businessweekly.com.tw", "今周刊", "businesstoday.com.tw",
        "鉅亨網", "news.cnyes.com", "DIGITIMES", "digitimes.com.tw", "財訊", "wealth.com.tw", "TVBS", "tvbs.com.tw", "MoneyDJ", "moneydj.com",
    ],
}


def _domain(url):
    m = re.match(r"https?://([^/:]+)", url or "")
    return m.group(1).lower() if m else ""


# ── 해외 주요 외신 (미국·세계 뉴스에 함께 적용) ──
GLOBAL_PRESS = [
    "AFP", "afp.com", "France 24", "france24.com", "Nikkei", "nikkei.com", "Kyodo", "kyodonews.net",
    "Japan Times", "japantimes.co.jp", "Le Monde", "lemonde.fr", "Les Echos", "lesechos.fr",
    "Handelsblatt", "handelsblatt.com", "FAZ", "faz.net", "Spiegel", "spiegel.de",
    "El País", "elpais.com", "Il Sole 24 Ore", "ilsole24ore.com", "Globe and Mail", "theglobeandmail.com",
    "Australian Financial Review", "afr.com", "Straits Times", "straitstimes.com",
    "Business Times", "businesstimes.com.sg", "Economic Times", "economictimes.indiatimes.com",
    "Mint", "livemint.com", "Caixin", "caixinglobal.com", "Yicai", "yicaiglobal.com",
    "Korea Herald", "koreaherald.com", "Korea JoongAng Daily", "koreajoongangdaily.joins.com",
    "Semafor", "semafor.com", "The Atlantic", "theatlantic.com", "TIME", "time.com",
]
# ── 애널리스트·업계 전문지 (미국·세계 뉴스에 함께 적용) ──
EXPERT_PRESS = [
    # 리서치·투자
    "S&P Global", "spglobal.com", "FactSet", "factset.com",
    "Kiplinger", "kiplinger.com", "Breakingviews",
    # 바이오
    "STAT", "statnews.com", "Endpoints News", "endpts.com", "Fierce Biotech", "fiercebiotech.com",
    "Fierce Pharma", "fiercepharma.com", "BioPharma Dive", "biopharmadive.com", "BioSpace", "biospace.com",
    # 배터리·소재·에너지
    "Benchmark Mineral", "benchmarkminerals.com", "Fastmarkets", "fastmarkets.com", "Electrek", "electrek.co",
    "electrive", "electrive.com", "Energy-Storage.news", "energy-storage.news", "Utility Dive", "utilitydive.com",
    "Canary Media", "canarymedia.com", "POWER Magazine", "powermag.com", "Argus", "argusmedia.com",
    # 데이터센터·AI·로봇·테크
    "DatacenterDynamics", "datacenterdynamics.com", "The Robot Report", "therobotreport.com",
    "IEEE Spectrum", "spectrum.ieee.org", "TechCrunch", "techcrunch.com", "The Information", "theinformation.com",
    "The Verge", "theverge.com", "Ars Technica", "arstechnica.com", "Wired", "wired.com",
]
# ── 한국 전문지 ──
KR_EXPERT = [
    "더벨", "thebell.co.kr", "인베스트조선", "investchosun.com", "뉴스핌", "newspim.com",
    "이투데이", "etoday.co.kr", "비즈니스포스트", "businesspost.co.kr",
    "디일렉", "thelec.kr", "전기신문", "electimes.com", "에너지경제", "ekn.kr",
    "로봇신문", "irobotnews.com", "바이오스펙테이터", "biospectator.com", "약업신문", "yakup.com",
    "데일리팜", "dailypharm.com", "히트뉴스", "hitnews.co.kr",
]
TRUSTED["us"] += GLOBAL_PRESS + EXPERT_PRESS
TRUSTED["world"] += GLOBAL_PRESS + EXPERT_PRESS
TRUSTED["kr"] += KR_EXPERT

# ── 자동 추가에서 제외할 곳 (다른 기사 퍼 나르기·개인 투고·광고성) ──
BLOCKED = [
    "investing.com", "tradingview", "moomoo", "msn", "line today", "biggo", "ad-hoc-news", "kalkine",
    "gurufocus", "seeking alpha", "motley fool", "fool.com", "zacks", "investorplace", "24/7 wall st",
    "ainvest", "marketbeat", "simply wall st", "stocktwits", "nasdaq.com", "nasdaq", "benzinga",
    "yahoo新聞", "yahoo奇摩", "yahoo 財經", "yahoo股市", "cmoney", "鉅亨號", "pchome",
    "네이버", "naver", "다음", "daum", "블로그", "blog", "카페", "medium", "substack", "reddit",
    "youtube", "facebook", "x.com", "twitter", "newsbreak", "ground news", "flipboard",
    "epoch times", "大紀元", "新唐人", "zerohedge",
    "pr newswire", "prnewswire", "business wire", "businesswire", "globe newswire", "globenewswire",
    "accesswire", "newsfile", "einpresswire", "보도자료", "aol", "morningstar",
]
# 자동 추가 기준: 최근 14일 동안
AUTO_MIN_STORIES = 10      # 이 언론사가 보도한 소식이 10개 이상이고
AUTO_MIN_CO = 6            # 그중 주요 언론사 2곳 이상도 함께 보도한 소식이 6개 이상이며
AUTO_MIN_RATIO = 0.5       # 그 비율이 절반 이상이면 → 믿을 만한 곳으로 자동 추가
SOURCES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources.json")


def load_sources():
    try:
        with open(SOURCES_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


_AUTO = load_sources().get("auto", {})


def is_blocked(source, url=""):
    s = (source or "").lower() + " " + _domain(url)
    return any(b in s for b in BLOCKED)


def is_trusted(region_key, source, url=""):
    names = TRUSTED.get(region_key)
    if names is None:      # 목록이 없는 지역은 거르지 않음
        return True
    src = (source or "").lower()
    dom = _domain(url)
    for e in names:
        el = e.lower()
        if "." in el:
            if dom and (dom == el or dom.endswith("." + el)):
                return True
        elif el and len(el) <= 5:          # 짧은 이름은 단어가 정확히 맞을 때만 (예: STAT ≠ Statista)
            if re.search(r"(?<![0-9a-z가-힣])" + re.escape(el) + r"(?![0-9a-z가-힣])", src):
                return True
        elif el and el in src:
            return True
    # 인용·공동 보도 기준으로 자동 추가된 언론사
    if src and src in (x.lower() for x in _AUTO.get(region_key, [])) and not is_blocked(source, url):
        return True
    return False

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


def site_filters(region_key, chunk=20):
    """주요 언론사 사이트로 검색 범위 좁히기: (site:a.com OR site:b.com ...) — 너무 길면 여러 묶음으로"""
    doms = list(dict.fromkeys(e for e in TRUSTED.get(region_key, []) if "." in e))
    return ["(" + " OR ".join(f"site:{d}" for d in doms[i:i + chunk]) + ")" for i in range(0, len(doms), chunk)]


def search_url(region, words, when="1d", rss=True, sites=""):
    q = build_query(words) + (" " + sites if sites else "") + (f" when:{when}" if when else "")
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
        src_url = (src_el.get("url") or "") if src_el is not None else ""
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
            items.append({"title": title, "source": source, "src_url": src_url, "link": link, "published": pub})
    return items


def _get_rss(url, label):
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return parse_rss(r.text)
        except Exception as e:
            print(f"  ! {label} 가져오기 실패 ({attempt + 1}/3): {e}")
            time.sleep(3)
    return None


def fetch_news(region, words):
    # ① 주요 언론사 사이트 안에서 검색(여러 묶음) + ② 일반 검색 → 합침 (뒤에서 믿을 만한 곳만 남김)
    results = [_get_rss(search_url(region, words, sites=f), region["label"]) for f in site_filters(region["key"])]
    results.append(_get_rss(search_url(region, words), region["label"]))
    if all(r is None for r in results):
        return None
    seen_links, out = set(), []
    for it in [x for r in results for x in (r or [])]:
        if it["link"] not in seen_links:
            seen_links.add(it["link"])
            out.append(it)
    return out


# ─────────────────────────────────────────────
# 번역 (실패하면 원문 그대로)
# ─────────────────────────────────────────────
_translate_cache = {}


def translate_ko(text, tries=3):
    if not TRANSLATE_EN or not text or re.search(r"[가-힣]", text):
        return text
    if text in _translate_cache:
        return _translate_cache[text]
    result = text
    for attempt in range(tries):
        try:
            r = requests.get("https://translate.googleapis.com/translate_a/single",
                             params={"client": "gtx", "sl": "auto", "tl": "ko", "dt": "t", "q": text},
                             headers=HEADERS, timeout=15)
            r.raise_for_status()
            out = "".join(seg[0] for seg in r.json()[0] if seg and seg[0]).strip()
            if out:
                result = out
                break
        except Exception as e:
            print(f"  ! 번역 실패 ({attempt + 1}/{tries}): {e}")
        time.sleep(2 + attempt * 3)   # 2초 → 5초 쉬고 다시 시도
    if result != text:                # 실패한 건 기억하지 않음 → 다음 실행 때 다시 시도
        _translate_cache[text] = result
    time.sleep(0.2)
    return result


def retranslate_failed(items, limit=40):
    """예전에 번역에 실패해서 원문 그대로 남은 제목을 다시 번역"""
    done = fixed = 0
    for n in items:
        if done >= limit:
            break
        if not is_korean(n["title"]) and n.get("show") == n["title"]:
            done += 1
            ko = translate_ko(n["title"])
            if ko != n["title"]:
                n["show"] = ko
                fixed += 1
    if done:
        print(f"번역 다시 시도: {fixed}/{done}건 성공")


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


def add_real_urls(items, limit=200):
    """외국어 기사에 실제 언론사 주소(url) 붙이기 — 누르면 원문으로 바로 이동"""
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


def _stem(w):
    w = w[:-2] if w.endswith("'s") else w
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def _words(title):
    return {_stem(w) for w in re.findall(r"[a-z0-9'가-힣\u4e00-\u9fff]+", title.lower())
            if w not in _STOP and len(w) > 1}


def _bigrams(title):
    s = re.sub(r"[^0-9a-z가-힣\u4e00-\u9fff\u3400-\u4dbf]", "", title.lower())
    return {s[i:i + 2] for i in range(len(s) - 1)}


_CJK = re.compile(r"[가-힣\u4e00-\u9fff]")


def same_story(a, b):
    ca, cb = bool(_CJK.search(a)), bool(_CJK.search(b))
    if ca and cb:
        # 한국어·중국어: 글자 2개씩 묶어서 비교
        ba, bb = _bigrams(a), _bigrams(b)
        return bool(ba and bb) and 2 * len(ba & bb) / (len(ba) + len(bb)) >= SIMILAR
    if ca != cb:
        return False
    # 영어: 단어로 비교 (짧은 단어·흔한 단어 제외)
    wa, wb = _words(a), _words(b)
    if min(len(wa), len(wb)) < 3:
        return False
    common = len(wa & wb)
    return common >= 3 and common / min(len(wa), len(wb)) >= 0.6


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
    by_theme = {BREAKING_NAME: []}
    by_theme.update({t["name"]: [] for t in THEMES})
    brk = sorted(load_breaking().get("items", []), key=lambda n: -n["pub"])
    rk = {r["label"]: r["key"] for r in REGIONS}
    news = [n for n in brk + list(news)
            if any(is_trusted(k, n.get("source", ""), n.get("src_url") or n.get("url", ""))
                   for k in (["us", "world"] if n.get("theme") == BREAKING_NAME else [rk.get(n["region"], "")]))]
    for n in news:
        by_theme.setdefault(n["theme"], []).append(n)
    etfs = {t["name"]: t.get("etfs", "") for t in THEMES}
    etfs[BREAKING_NAME] = ""
    rkey = {r["label"]: r["key"] for r in REGIONS}

    # ① 예쁜 페이지 (GitHub Pages)
    nav = "".join(f'<a href="#t{i}">{esc(name)} <b id="n{i}">{len(items)}</b></a>'
                  for i, (name, items) in enumerate(by_theme.items()))
    chips = '<button class="on" data-r="all" onclick="flt(\'all\')">전체</button>' + "".join(
        f'<button data-r="{r["key"]}" onclick="flt(\'{r["key"]}\')">{esc(r["label"])}</button>' for r in REGIONS)
    opts = '<option value="all">전체 국가</option>' + "".join(
        f'<option value="{r["key"]}">{esc(r["label"])}</option>' for r in REGIONS)
    body = []
    for i, (name, items) in enumerate(by_theme.items()):
        body.append(f'<section id="t{i}"><div class="sh"><h2>{esc(name)}</h2>'
                    f'<div class="ss"><select onchange="flt(this.value,this)">{opts}</select>'
                    f'<button class="c{"" if name == BREAKING_NAME else " on"}" onclick="srt(\'c\',this)">🔥 화제순</button>'
                    f'<button class="p{" on" if name == BREAKING_NAME else ""}" onclick="srt(\'p\',this)">🕒 최신순</button></div></div>')
        if etfs.get(name):
            body.append(f'<p class="etf">보유: {esc(etfs[name])}</p>')
        if name == BREAKING_NAME:
            body.append('<p class="etf">미국장 시간에 15분마다 확인 · 여러 언론이 동시에 보도한 큰 소식</p>')
        body.append(f'<p class="none"{"" if not items else " hidden"}>최근 {"속보" if name == BREAKING_NAME else "기사"} 없음</p>')
        body.append('<div class="list">')
        for n in items:
            new = ' <span class="new">NEW</span>' if n.get("run") == run_id and run_id != "breaking" else ""
            orig = (f'<div class="orig">{esc(n["title"])}</div>'
                    if n["show"] != n["title"] else "")
            c = n.get("count", 1)
            hot = (f'<span class="hot{" big" if c >= 5 else ""}">🔥 언론 {c}곳</span>' if c > 1 else "")
            href = n.get("url") or n["link"]
            body.append(
                f'<a class="card" data-c="{c}" data-p="{int(n["pub"])}" data-r="{rkey.get(n["region"], "")}" '
                f'href="{esc(href)}" target="_blank" rel="noopener">'
                f'<div class="meta">{hot}{esc(n["region"])} · {esc(n["source"])} · {esc(n["time"])}{new}</div>'
                f'<div class="title">{esc(n["show"])}</div>{orig}</a>')
        body.append('</div><button class="more" onclick="more(this)" hidden></button></section>')
    auto = load_sources().get("auto", {})
    lab = {r["key"]: r["label"] for r in REGIONS}
    rows = "".join(f"<div>{esc(lab.get(k, k))}: {esc(', '.join(v))}</div>" for k, v in auto.items() if v)
    auto_html = ('<footer><b>자동으로 추가된 언론사</b><br>주요 언론사들과 같은 소식을 꾸준히 함께 보도한 곳 (최근 14일 기준)'
                 + (rows or "<div>아직 없음</div>") + "</footer>")
    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#262624">
<title>투자 테마 뉴스</title>
<style>
@font-face{{font-family:'ChosunIlboMyungjo';src:url('https://cdn.jsdelivr.net/gh/projectnoonnu/noonfonts_one@1.0/Chosunilbo_myungjo.woff') format('woff');font-weight:normal;font-display:swap}}
:root{{color-scheme:dark;--bg:#262624;--card:#30302e;--card2:#3a3a37;--text:#faf9f5;--sub:#a6a39a;--line:#3e3e3a;--acc:#d97757}}
*{{box-sizing:border-box}}[hidden]{{display:none!important}}
.bar::-webkit-scrollbar,nav::-webkit-scrollbar{{display:none}}.bar,nav{{scrollbar-width:none}}
body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 'ChosunIlboMyungjo',Georgia,"Noto Serif KR",serif;-webkit-font-smoothing:antialiased}}
header{{padding:22px 16px 10px;max-width:760px;margin:auto}}
h1{{font:600 22px/1.3 'ChosunIlboMyungjo',Georgia,serif;margin:0 0 4px;letter-spacing:-.2px}}
.upd{{color:var(--sub);font-size:12.5px}}
.bar{{display:flex;gap:6px;padding:4px 16px 6px;max-width:760px;margin:auto;overflow-x:auto}}
.bar button{{flex:none;border:1px solid var(--line);background:transparent;color:var(--sub);border-radius:8px;padding:5px 12px;font:inherit;font-size:13px}}
.bar button.on,.ss button.on{{background:var(--card2);border-color:var(--card2);color:var(--text)}}
.sh{{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:6px 8px;margin:26px 4px 2px}}.sh h2{{margin:0;white-space:nowrap}}
.ss{{display:flex;gap:4px;flex:none;align-items:center}}
.ss button,.ss select{{border:1px solid var(--line);background:transparent;color:var(--sub);border-radius:7px;padding:3px 8px;font:inherit;font-size:12px}}
.ss select{{background:var(--bg);max-width:96px}}
nav{{position:sticky;top:0;z-index:1;display:flex;gap:6px;overflow-x:auto;padding:10px 16px;background:rgba(38,38,36,.94);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}}
nav a{{flex:none;padding:6px 12px;border-radius:999px;background:var(--card);color:var(--text);text-decoration:none;font-size:13px}}
nav b{{color:var(--acc);font-weight:600}}
main{{padding:4px 12px 48px;max-width:760px;margin:auto}}
section{{scroll-margin-top:56px}}
h2{{font:600 17px/1.3 'ChosunIlboMyungjo',Georgia,serif;margin:26px 4px 2px}}
.etf{{margin:0 4px 10px;color:var(--sub);font-size:12px}}
.card{{display:block;background:var(--card);border-radius:12px;padding:12px 14px;margin:8px 0;color:var(--text);text-decoration:none;transition:background .15s}}
.card:hover{{background:var(--card2)}}.card:active{{opacity:.75}}
.meta{{color:var(--sub);font-size:12px}}
.title{{font-weight:500;margin-top:3px}}
.orig{{color:var(--sub);font-size:12px;margin-top:3px}}
.new{{margin-left:4px;color:var(--acc);font-size:11px;font-weight:700;letter-spacing:.3px}}
.none{{color:var(--sub);margin:4px}}
.hot{{display:inline-block;margin-right:6px;padding:0 6px;border-radius:4px;background:rgba(217,119,87,.16);color:var(--acc);font-weight:600}}
.hot.big{{background:var(--acc);color:#1f1e1d}}
.card.f{{display:none}}.card.o{{display:none}}
.more{{display:block;width:100%;margin:4px 0 0;padding:10px;border:1px dashed var(--line);border-radius:12px;background:transparent;color:var(--sub);font:inherit;font-size:13px}}
.more:active{{opacity:.7}}
footer{{margin:36px 4px 0;padding-top:14px;border-top:1px solid var(--line);color:var(--sub);font-size:12px;line-height:1.7}}
footer b{{color:var(--text);font-weight:600}}
</style></head><body>
<header><h1>📰 투자 테마 뉴스</h1><div class="upd">업데이트 {esc(updated)} · 최근 {PAGE_DAYS}일 · 기사를 누르면 원문으로 이동<br>🔥 언론 N곳 = 같은 소식을 보도한 언론사 수 (많을수록 화제)</div></header>
<div class="bar sort"><button class="c on" onclick="srt('c')">🔥 전체 화제순</button><button class="p" onclick="srt('p')">🕒 전체 최신순</button></div>
<div class="bar region">{chips}</div>
<nav>{nav}</nav><main>{''.join(body)}{auto_html}</main>
<script>
function each(btn, fn){{
  // btn 이 있으면 그 테마만, 없으면 전체 테마
  (btn ? [btn.closest('section')] : [].slice.call(document.querySelectorAll('section'))).forEach(fn);
}}
function srt(k,btn){{
  each(btn, function(sec){{
    var l=sec.querySelector('.list'); if(!l) return;
    var a=[].slice.call(l.children);
    a.sort(function(x,y){{
      var c=(+y.dataset.c)-(+x.dataset.c), p=(+y.dataset.p)-(+x.dataset.p);
      return k==='c' ? (c||p) : (p||c);
    }});
    a.forEach(function(e){{l.appendChild(e);}});
    lim(sec);
    sec.querySelectorAll('.ss button').forEach(function(b){{b.classList.toggle('on', b.classList.contains(k));}});
  }});
  if(!btn) document.querySelectorAll('.sort button').forEach(function(b){{b.classList.toggle('on', b.classList.contains(k));}});
}}
function flt(r,sel){{
  each(sel, function(sec){{
    var shown=0;
    sec.querySelectorAll('.card').forEach(function(c){{
      var ok = r==='all' || c.dataset.r===r; c.classList.toggle('f', !ok); if(ok) shown++;
    }});
    sec.querySelector('.none').hidden = shown>0;
    sec.querySelector('select').value = r;
    var n=document.getElementById('n'+sec.id.slice(1)); if(n) n.textContent=shown;
    lim(sec);
  }});
  if(!sel) document.querySelectorAll('.region button').forEach(function(b){{b.classList.toggle('on', b.dataset.r===r);}});
}}
var LIMIT={SHOW_PER_THEME}, STEP=20;
function lim(sec){{
  // 보이는 기사 중 위에서부터 정해진 개수만 보여주고 나머지는 '더보기'
  var max = +(sec.dataset.n || LIMIT), i=0, extra=0;
  sec.querySelectorAll('.card').forEach(function(c){{
    if(c.classList.contains('f')) {{ c.classList.remove('o'); return; }}
    var over = i>=max; c.classList.toggle('o', over); if(over) extra++; i++;
  }});
  var b=sec.querySelector('.more');
  b.hidden = extra===0 && max<=LIMIT;
  b.textContent = extra>0 ? '더보기 ▾  (' + extra + '개 더)' : '접기 ▴';
}}
function more(b){{
  var sec=b.closest('section'), max=+(sec.dataset.n || LIMIT);
  if(b.textContent.indexOf('접기')===0) {{ sec.dataset.n=LIMIT; lim(sec); sec.scrollIntoView(); return; }}
  sec.dataset.n = max + STEP; lim(sec);
}}
document.querySelectorAll('section').forEach(lim);
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
            md.append(f"- {hot}[{t}]({n.get('url') or n['link']}) — {n['region']} · {n['source']} · {n['time']}{new}")
    with open(MD_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")


# ─────────────────────────────────────────────
# 🚨 미국 속보 (15분마다 따로 확인 → 큰 속보면 바로 알림)
# ─────────────────────────────────────────────
BREAKING_NAME = "🚨 미국 속보"
BREAKING_WINDOW_MIN = 90      # 최근 몇 분 안의 기사만 속보로 봄
BREAKING_MIN_SOURCES = 3      # 같은 소식을 이만큼 많은 언론이 보도하면 속보로 봄
BREAKING_MAX_ALERTS = 3       # 한 번 확인할 때 최대 몇 개까지 알림
BREAKING_WORDS = ["stock market", "Wall Street", "Fed", "Dow Jones", "Nasdaq", "S&P 500",
                  "Treasury yields", "oil prices", "tariffs", "Nvidia", "Tesla", "Apple"]
# 제목에 이런 표시가 있으면 보도 수와 상관없이 속보로 봄
BREAKING_MARK = re.compile(r"\bbreaking\b|\bjust in\b|\bflash\b|\balert:", re.I)
BREAKING_TOPIC = "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en"
BREAKING_FILE = os.path.join(HERE, "breaking.json")
US = next(r for r in REGIONS if r["key"] == "us") if any(r["key"] == "us" for r in REGIONS) else \
    {"key": "us", "label": "🇺🇸 미국", "words": "en", "hl": "en-US", "gl": "US", "ceid": "US:en"}


def load_breaking():
    try:
        with open(BREAKING_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {"items": [], "seen": {}}
    except Exception:
        return {"items": [], "seen": {}}


def check_breaking():
    data = load_breaking()
    seen = data.setdefault("seen", {})
    now = datetime.now(timezone.utc)
    since = now - timedelta(minutes=BREAKING_WINDOW_MIN)
    items = []
    for url in (BREAKING_TOPIC, search_url(US, BREAKING_WORDS, when="1h")):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            items += parse_rss(r.text)
        except Exception as e:
            print(f"  ! 속보 가져오기 실패: {e}")
    uniq = {}
    for it in items:
        k = title_key(it["title"])
        if (k and it["published"] and it["published"] >= since and not EXCLUDE.search(it["title"])
                and (is_trusted("us", it["source"], it["src_url"]) or is_trusted("world", it["source"], it["src_url"]))):
            uniq.setdefault(k + (it["source"] or ""), it)
    items = sorted(uniq.values(), key=lambda x: x["published"], reverse=True)
    groups = cluster(items)
    cands = [g for g in groups if n_sources(g) >= BREAKING_MIN_SOURCES
             or any(BREAKING_MARK.search(m["title"]) for m in g)]
    cands.sort(key=lambda g: (n_sources(g), g[0]["published"]), reverse=True)
    print(f"속보 확인: 최근 {BREAKING_WINDOW_MIN}분 기사 {len(items)}건 → 소식 {len(groups)}개 → 속보 후보 {len(cands)}개")

    recent = [x for x in data["items"] if x["pub"] >= time.time() - 12 * 3600]
    alerts = 0
    for g in cands:
        keys = list(dict.fromkeys(title_key(m["title"]) for m in g))
        if any(k in seen for k in keys) or any(same_story(g[0]["title"], x["title"]) for x in recent):
            for k in keys:
                seen[k] = time.time()
            continue
        if alerts >= BREAKING_MAX_ALERTS:
            break
        rep = next((m for m in g if BREAKING_MARK.search(m["title"])), g[0])
        cnt = n_sources(g)
        show = translate_ko(rep["title"])
        real = decode_gnews(rep["link"]) or rep["link"]
        pub = rep["published"]
        item = {"key": keys[0], "keys": keys[:60], "count": cnt, "theme": BREAKING_NAME,
                "region": US["label"], "title": rep["title"], "show": show, "source": rep["source"],
                "src_url": rep.get("src_url", ""),
                "link": rep["link"], "url": real, "pub": pub.timestamp(),
                "time": pub.astimezone(KST).strftime("%m/%d %H:%M"), "run": "breaking"}
        meta = " · ".join(x for x in [rep["source"], item["time"], f"언론 {cnt}곳" if cnt > 1 else ""] if x)
        if notify(f"🚨 미국 속보", f"{show}\n{meta}", click=real,
                  tags=["rotating_light"], priority=4):
            data["items"].append(item)
            recent.append(item)
            for k in keys:
                seen[k] = time.time()
            alerts += 1
            print(f"  🚨 {show}")
            time.sleep(1)

    cutoff = time.time() - PAGE_DAYS * 86400
    data["items"] = [x for x in data["items"] if x["pub"] >= cutoff]
    data["seen"] = {k: v for k, v in seen.items() if v >= time.time() - 2 * 86400}
    with open(BREAKING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)

    # 새 속보가 있으면 목록 페이지도 다시 만들어서 올림
    out = os.environ.get("GITHUB_OUTPUT")
    if alerts:
        build_pages(load_news(), "breaking", datetime.now(KST).strftime("%m/%d %H:%M"))
    if out:
        with open(out, "a") as f:
            f.write(f"deploy={'true' if alerts else 'false'}\n")
    print(f"속보 알림 {alerts}건")


def score_sources(region_key, raw_items, sc):
    """공동 보도 점수: 목록에 없는 언론사가 주요 언론사(2곳 이상)와 같은 소식을 얼마나 함께 보도했는지"""
    day = datetime.now(KST).strftime("%Y-%m-%d")
    bucket = sc.setdefault("days", {}).setdefault(day, {}).setdefault(region_key, {})
    for g in cluster(raw_items):
        trusted_n = len({m["source"] for m in g if is_trusted(region_key, m["source"], m["src_url"])})
        for m in g:
            if not m["source"] or is_trusted(region_key, m["source"], m["src_url"]) or is_blocked(m["source"], m["src_url"]):
                continue
            # 언론사별로 기사 하나당 한 번만 셈 (여러 번 실행돼도 중복 안 됨). 1 = 주요 언론사 2곳 이상과 공동 보도
            arts = bucket.setdefault(m["source"], {})
            k = title_key(m["title"])[:24]
            arts[k] = max(arts.get(k, 0), 1 if trusted_n >= 2 else 0)


def update_auto(sc):
    """최근 14일 점수로 자동 추가 목록 다시 만들기"""
    cutoff = (datetime.now(KST) - timedelta(days=14)).strftime("%Y-%m-%d")
    sc["days"] = {d: v for d, v in sc.get("days", {}).items() if d >= cutoff}
    total = {}
    for regs in sc["days"].values():
        for rk, srcs in regs.items():
            for src, arts in srcs.items():
                if not isinstance(arts, dict):
                    continue
                t = total.setdefault(rk, {}).setdefault(src, [0, 0])
                t[0] += len(arts)
                t[1] += sum(arts.values())
    auto = {}
    for rk, srcs in total.items():
        auto[rk] = sorted(src for src, (n, co) in srcs.items()
                          if n >= AUTO_MIN_STORIES and co >= AUTO_MIN_CO and co / n >= AUTO_MIN_RATIO)
    sc["auto"] = auto
    with open(SOURCES_FILE, "w", encoding="utf-8") as f:
        json.dump(sc, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    added = sum(len(v) for v in auto.values())
    print(f"자동 추가된 언론사: {added}곳 " + str({k: v for k, v in auto.items() if v}))


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
    sc = load_sources()     # 언론사 공동 보도 점수

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
            raw = [it for it in items
                   if not (it["published"] and it["published"] < oldest)
                   and not EXCLUDE.search(it["title"]) and title_key(it["title"])]
            raw.sort(key=lambda x: x["published"] or now, reverse=True)
            score_sources(region["key"], raw, sc)
            items = [it for it in raw if is_trusted(region["key"], it["source"], it["src_url"])]
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
                    "show": show, "source": rep["source"], "src_url": rep.get("src_url", ""), "link": rep["link"],
                    "pub": pub.timestamp(), "time": pub.astimezone(KST).strftime("%m/%d %H:%M"),
                    "run": run_id})
                taken.update(keys)
                picked += 1
            counts[name] += picked
            extra = f", 앞 지역과 겹친 소식 {merged[region['key']]}건은 합침" if merged.get(region["key"]) else ""
            print(f"  {region['label']}: 기사 {fetched.get(region['key'], 0)}건 → 소식 {len(groups)}개 → 새 소식 {picked}개{extra}")

    update_auto(sc)

    # 기록 저장
    for n in new_items:
        for k in n["keys"]:
            seen[k] = time.time()
    save_state(state)

    # 페이지용 기사 목록: 테마 순서 → 화제성 높은 순 → 최신순
    news = old_news + new_items
    add_real_urls(news)
    retranslate_failed(news)
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
    elif len(sys.argv) > 1 and sys.argv[1] == "breaking":
        check_breaking()
    else:
        collect()

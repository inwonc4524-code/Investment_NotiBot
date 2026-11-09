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
#    ja   : 일본 뉴스 검색어 (일본어)   ※ 싱가포르는 영어(en) 검색어를 씀
#    cn   : 중국 뉴스 검색어 (중국어 간체)
#    검색어는 여러 개 넣을 수 있고, 하나라도 들어간 기사를 찾습니다.
#    etfs : 이 테마와 연결된 내 ETF (알림 맨 위에 표시)
#    rel  : 관련성 검사 단어 — 기사 제목에 이 단어나 검색어가 하나도 없으면 테마와 상관없는 기사로 보고 뺌
# ─────────────────────────────────────────────
THEMES = [
    {"name": "🇺🇸 미국 S&P500",
     "etfs": "TIGER 미국S&P500",
     "kr": ["S&P500", "뉴욕증시", "미국 증시", "연준 금리"],
     "en": ["S&P 500", "Wall Street stocks", "Federal Reserve rate", "US stock market"],
     "zh": ["美股", "標普500", "聯準會", "美聯儲", "華爾街"],
     "ja": ["米国株", "S&P500", "米連邦準備制度", "FRB 利下げ", "ウォール街", "ナスダック"],
     "cn": ["美股", "标普500", "美联储", "华尔街", "纳斯达克"],
     "rel": ["S&P", "뉴욕증시", "미국 증시", "미 증시", "美증시", "美 증시", "나스닥", "다우", "연준", "월가", "stock", "stocks", "shares", "equities", "stock market", "Wall Street", "Fed", "Federal Reserve", "Nasdaq", "Dow", "Treasury yields", "bond yields", "rate cut", "rate hike", "inflation", "earnings", "美股", "標普", "道瓊", "道琼", "納斯達克", "聯準會", "美聯儲", "華爾街", "米国株", "米株", "ダウ", "FRB", "米連邦", "NY株"]},
    {"name": "🧬 나스닥 바이오",
     "etfs": "TIGER 미국나스닥바이오",
     "kr": ["나스닥 바이오", "미국 바이오주", "바이오 ETF", "FDA 승인"],
     "en": ["biotech stocks", "Nasdaq Biotechnology", "IBB ETF", "XBI", "FDA approval"],
     "zh": ["生技股", "生物科技股", "納斯達克生技", "FDA 批准"],
     "ja": ["バイオ株", "米バイオテック", "創薬ベンチャー", "FDA 承認"],
     "cn": ["生物科技股", "美国生物医药", "创新药", "FDA 批准"],
     "rel": ["바이오", "제약", "신약", "FDA", "임상", "biotech", "pharma", "pharmaceutical", "drugmaker", "drug approval", "new drug", "clinical", "gene therapy", "cell therapy", "vaccine", "XBI", "IBB", "生技", "生物科技", "醫藥", "医药", "新藥", "新药", "創新藥", "臨床", "临床", "バイオ", "創薬", "新薬", "製薬", "治験"]},
    {"name": "🔋 2차전지",
     "etfs": "TIGER 2차전지테마 · KODEX 2차전지산업 · TIGER 2차전지소재Fn",
     "kr": ["2차전지", "이차전지", "LG에너지솔루션", "에코프로비엠", "포스코퓨처엠", "양극재", "리튬 가격"],
     "en": ["EV battery", "lithium price", "battery makers", "CATL", "cathode materials"],
     "zh": ["電池股", "鋰電池", "寧德時代", "鋰價", "正極材料"],
     "ja": ["車載電池", "リチウムイオン電池", "電池メーカー", "リチウム価格", "正極材"],
     "cn": ["动力电池", "锂电池", "宁德时代", "碳酸锂 价格", "正极材料"],
     "rel": ["배터리", "2차전지", "이차전지", "양극재", "음극재", "리튬", "전해질", "분리막", "에코프로", "엘앤에프", "포스코퓨처엠", "LG에너지", "엔솔", "삼성SDI", "SK온", "전기차", "battery", "batteries", "lithium", "cathode", "anode", "EV", "CATL", "電池", "电池", "鋰", "锂", "正極", "正极", "負極", "负极", "寧德", "宁德", "比亞迪", "比亚迪", "電動車", "电动车", "リチウム", "電気自動車"]},
    {"name": "⚡ 전고체배터리·ESS",
     "etfs": "KODEX 전고체배터리ESS TOP2플러스",
     "kr": ["전고체 배터리", "전고체 전지", "ESS 배터리", "에너지저장장치", "삼성SDI 전고체"],
     "en": ["solid-state battery", "energy storage system", "ESS battery", "grid-scale storage"],
     "zh": ["固態電池", "全固態電池", "儲能", "儲能系統"],
     "ja": ["全固体電池", "蓄電池", "蓄電システム", "系統用蓄電池"],
     "cn": ["固态电池", "全固态电池", "储能", "储能系统"],
     "rel": ["전고체", "ESS", "에너지저장", "에너지 저장", "배터리", "LFP", "삼성SDI", "solid-state", "energy storage", "battery storage", "grid-scale", "battery", "batteries", "固態", "固态", "儲能", "储能", "電池", "电池", "全固体", "蓄電"]},
    {"name": "🏭 AI 전력",
     "etfs": "ACE 코리아AI전력TOP10",
     "kr": ["AI 전력", "전력기기", "변압기 수출", "HD현대일렉트릭", "효성중공업", "LS ELECTRIC", "두산에너빌리티"],
     "en": ["AI power demand", "data center power", "transformer shortage", "power grid investment"],
     "zh": ["AI 電力", "重電股", "變壓器", "資料中心 電力", "電網"],
     "ja": ["データセンター 電力", "AI 電力需要", "変圧器", "送電網", "重電株"],
     "cn": ["AI 电力", "变压器", "数据中心 电力", "电网 投资", "算力 电力"],
     "rel": ["전력망", "전력기기", "전력 수요", "전력난", "전력 인프라", "전력주", "전력 설비", "변압기", "송전", "전선", "원전", "SMR", "전력망", "배전", "초고압", "LS전선", "대한전선", "데이터센터", "현대일렉트릭", "효성중공업", "LS ELECTRIC", "LS일렉트릭", "두산에너빌리티", "산일전기", "가스터빈", "power grid", "power demand", "power supply", "power plant", "power prices", "grid", "transformer", "electricity", "data center", "data centers", "datacenter", "utility", "utilities", "nuclear", "電力", "电力", "變壓器", "变压器", "電網", "电网", "資料中心", "數據中心", "数据中心", "算力", "核電", "核电", "重電", "変圧器", "送電", "データセンター", "原発"]},
    {"name": "🤖 로봇",
     "etfs": "",
     "kr": ["로봇 관련주", "휴머노이드", "레인보우로보틱스", "두산로보틱스", "로봇 ETF", "협동로봇"],
     "en": ["humanoid robot", "robotics stocks", "Tesla Optimus", "BOTZ ETF", "Figure AI", "industrial robots"],
     "zh": ["人形機器人", "機器人概念股", "機器人股", "優必選"],
     "ja": ["ヒューマノイド", "ロボット株", "産業用ロボット", "ファナック", "安川電機"],
     "cn": ["人形机器人", "机器人概念股", "工业机器人", "优必选", "宇树科技"],
     "rel": ["로봇", "휴머노이드", "로보틱스", "자동화", "보스턴다이내믹스", "아틀라스", "옵티머스", "robot", "robotics", "humanoid", "Optimus", "automation", "Boston Dynamics", "Figure AI", "Unitree", "機器人", "机器人", "人形", "宇樹", "宇树", "優必選", "优必选", "ロボット", "ヒューマノイド", "ファナック", "安川"]},
]

# ─────────────────────────────────────────────
# 2) 어느 지역 뉴스를 볼지
#    필요 없는 지역은 줄 앞에 # 을 붙이면 꺼집니다.
# ─────────────────────────────────────────────
REGIONS = [   # 이 순서대로 국가 버튼이 보여요
    {"key": "kr", "label": "🇰🇷 한국", "words": "kr", "hl": "ko", "gl": "KR", "ceid": "KR:ko"},
    {"key": "us", "label": "🇺🇸 미국", "words": "en", "hl": "en-US", "gl": "US", "ceid": "US:en"},
    {"key": "cn", "label": "🇨🇳 중국", "words": "cn", "hl": "zh-CN", "gl": "CN", "ceid": "CN:zh-Hans"},
    {"key": "tw", "label": "🇹🇼 대만", "words": "zh", "hl": "zh-TW", "gl": "TW", "ceid": "TW:zh-Hant"},
    {"key": "hk", "label": "🇭🇰 홍콩", "words": "zh", "hl": "zh-HK", "gl": "HK", "ceid": "HK:zh-Hant"},
    {"key": "jp", "label": "🇯🇵 일본", "words": "ja", "hl": "ja", "gl": "JP", "ceid": "JP:ja"},
    {"key": "sg", "label": "🇸🇬 싱가포르", "words": "en", "hl": "en-SG", "gl": "SG", "ceid": "SG:en"},
    {"key": "world", "label": "🌍 세계", "words": "en", "hl": "en-GB", "gl": "GB", "ceid": "GB:en"},
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
THEME_KEEP = 80           # 테마마다 페이지에 남길 최대 기사 수 (최근 24시간 기사는 모두 남김)
# 제목이 이만큼 비슷하면 같은 소식으로 묶음 (0~1, 낮을수록 더 많이 묶음)
SIMILAR = 0.3

# 이런 단어가 제목에 있으면 제외 (광고성·무관한 기사 걸러내기)
EXCLUDE = re.compile(r"리딩방|무료\s*추천|급등주\s*추천|카톡방|sponsored|press release"
                     r"|\b(?:call|put)\s*\([A-Z0-9]+\)"                 # 옵션 시세 페이지 (예: XBI Jun 2027 153.000 put (XBI…))
                     r"|\b\d+\.\d{3}\s+(?:call|put)\b"
                     r"|stock price,? news,? quote|quote & history|historical prices"
                     r"|^【[^】]*株式会社[^】]*】"                          # 일본 기업 보도자료 형식
                     r"|年収\s*[0-9,]+万|【原則|◆大手", re.I)                  # 구인 공고

# ─────────────────────────────────────────────
# 믿을 만한 언론사만 (나라별)
#   - 점(.)이 들어간 건 사이트 주소, 아니면 언론사 이름
#   - 목록에 없는 곳의 기사는 가져오지 않습니다. 추가·삭제는 여기서.
# ─────────────────────────────────────────────
TRUSTED = {
    "kr": [
        "연합뉴스", "yna.co.kr", "연합뉴스TV", "yonhapnewstv.co.kr", "연합인포맥스", "einfomax.co.kr",
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
    "cn": [
        "财新", "Caixin", "caixin.com", "第一财经", "yicai.com", "证券时报", "stcn.com", "中国证券报", "cs.com.cn",
        "上海证券报", "cnstock.com", "21世纪经济报道", "21jingji.com", "经济观察", "eeo.com.cn",
        "界面新闻", "jiemian.com", "澎湃新闻", "thepaper.cn", "每日经济新闻", "nbd.com.cn", "财联社", "cls.cn",
        "新华社", "新华网", "xinhuanet.com", "news.cn", "人民日报", "人民网", "people.com.cn", "央视", "cctv.com",
        "中国新闻网", "chinanews.com.cn", "36氪", "36kr.com",
    ],
    "jp": [
        "日本経済新聞", "日経", "nikkei.com", "NHK", "nhk.or.jp", "共同通信", "kyodonews.jp", "時事通信", "時事ドットコム", "jiji.com",
        "朝日新聞", "asahi.com", "読売新聞", "yomiuri.co.jp", "毎日新聞", "mainichi.jp", "産経新聞", "産経ニュース", "sankei.com",
        "東洋経済", "toyokeizai.net", "ダイヤモンド", "diamond.jp", "日刊工業新聞", "nikkan.co.jp", "テレ東", "tv-tokyo.co.jp",
        "ロイター", "jp.reuters.com", "ブルームバーグ", "bloomberg.co.jp", "ウォール・ストリート・ジャーナル", "jp.wsj.com",
        "ITmedia", "itmedia.co.jp", "株探", "kabutan.jp", "QUICK", "Nikkei Asia", "asia.nikkei.com", "Japan Times", "japantimes.co.jp",
    ],
    "sg": [
        "The Straits Times", "straitstimes.com", "The Business Times", "businesstimes.com.sg",
        "CNA", "channelnewsasia.com", "The Edge Singapore", "theedgesingapore.com", "TODAY", "todayonline.com",
        "Reuters", "reuters.com", "Bloomberg", "bloomberg.com", "Nikkei Asia", "asia.nikkei.com",
        "South China Morning Post", "scmp.com", "CNBC", "cnbc.com", "Financial Times", "ft.com",
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
    "證券", "증권", "securities", "期貨", "投信",          # 증권사 자체 콘텐츠는 언론 보도가 아니라서 제외
    "転職", "career.nikkei", "求人", "채용",                # 구인 공고
]
# 자동 추가 기준: 최근 14일 동안
AUTO_MIN_STORIES = 10      # 이 언론사가 보도한 소식이 10개 이상이고
AUTO_MIN_CO = 6            # 그중 주요 언론사 2곳 이상도 함께 보도한 소식이 6개 이상이며
AUTO_MIN_RATIO = 0.5       # 그 비율이 절반 이상이고
AUTO_MIN_FIRST = 3         # 주요 언론사보다 먼저 보도한 소식이 3개 이상이면 → 믿을 만한 곳으로 자동 추가
                           # (남의 기사를 받아 쓰기만 하는 곳은 먼저 보도하는 일이 거의 없어서 걸러짐)
SOURCES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources.json")


def load_sources():
    try:
        with open(SOURCES_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


_AUTO = load_sources().get("auto", {})


# 언론사 사이트 안의 보도자료 코너 등 (원문 주소로 확인)
PR_URL = re.compile(r"[?&]g=prt\b|prtimes\.|prnewswire|businesswire|globenewswire|newswire\.|/press-?release", re.I)


def is_pr(url):
    return bool(url and PR_URL.search(url))


def is_blocked(source, url=""):
    s = (source or "").lower() + " " + _domain(url)
    return any(b in s for b in BLOCKED)


def is_trusted(region_key, source, url=""):
    names = TRUSTED.get(region_key)
    if names is None:      # 목록이 없는 지역은 거르지 않음
        return True
    if re.search(r"転職|求人|career\.|jobs\.|채용", (source or "") + " " + (url or "")):   # 구인 사이트
        return False
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


_translate_fail = {"n": 0}     # 연속 실패 수 — 번역 서버가 막혔을 때 계속 붙잡고 있지 않게


def translate_ko(text, tries=3):
    if not TRANSLATE_EN or not text or re.search(r"[가-힣]", text):
        return text
    if text in _translate_cache:
        return _translate_cache[text]
    if _translate_fail["n"] >= 6:  # 연속 6번 실패하면 이번 실행에서는 번역을 쉬고 다음 실행 때 다시 시도
        return text
    result = text
    api_ok = False                # 번역 서버가 응답했는지 (번역 결과가 원문과 같아도 성공)
    for attempt in range(tries):
        try:
            r = requests.get("https://translate.googleapis.com/translate_a/single",
                             params={"client": "gtx", "sl": "auto", "tl": "ko", "dt": "t", "q": text},
                             headers=HEADERS, timeout=15)
            r.raise_for_status()
            out = "".join(seg[0] for seg in r.json()[0] if seg and seg[0]).strip()
            if out:
                result = out
                api_ok = True
                break
        except Exception as e:
            print(f"  ! 번역 실패 ({attempt + 1}/{tries}): {e}")
        time.sleep(2 + attempt * 3)   # 2초 → 5초 쉬고 다시 시도
    if api_ok:                        # 실패한 건 기억하지 않음 → 다음 실행 때 다시 시도
        _translate_cache[text] = result
        _translate_fail["n"] = 0
    else:
        _translate_fail["n"] += 1
        if _translate_fail["n"] == 6:
            print("  ! 번역 서버가 계속 실패해서 이번 실행에서는 번역을 멈춥니다 (다음 실행 때 자동으로 다시 번역)")
    time.sleep(0.2)
    return result


def retranslate_failed(items, limit=40):
    """예전에 번역에 실패해서 원문 그대로 남은 제목을 다시 번역"""
    done = fixed = 0
    for n in items:
        if done >= limit:
            break
        if not is_korean(n["title"]) and n.get("show") == n["title"] and not n.get("tr_same"):
            done += 1
            ko = translate_ko(n["title"])
            if ko != n["title"]:
                n["show"] = ko
                fixed += 1
            elif n["title"] in _translate_cache:   # 번역은 됐는데 원문과 같음 (예: 회사 이름) → 다시 안 함
                n["tr_same"] = True
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
    """기사에 실제 언론사 주소(url) 붙이기 — 요약 가져오기 + 누르면 원문으로 바로 이동"""
    done = ok = 0
    for n in items:
        if n.get("url") or n.get("url_tried", 0) >= 2 or done >= limit:
            continue
        done += 1
        u = decode_gnews(n["link"])
        if u:
            n["url"] = u
            ok += 1
        else:
            n["url_tried"] = n.get("url_tried", 0) + 1
        time.sleep(0.25)
    if done:
        print(f"기사 원문 주소 찾기: {ok}/{done}건 성공")


# ─────────────────────────────────────────────
# 기사 요약 (누르면 먼저 한국어 요약 → 원문 볼지 선택)
#   언론사가 직접 쓴 기사 소개 문구(og:description) → 짧으면 본문 앞부분
#   외국어는 한국어로 번역
# ─────────────────────────────────────────────
import html as _html
from concurrent.futures import ThreadPoolExecutor

SUMMARY_MAX = 400          # 요약 최대 글자 수
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def _meta(page, *names):
    for nm in names:
        for pat in (rf'<meta[^>]+(?:property|name)=["\']{nm}["\'][^>]*content=["\']([^"\']+)["\']',
                    rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']{nm}["\']'):
            m = re.search(pat, page, re.I)
            if m:
                return _html.unescape(m.group(1)).strip()
    return ""


def _lead_text(page):
    """본문 앞부분 2~3문장 (trafilatura 가 있으면 사용)"""
    try:
        import trafilatura
        text = trafilatura.extract(page, include_comments=False, include_tables=False) or ""
    except Exception:
        paras = re.findall(r"<p[^>]*>(.*?)</p>", page, re.S | re.I)
        text = " ".join(re.sub(r"<[^>]+>", "", _html.unescape(p)) for p in paras[:6])
    text = re.sub(r"\s+", " ", text).strip()
    out = ""
    for sent in re.split(r"(?<=[.!?。！？다])\s+", text):
        if len(out) + len(sent) > SUMMARY_MAX:
            break
        out += (" " if out else "") + sent
        if len(out) > 220:
            break
    return out


def fetch_summary(url):
    if not url or "news.google.com" in url:
        return ""
    try:
        r = requests.get(url, headers={"User-Agent": BROWSER_UA, "Accept-Language": "ko,en;q=0.8,zh;q=0.6"},
                         timeout=12)
        if r.status_code >= 400:
            return ""
        if not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding
        page = r.text[:1_500_000]
    except Exception:
        return ""
    desc = _meta(page, "og:description", "twitter:description", "description")
    desc = re.sub(r"\s+", " ", desc).strip()
    if len(desc) < 60:
        lead = _lead_text(page)
        if len(lead) > len(desc):
            desc = lead
    return desc[:SUMMARY_MAX]


def add_summaries(items, limit=120):
    """요약이 없는 기사에 한국어 요약 붙이기 (여러 개 동시에 가져옴)"""
    todo = [n for n in items if not n.get("sum") and n.get("sum_tried", 0) < 2 and n.get("url")][:limit]
    if not todo:
        return
    with ThreadPoolExecutor(max_workers=8) as ex:
        raw = list(ex.map(lambda n: fetch_summary(n["url"]), todo))
    # 같은 언론사의 여러 기사에 똑같은 문구가 붙으면 사이트 기본 소개문이라 버림
    dup = {}
    for n, d in zip(todo, raw):
        if d:
            dup.setdefault((n["source"], d), 0)
            dup[(n["source"], d)] += 1
    ok = 0
    for n, d in zip(todo, raw):
        if (d and dup[(n["source"], d)] == 1 and title_key(d) != title_key(n["title"])
                and len(d) >= 30 and not re.search(r"https?://", d)):
            n["sum"] = translate_ko(d)
            ok += 1
        else:
            n["sum_tried"] = n.get("sum_tried", 0) + 1
    print(f"기사 요약: {ok}/{len(todo)}건 성공")


# ─────────────────────────────────────────────
# 기록 (중복 방지)
# ─────────────────────────────────────────────
_REL_CACHE = {}


def _rel_terms(theme):
    name = theme["name"]
    if name not in _REL_CACHE:
        terms = set()
        for key in ("kr", "en", "zh", "ja", "cn", "rel"):
            for w in theme.get(key, []):
                terms.add(w.lower())              # 검색어 전체 그대로 (쪼개면 "AI" 같은 흔한 단어까지 통과해서)
        _REL_CACHE[name] = sorted(terms)
    return _REL_CACHE[name]


def is_relevant(theme, title):
    """기사 제목에 테마 관련 단어가 있는지 (영어는 단어 단위로, 한·중·일은 글자 포함으로 확인)"""
    t = (title or "").lower()
    for w in _rel_terms(theme):
        if re.fullmatch(r"[a-z0-9&.\- ]+", w):     # 영어·숫자: 단어 단위 (예: "dow" ≠ "down")
            if re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", t):
                return True
        elif w in t:
            return True
    return False


def title_key(title):
    return re.sub(r"[^0-9a-z가-힣\u3040-\u30ff\u4e00-\u9fff\u3400-\u4dbf]", "", title.lower())[:80]


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
    return {_stem(w) for w in re.findall(r"[a-z0-9'가-힣\u3040-\u30ff\u4e00-\u9fff]+", title.lower())
            if w not in _STOP and len(w) > 1}


def _bigrams(title):
    s = re.sub(r"[^0-9a-z가-힣\u3040-\u30ff\u4e00-\u9fff\u3400-\u4dbf]", "", title.lower())
    return {s[i:i + 2] for i in range(len(s) - 1)}


_CJK = re.compile(r"[가-힣\u3040-\u30ff\u4e00-\u9fff]")


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


def _added(n):
    """기사가 봇에 들어온 시각 (레드닷·NEW 표시용)"""
    if n.get("added"):
        return int(n["added"])
    r = n.get("run", "")
    if r.isdigit() and len(r) == 12:
        try:
            return int(datetime.strptime(r, "%Y%m%d%H%M").replace(tzinfo=timezone.utc).timestamp())
        except Exception:
            pass
    return int(n.get("pub", 0))


def _pack(n, rkey):
    """페이지에 넣을 기사 정보 (짧은 이름으로 줄여서 페이지를 가볍게)"""
    d = {"s": n["show"], "so": n.get("source", ""), "tm": n.get("time", ""), "c": n.get("count", 1),
         "r": n.get("rk") or rkey.get(n["region"], "us"), "u": n.get("url") or n["link"], "p": int(n["pub"]), "a": _added(n)}
    if n["show"] != n["title"]:
        d["t"] = n["title"]
    if n.get("sum"):
        d["su"] = n["sum"]
    return d


def build_pages(news, run_id, updated):
    by_theme = {BREAKING_NAME: [], GLOBAL_BREAKING_NAME: []}
    by_theme.update({t["name"]: [] for t in THEMES})
    brk = sorted(load_breaking().get("items", []), key=lambda n: -n["pub"])
    rk = {r["label"]: r["key"] for r in REGIONS}
    news = [n for n in brk + list(news)
            if any(is_trusted(k, n.get("source", ""), n.get("src_url") or n.get("url", ""))
                   for k in (["us", "world"] if n.get("theme") == BREAKING_NAME else [rk.get(n["region"], "")]))]
    brk_names = (BREAKING_NAME, GLOBAL_BREAKING_NAME)
    for n in news:
        by_theme.setdefault(n["theme"], []).append(n)
    etfs = {t["name"]: t.get("etfs", "") for t in THEMES}
    etfs[BREAKING_NAME] = etfs[GLOBAL_BREAKING_NAME] = ""
    rkey = {r["label"]: r["key"] for r in REGIONS}

    # ① 예쁜 페이지 (GitHub Pages) — 탭을 눌러야 그 테마 뉴스가 보이고, 새 뉴스가 있으면 탭에 레드닷
    data = {
        "updated": updated,
        "regions": [{"k": r["key"], "l": r["label"]} for r in REGIONS],
        "themes": [{"name": name,
                    "note": ("평일 12분마다 확인 · 여러 언론이 동시에 보도한 큰 소식 · 휴대폰 알림"
                             if name == BREAKING_NAME else
                             "한국·중국·대만·홍콩·일본·싱가포르·세계 · 여러 언론이 동시에 보도했거나 언론사가 속보로 표시한 소식"
                             if name == GLOBAL_BREAKING_NAME else (f"보유: {etfs[name]}" if etfs.get(name) else "")),
                    "breaking": name in brk_names,
                    "items": [_pack(n, rkey) for n in items]}
                   for name, items in by_theme.items()],
        "auto": {r["label"]: v for r in REGIONS for k, v in load_sources().get("auto", {}).items()
                 if k == r["key"] and v},
        "breaking_url": f"https://raw.githubusercontent.com/{REPO}/main/breaking.json",
        "show": SHOW_PER_THEME,
    }
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#262624">
<title>투자 테마 뉴스</title>
<style>
@font-face{font-family:'ChosunIlboMyungjo';src:url('https://cdn.jsdelivr.net/gh/projectnoonnu/noonfonts_one@1.0/Chosunilbo_myungjo.woff') format('woff');font-weight:normal;font-display:swap}
:root{color-scheme:dark;--bg:#262624;--card:#30302e;--card2:#3a3a37;--text:#faf9f5;--sub:#a6a39a;--line:#3e3e3a;--acc:#d97757;--red:#ef4444}
*{box-sizing:border-box}[hidden]{display:none!important}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 'ChosunIlboMyungjo',Georgia,"Noto Serif KR",serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:760px;margin:auto}
header{padding:20px 16px 8px}
h1{font:600 22px/1.3 'ChosunIlboMyungjo',Georgia,serif;margin:0 0 4px}
.upd{color:var(--sub);font-size:12.5px}
/* 테마 탭 */
.tabs{position:sticky;top:0;z-index:3;background:rgba(38,38,36,.96);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.tabrow{display:flex;gap:8px;overflow-x:auto;padding:12px 16px 10px;scrollbar-width:none}.tabrow::-webkit-scrollbar{display:none}
.tab{position:relative;flex:none;padding:9px 15px;border-radius:12px;border:1px solid var(--line);background:var(--card);
  color:var(--sub);font:inherit;font-size:14px;cursor:pointer}
.tab b{margin-left:5px;color:var(--sub);font-weight:400;font-size:12px}
.tab.on{background:var(--acc);border-color:var(--acc);color:#1f1e1d;font-weight:600}.tab.on b{color:#1f1e1d}
.dot{position:absolute;top:-3px;right:-3px;width:11px;height:11px;border-radius:50%;background:var(--red);border:2px solid var(--bg)}
/* 정렬·국가 */
.ctrl{display:flex;gap:6px;overflow-x:auto;padding:0 16px 10px;scrollbar-width:none}.ctrl::-webkit-scrollbar{display:none}
.ctrl button{flex:none;border:1px solid var(--line);background:transparent;color:var(--sub);border-radius:8px;padding:5px 11px;font:inherit;font-size:12.5px}
.ctrl button.on{background:var(--card2);border-color:var(--card2);color:var(--text)}
.ctrl .sep{flex:none;width:1px;background:var(--line);margin:2px 4px}
main{padding:6px 12px 48px}
h2{font:600 19px/1.3 'ChosunIlboMyungjo',Georgia,serif;margin:16px 4px 2px}
.note{margin:0 4px 10px;color:var(--sub);font-size:12px}
.none{color:var(--sub);margin:24px 4px;text-align:center}
.card{display:block;background:var(--card);border-radius:12px;padding:12px 14px;margin:8px 0;color:var(--text);text-decoration:none;transition:background .15s}
.card:hover{background:var(--card2)}.card:active{opacity:.75}
.meta{color:var(--sub);font-size:12px}
.title{font-weight:500;margin-top:3px}
.orig{color:var(--sub);font-size:12px;margin-top:3px}
.new{margin-left:4px;color:var(--red);font-size:11px;font-weight:700;letter-spacing:.3px}
.hot{display:inline-block;margin-right:6px;padding:0 6px;border-radius:4px;background:rgba(217,119,87,.16);color:var(--acc);font-weight:600}
.hot.big{background:var(--acc);color:#1f1e1d}
.newbar{display:block;width:100%;margin:2px 0 6px;padding:9px;border:0;border-radius:10px;background:rgba(239,68,68,.14);color:#fca5a5;font:inherit;font-size:13px;text-align:left}
.more{display:block;width:100%;margin:4px 0 0;padding:10px;border:1px dashed var(--line);border-radius:12px;background:transparent;color:var(--sub);font:inherit;font-size:13px}
footer{margin:36px 4px 0;padding-top:14px;border-top:1px solid var(--line);color:var(--sub);font-size:12px;line-height:1.7}
footer b{color:var(--text);font-weight:600}
/* 요약 창 */
#dim{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:5}
#sheet{position:fixed;left:0;right:0;bottom:0;z-index:6;max-width:760px;margin:auto;max-height:82vh;overflow-y:auto;
  background:var(--card);border-radius:16px 16px 0 0;padding:10px 18px calc(18px + env(safe-area-inset-bottom));box-shadow:0 -8px 30px rgba(0,0,0,.4)}
.grab{width:38px;height:4px;border-radius:2px;background:var(--line);margin:0 auto 12px}
.s-title{font-size:17px;font-weight:600;margin:4px 0 2px;line-height:1.45}
.s-label{margin:16px 0 4px;color:var(--acc);font-size:12px;font-weight:700;letter-spacing:.5px}
.s-sum{font-size:15px;line-height:1.75}.s-sum.empty{color:var(--sub);font-size:13.5px}
.s-btns{display:flex;gap:8px;margin-top:20px}
.s-btns button,.s-btns a{flex:1;text-align:center;padding:12px;border-radius:10px;font:inherit;font-size:14.5px;text-decoration:none}
.s-btns button{background:transparent;border:1px solid var(--line);color:var(--sub)}
.s-btns a{background:var(--acc);color:#1f1e1d;font-weight:600}
</style></head><body>
<div class="wrap">
<header><h1>📰 투자 테마 뉴스</h1><div class="upd" id="upd"></div></header>
</div>
<div class="tabs"><div class="wrap">
  <div class="tabrow" id="tabs"></div>
  <div class="ctrl" id="ctrl"></div>
</div></div>
<div class="wrap"><main id="main"></main></div>
<div id="dim" onclick="closeSheet()" hidden></div>
<div id="sheet" role="dialog" aria-modal="true" hidden>
  <div class="grab"></div>
  <div id="s-meta" class="meta"></div>
  <div id="s-title" class="s-title"></div>
  <div id="s-orig" class="orig"></div>
  <div class="s-label">요약</div>
  <div id="s-sum" class="s-sum"></div>
  <div class="s-btns"><button onclick="closeSheet()">닫기</button><a id="s-go" target="_blank" rel="noopener" onclick="closeSheet()">원문 보기 ↗</a></div>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
var D = JSON.parse(document.getElementById('data').textContent);
var RL = {}; D.regions.forEach(function(r){ RL[r.k] = r.l; });
function $(id){ return document.getElementById(id); }
function esc(t){ return String(t==null?'':t).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
// 휴대폰에 기억해 두는 값 (마지막 탭, 탭별로 마지막에 본 시각, 정렬, 국가)
function load(k, d){ try { var v = localStorage.getItem('nb_'+k); return v===null ? d : JSON.parse(v); } catch(e){ return d; } }
function save(k, v){ try { localStorage.setItem('nb_'+k, JSON.stringify(v)); } catch(e){} }
var S = { tab: 0, seen: load('seen', null), sort: load('sort', 'c'), region: load('region', 'all'), shown: D.show, prev: {} };
function newest(t){ var m = 0; t.items.forEach(function(n){ if(n.a > m) m = n.a; }); return m; }
if(S.seen === null){ S.seen = {}; D.themes.forEach(function(t){ S.seen[t.name] = newest(t); }); save('seen', S.seen); }  // 처음 방문: 레드닷 없이 시작
(function(){ var nm = load('tabname', ''); D.themes.forEach(function(t, i){ if(t.name === nm) S.tab = i; }); })();  // 마지막에 본 탭 (이름으로 기억)
if(location.hash && /^#t\\d+$/.test(location.hash)) S.tab = +location.hash.slice(2);
if(S.tab >= D.themes.length) S.tab = 0;

function visible(t){
  return t.items.filter(function(n){ return S.region==='all' || n.r===S.region; });
}
function sorted(list, breaking){
  var k = breaking ? 'p' : S.sort;
  return list.slice().sort(function(x,y){
    var c = y.c - x.c, p = y.p - x.p; return k==='c' ? (c||p) : (p||c);
  });
}
function renderTabs(){
  $('tabs').innerHTML = D.themes.map(function(t, i){
    var dot = newest(t) > (S.seen[t.name] || 0) && i !== S.tab;
    return '<button class="tab'+(i===S.tab?' on':'')+'" onclick="openTab('+i+')">'+esc(t.name)+
           '<b>'+visible(t).length+'</b>'+(dot?'<span class="dot" title="새 뉴스"></span>':'')+'</button>';
  }).join('');
  var on = $('tabs').children[S.tab]; if(on && on.scrollIntoView) on.scrollIntoView({block:'nearest', inline:'center'});
}
function renderCtrl(){
  var br = D.themes[S.tab].breaking;
  var h = '';
  if(!br){
    h += '<button class="'+(S.sort==='c'?'on':'')+'" onclick="setSort(\\'c\\')">🔥 화제순</button>';
    h += '<button class="'+(S.sort==='p'?'on':'')+'" onclick="setSort(\\'p\\')">🕒 최신순</button><span class="sep"></span>';
  }
  h += '<button class="'+(S.region==='all'?'on':'')+'" onclick="setRegion(\\'all\\')">전체</button>';
  D.regions.forEach(function(r){
    h += '<button class="'+(S.region===r.k?'on':'')+'" onclick="setRegion(\\''+r.k+'\\')">'+esc(r.l)+'</button>';
  });
  $('ctrl').innerHTML = h;
}
function card(n, prev){
  var hot = n.c > 1 ? '<span class="hot'+(n.c>=5?' big':'')+'">🔥 언론 '+n.c+'곳</span>' : '';
  var isNew = prev && n.a > prev ? ' <span class="new">NEW</span>' : '';
  return '<a class="card" href="'+esc(n.u)+'" target="_blank" rel="noopener" data-s="'+esc(n.su||'')+'">'+
    '<div class="meta">'+hot+esc(RL[n.r]||'')+' · '+esc(n.so)+' · '+esc(n.tm)+isNew+'</div>'+
    '<div class="title">'+esc(n.s)+'</div>'+(n.t?'<div class="orig">'+esc(n.t)+'</div>':'')+'</a>';
}
function renderMain(){
  var t = D.themes[S.tab], list = sorted(visible(t), t.breaking), prev = S.prev[t.name] || 0;
  var h = '<h2>'+esc(t.name)+'</h2>' + (t.note ? '<p class="note">'+esc(t.note)+'</p>' : '');
  var fresh = prev ? list.filter(function(n){ return n.a > prev; }).length : 0;
  if(S.onlyNew){                                // '새 기사만 보기' 중
    list = list.filter(function(n){ return n.a > prev; });
    h += '<button class="newbar" onclick="onlyNew(false)">🆕 새 기사 '+list.length+'개만 보는 중 · 전체 보기</button>';
  } else if(fresh && !t.breaking){              // 새 기사가 정렬 때문에 아래로 밀려도 바로 찾을 수 있게
    h += '<button class="newbar" onclick="onlyNew(true)">🆕 새 기사 '+fresh+'개 · 새 기사만 보기</button>';
  }
  if(!list.length) h += '<p class="none">'+(S.region==='all' ? '최근 ' + (t.breaking?'속보':'기사') + ' 없음' : esc(RL[S.region])+' 기사 없음')+'</p>';
  h += list.slice(0, S.shown).map(function(n){ return card(n, prev); }).join('');
  var extra = list.length - S.shown;
  if(extra > 0) h += '<button class="more" onclick="more()">더보기 ▾  ('+extra+'개 더)</button>';
  else if(S.shown > D.show) h += '<button class="more" onclick="less()">접기 ▴</button>';
  var auto = Object.keys(D.auto);
  h += '<footer>업데이트 '+esc(D.updated)+' · 최근 3일 · 믿을 만한 언론사 기사만 · 기사를 누르면 한국어 요약 → 원문 보기<br>'+
       '🔥 언론 N곳 = 같은 소식을 보도한 언론사 수 (많을수록 화제) · <span style="color:var(--red)">●</span> = 새 뉴스'+
       '<br><br><b>자동으로 추가된 언론사</b> (주요 언론보다 먼저 보도하고, 주요 언론도 함께 다룬 소식이 많은 곳 · 최근 14일)'+
       (auto.length ? auto.map(function(k){ return '<div>'+esc(k)+': '+esc(D.auto[k].join(', '))+'</div>'; }).join('') : '<div>아직 없음</div>')+
       '</footer>';
  $('main').innerHTML = h;
}
function openTab(i){
  var t = D.themes[i];
  S.tab = i; S.shown = D.show; S.onlyNew = false; save('tabname', t.name);
  if(!(t.name in S.prev)) S.prev[t.name] = S.seen[t.name] || 0;     // 이 탭에서 NEW 로 보여줄 기준
  S.seen[t.name] = Math.max(S.seen[t.name] || 0, newest(t)); save('seen', S.seen);  // 탭에 들어오면 레드닷 지움
  history.replaceState(null, '', '#t'+i);
  renderTabs(); renderCtrl(); renderMain(); window.scrollTo(0, 0);
}
function setSort(k){ S.sort = k; save('sort', k); S.shown = D.show; renderCtrl(); renderMain(); }
function setRegion(k){ S.region = k; save('region', k); S.shown = D.show; renderTabs(); renderCtrl(); renderMain(); }
function more(){ S.shown += 20; renderMain(); }
function onlyNew(on){ S.onlyNew = on; S.shown = D.show; renderMain(); }
function less(){ S.shown = D.show; renderMain(); window.scrollTo(0, 0); }
$('upd').textContent = '업데이트 ' + D.updated + ' · 탭을 눌러 테마별 뉴스 보기';

// 🚨 미국 속보 · 🌏 해외 속보는 페이지를 새로 올리지 않아도 최신 내용을 바로 가져옴
function refreshBreaking(){
  if(!window.fetch) return;
  fetch(D.breaking_url + '?t=' + Date.now(), {cache:'no-store'}).then(function(r){ return r.json(); }).then(function(b){
    var all = b.items || [];
    D.themes.forEach(function(t, i){
      if(!t.breaking) return;
      var items = all.filter(function(n){ return n.theme === t.name; }).map(function(n){
        var d = {s:n.show, so:n.source||'', tm:n.time||'', c:n.count||1, r:n.rk||'us', u:n.url||n.link, p:Math.floor(n.pub), a:Math.floor(n.added||n.pub)};
        if(n.show !== n.title) d.t = n.title; if(n.sum) d.su = n.sum; return d;
      });
      if(!items.length && t.items.length) return;
      t.items = items;
      if(S.tab === i){ S.seen[t.name] = Math.max(S.seen[t.name]||0, newest(t)); save('seen', S.seen); renderMain(); }
    });
    renderTabs();
  }).catch(function(){});
}
openTab(S.tab);
refreshBreaking();
setInterval(refreshBreaking, 5 * 60 * 1000);
document.addEventListener('visibilitychange', function(){ if(!document.hidden) refreshBreaking(); });

// 기사를 누르면 먼저 한국어 요약 → 원문 볼지 선택
document.addEventListener('click', function(e){
  var c = e.target.closest('a.card'); if(!c) return;
  if(e.ctrlKey||e.metaKey||e.shiftKey) return;
  e.preventDefault();
  $('s-meta').innerHTML = c.querySelector('.meta').innerHTML;
  $('s-title').textContent = c.querySelector('.title').textContent;
  var o = c.querySelector('.orig'); $('s-orig').textContent = o ? o.textContent : '';
  var sm = c.dataset.s || '';
  $('s-sum').textContent = sm || '이 기사는 요약을 가져오지 못했어요. (사이트가 자동 접속을 막았거나 아직 준비 중)';
  $('s-sum').className = 's-sum' + (sm ? '' : ' empty');
  $('s-go').href = c.href;
  $('dim').hidden = false; $('sheet').hidden = false; $('sheet').scrollTop = 0;
  document.body.style.overflow = 'hidden';
});
function closeSheet(){ $('dim').hidden = true; $('sheet').hidden = true; document.body.style.overflow = ''; }
document.addEventListener('keydown', function(e){ if(e.key==='Escape') closeSheet(); });
</script></body></html>""".replace("__DATA__", blob)
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
# 🚨 미국 속보 (12분마다 따로 확인 → 큰 속보면 바로 알림)
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


# ── 🌏 해외 속보 (한국·중국·대만·홍콩·일본·싱가포르·세계) ──
GLOBAL_BREAKING_NAME = "🌏 해외 속보"
GLOBAL_BREAKING_PUSH = False   # True 로 바꾸면 해외 속보도 휴대폰 알림 (기본은 탭에만 쌓임)
GLOBAL_BREAKING_MAX = 3        # 한 번 확인할 때 지역마다 최대 몇 개까지
# 지역별 시장 검색어
GLOBAL_BREAKING_WORDS = {
    "kr": ["코스피", "코스닥", "증시", "환율", "한국은행", "반도체"],
    "cn": ["A股", "股市", "人民币", "央行", "沪指"],
    "tw": ["台股", "加權指數", "台積電", "央行", "新台幣"],
    "hk": ["港股", "恒指", "恒生指數", "港元"],
    "jp": ["日経平均", "株式市場", "日銀", "円相場", "東証"],
    "sg": ["Singapore stocks", "STI", "MAS", "Singapore dollar", "SGX"],
    "world": ["global markets", "European stocks", "ECB", "oil prices", "China economy"],
}
# 언론사가 제목에 직접 속보라고 단 경우 (나라별 표기)
GLOBAL_BREAKING_MARK = re.compile(r"\[속보\]|【速報】|速報|快訊|快讯|突發|突发|即時|\bbreaking\b|\bjust in\b", re.I)


def _topic_url(region):
    return (f"https://news.google.com/rss/headlines/section/topic/BUSINESS"
            f"?hl={region['hl']}&gl={region['gl']}&ceid={region['ceid']}")


def _breaking_round(data, seen, region, words, theme, mark, min_src, max_new, push):
    """한 지역의 최근 90분 기사에서 속보를 골라 data 에 추가. 새로 추가한 개수를 돌려줌"""
    now = datetime.now(timezone.utc)
    since = now - timedelta(minutes=BREAKING_WINDOW_MIN)
    trust_keys = ["us", "world"] if region["key"] == "us" else [region["key"]]
    items = []
    for url in (_topic_url(region), search_url(region, words, when="1h")):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            items += parse_rss(r.text)
        except Exception as e:
            print(f"  ! {region['label']} 속보 가져오기 실패: {e}")
    uniq = {}
    for it in items:
        k = title_key(it["title"])
        if (k and it["published"] and it["published"] >= since and not EXCLUDE.search(it["title"])
                and any(is_trusted(t, it["source"], it["src_url"]) for t in trust_keys)):
            uniq.setdefault(k + (it["source"] or ""), it)
    items = sorted(uniq.values(), key=lambda x: x["published"], reverse=True)
    groups = cluster(items)
    cands = [g for g in groups if n_sources(g) >= min_src or any(mark.search(m["title"]) for m in g)]
    cands.sort(key=lambda g: (n_sources(g), g[0]["published"]), reverse=True)
    print(f"  {region['label']}: 최근 {BREAKING_WINDOW_MIN}분 기사 {len(items)}건 → 소식 {len(groups)}개 → 속보 후보 {len(cands)}개")

    recent = [x for x in data["items"] if x.get("theme") == theme and x["pub"] >= time.time() - 12 * 3600]
    added = 0
    for g in cands:
        keys = list(dict.fromkeys(title_key(m["title"]) for m in g))
        if any(k in seen for k in keys) or any(same_story(g[0]["title"], x["title"]) for x in recent):
            for k in keys:
                seen[k] = time.time()
            continue
        if added >= max_new:
            break
        rep = next((m for m in g if mark.search(m["title"])), g[0])
        cnt = n_sources(g)
        show = translate_ko(rep["title"])
        real = decode_gnews(rep["link"]) or rep["link"]
        if is_pr(real):                     # 보도자료는 속보가 아님
            for k in keys:
                seen[k] = time.time()
            continue
        summ = fetch_summary(real)
        pub = rep["published"]
        item = {"key": keys[0], "keys": keys[:60], "count": cnt, "theme": theme, "rk": region["key"],
                "region": region["label"], "title": rep["title"], "show": show, "source": rep["source"],
                "src_url": rep.get("src_url", ""), "sum": translate_ko(summ) if summ else "",
                "link": rep["link"], "url": real, "pub": pub.timestamp(),
                "time": pub.astimezone(KST).strftime("%m/%d %H:%M"), "run": "breaking",
                "added": int(time.time())}
        if push:
            meta = " · ".join(x for x in [rep["source"], item["time"], f"언론 {cnt}곳" if cnt > 1 else ""] if x)
            label = "🚨 미국 속보" if region["key"] == "us" else f"🌏 {region['label']} 속보"
            if not notify(label, f"{show}\n{meta}", click=real, tags=["rotating_light"], priority=4):
                continue   # 알림 실패 → 다음 확인 때 다시 시도
            time.sleep(1)
        data["items"].append(item)
        recent.append(item)
        for k in keys:
            seen[k] = time.time()
        added += 1
        print(f"    {'🚨' if push else '•'} {show}")
    return added


def check_breaking():
    data = load_breaking()
    seen = data.setdefault("seen", {})
    print("속보 확인:")
    us_new = _breaking_round(data, seen, US, BREAKING_WORDS, BREAKING_NAME, BREAKING_MARK,
                             BREAKING_MIN_SOURCES, BREAKING_MAX_ALERTS, push=True)
    gl_new = 0
    for region in REGIONS:
        if region["key"] == "us" or region["key"] not in GLOBAL_BREAKING_WORDS:
            continue
        gl_new += _breaking_round(data, seen, region, GLOBAL_BREAKING_WORDS[region["key"]], GLOBAL_BREAKING_NAME,
                                  GLOBAL_BREAKING_MARK, BREAKING_MIN_SOURCES, GLOBAL_BREAKING_MAX,
                                  push=GLOBAL_BREAKING_PUSH)

    cutoff = time.time() - PAGE_DAYS * 86400
    data["items"] = [x for x in data["items"] if x["pub"] >= cutoff]
    data["seen"] = {k: v for k, v in seen.items() if v >= time.time() - 2 * 86400}
    with open(BREAKING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)

    print(f"미국 속보 알림 {us_new}건 · 해외 속보 {gl_new}건 추가")
    if us_new or gl_new:
        open(os.path.join(HERE, ".breaking_new"), "w").close()   # 새 속보 있음 → 이번에 기록 저장


def score_sources(region_key, raw_items, sc):
    """공동 보도 점수: 목록에 없는 언론사가 주요 언론사(2곳 이상)와 같은 소식을 얼마나 함께 보도했는지"""
    day = datetime.now(KST).strftime("%Y-%m-%d")
    bucket = sc.setdefault("days", {}).setdefault(day, {}).setdefault(region_key, {})
    for g in cluster(raw_items):
        trusted = [m for m in g if is_trusted(region_key, m["source"], m["src_url"])]
        trusted_n = len({m["source"] for m in trusted})
        first_trusted = min((m["published"] for m in trusted if m["published"]), default=None)
        for m in g:
            if not m["source"] or is_trusted(region_key, m["source"], m["src_url"]) or is_blocked(m["source"], m["src_url"]):
                continue
            # 언론사별로 기사 하나당 한 번만 셈 (여러 번 실행돼도 중복 안 됨)
            #   1 = 주요 언론사 2곳 이상과 공동 보도
            #   2 = 게다가 주요 언론사들보다 먼저 보도 (받아 쓴 게 아니라 먼저 취재했다는 신호)
            arts = bucket.setdefault(m["source"], {})
            k = title_key(m["title"])[:24]
            v = 0
            if trusted_n >= 2:
                v = 2 if (m["published"] and first_trusted and m["published"] < first_trusted) else 1
            arts[k] = max(arts.get(k, 0), v)


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
                t = total.setdefault(rk, {}).setdefault(src, [0, 0, 0])
                t[0] += len(arts)
                t[1] += sum(1 for v in arts.values() if v >= 1)
                t[2] += sum(1 for v in arts.values() if v >= 2)
    auto = {}
    for rk, srcs in total.items():
        auto[rk] = sorted(src for src, (n, co, first) in srcs.items()
                          if n >= AUTO_MIN_STORIES and co >= AUTO_MIN_CO and co / n >= AUTO_MIN_RATIO
                          and first >= AUTO_MIN_FIRST)
    sc["auto"] = auto
    with open(SOURCES_FILE, "w", encoding="utf-8") as f:
        json.dump(sc, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    added = sum(len(v) for v in auto.values())
    print(f"자동 추가된 언론사: {added}곳 " + str({k: v for k, v in auto.items() if v}))


def clean_news(news):
    """같은 원문 주소 중복 제거 + 사이트 소개문 같은 엉터리 요약 지우기"""
    out, by_url = [], {}
    pr = sum(1 for n in news if is_pr(n.get("url")))
    news = [n for n in news if not is_pr(n.get("url"))]
    if pr:
        print(f"정리: 보도자료 {pr}건 제외")
    for n in sorted(news, key=lambda n: (-n.get("count", 1), n["pub"])):
        u = n.get("url")
        if u and u in by_url:
            keep = by_url[u]
            keep["count"] = max(keep.get("count", 1), n.get("count", 1))
            keep["keys"] = list(dict.fromkeys((keep.get("keys") or [keep["key"]]) + (n.get("keys") or [n["key"]])))[:60]
            continue
        if u:
            by_url[u] = n
        out.append(n)
    # 같은 테마 안에서 제목만 조금 다른 같은 소식은 하나로 합침 (화제성 높은 쪽을 남김)
    merged, kept = 0, []
    for n in out:
        twin = next((k for k in kept if k["theme"] == n["theme"] and same_story(k["title"], n["title"])), None)
        if twin is not None:
            twin["count"] = max(twin.get("count", 1), n.get("count", 1))
            twin["keys"] = list(dict.fromkeys((twin.get("keys") or [twin["key"]]) + (n.get("keys") or [n["key"]])))[:60]
            merged += 1
            continue
        kept.append(n)
    out = kept
    # 같은 언론사 기사 여러 개에 똑같은 요약 → 사이트 소개문이라 지움 / 너무 짧거나 주소가 든 요약도 지움
    same = {}
    for n in out:
        if n.get("sum"):
            same[(n["source"], n["sum"])] = same.get((n["source"], n["sum"]), 0) + 1
    removed = 0
    for n in out:
        sm = n.get("sum", "")
        if sm and (same[(n["source"], sm)] > 1 or len(sm) < 30 or re.search(r"https?://", sm)):
            n.pop("sum", None)
            n["sum_tried"] = 2
            removed += 1
    if len(out) != len(news) or removed:
        print(f"정리: 중복 {len(news) - len(out)}건 합침(같은 원문 주소·비슷한 제목 {merged}건 포함), 엉터리 요약 {removed}건 지움")
    return out


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
    theme_of = {t["name"]: t for t in THEMES}
    old_news = [n for n in load_news() if n.get("pub", 0) >= cutoff and not EXCLUDE.search(n.get("title", ""))
                and n.get("theme") in theme_of and is_relevant(theme_of[n["theme"]], n.get("title", ""))]
    key_to_old = {}
    old_by_theme = {}
    for n in old_news:
        for k in n.get("keys") or [n["key"]]:
            key_to_old[k] = n
        old_by_theme.setdefault(n["theme"], []).append(n)

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
            items = [it for it in raw if is_trusted(region["key"], it["source"], it["src_url"])
                     and is_relevant(theme, it["title"])]
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
                if old is None:       # 제목이 조금 달라도 같은 테마에 이미 있는 소식이면 같은 걸로 봄
                    old = next((o for o in old_by_theme.get(name, [])
                                if any(same_story(m["title"], o["title"]) for m in g[:4])), None)
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
                    "run": run_id, "added": int(time.time())})
                taken.update(keys)
                old_by_theme.setdefault(name, []).append(new_items[-1])
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
    # 믿을 만한 언론사 기사만 남기고, 테마마다 너무 많이 쌓이지 않게 정리
    #   최근 24시간 기사는 모두 유지 + 그보다 오래된 건 화제성 높은 순으로 테마당 최대 THEME_KEEP 개
    rk = {r["label"]: r["key"] for r in REGIONS}
    news = [n for n in news if is_trusted(rk.get(n["region"], ""), n.get("source", ""), n.get("src_url") or n.get("url", ""))]
    day_ago = time.time() - 86400
    kept = []
    for t in THEMES:
        items = [n for n in news if n["theme"] == t["name"]]
        recent = [n for n in items if n.get("added", n["pub"]) >= day_ago]
        older = sorted((n for n in items if n.get("added", n["pub"]) < day_ago),
                       key=lambda n: (-n.get("count", 1), -n["pub"]))
        kept += recent + older[:max(0, THEME_KEEP - len(recent))]
    news = kept
    shown = list(news)
    shown.sort(key=lambda n: (n.get("run") != run_id, -n.get("count", 1), -n["pub"]))
    add_real_urls(shown, limit=300)
    retranslate_failed(shown)
    add_summaries(shown, limit=300)
    news = clean_news(news)
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

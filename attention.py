"""테마별 '관심도' 모으기 — 위키백과 조회수(4개 언어) + 구글 트렌드(되는 날만).

옛날 뉴스는 검색에 일부만 나와 기사 수로는 '얼마나 화제였나'를 알 수 없음.
그래서 사람들이 그 테마를 얼마나 찾아봤는지를 따로 모아 attention.json 에 저장.
  - 위키백과: 2026-01-01부터 어제까지 하루 단위 조회수 (열쇠 필요 없음, 정확)
  - 구글 트렌드: 한국 검색량 (비공식이라 자주 막힘 → 실패하면 지난 값 유지)
news_stats.apply_attn 이 이 파일로 '화제 테마 / 쟁점 테마'를 판정함.
"""
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

import requests

START = date(2026, 1, 1)
OUT = "attention.json"
UA = {"User-Agent": "Investment_NotiBot/1.0 (https://github.com/inwonc4524-code/Investment_NotiBot)"}
LANGS = ["en", "ko", "ja", "zh"]

# 테마마다 영어 위키 문서 → 한국어·일본어·중국어 문서는 언어 연결로 자동으로 찾음
WIKI = {
    "반도체": ["Semiconductor industry", "High Bandwidth Memory", "SK Hynix", "TSMC", "Nvidia", "Samsung Electronics"],
    "2차전지": ["Lithium-ion battery", "Solid-state battery", "CATL", "LG Energy Solution", "Sodium-ion battery"],
    "AI": ["Artificial intelligence", "ChatGPT", "OpenAI", "Large language model", "Anthropic"],
    "로봇": ["Humanoid robot", "Robotics", "Optimus (robot)", "Unitree Robotics", "Boston Dynamics"],
    "바이오·제약": ["Biotechnology", "Pharmaceutical industry", "Samsung Biologics", "Celltrion", "GLP-1 receptor agonist"],
    "방산": ["Arms industry", "Hanwha Aerospace", "K9 Thunder", "K2 Black Panther", "Lockheed Martin"],
    "원전": ["Nuclear power", "Small modular reactor", "Korea Hydro & Nuclear Power", "Doosan Enerbility"],
    "조선": ["Shipbuilding", "HD Hyundai Heavy Industries", "Hanwha Ocean", "LNG carrier"],
    "전력기기": ["Transformer", "Electrical grid", "HD Hyundai Electric", "LS Electric"],
    "자동차": ["Automotive industry", "Hyundai Motor Company", "Tesla, Inc.", "Electric vehicle", "Kia"],
    "우주항공": ["SpaceX", "Starlink", "Satellite internet constellation", "Korea Aerospace Industries", "Artemis program"],
    "수소": ["Hydrogen economy", "Fuel cell", "Hydrogen vehicle", "Green hydrogen"],
    "신재생에너지": ["Renewable energy", "Solar power", "Wind power", "Offshore wind power"],
    "게임": ["Video game industry", "Nexon", "Krafton", "Nintendo Switch 2", "NCSoft"],
    "엔터": ["K-pop", "Hybe Corporation", "BTS", "Blackpink", "KPop Demon Hunters"],
    "화장품": ["K-beauty", "Korean cosmetics", "Amorepacific", "Cosmetics", "Olive Young"],
    "금융": ["KB Financial Group", "Shinhan Financial Group", "Hana Financial Group", "Bank of Korea", "Federal Reserve"],
    "인터넷·플랫폼": ["Naver Corporation", "Kakao", "Coupang", "Big Tech", "Amazon (company)"],
    "건설·부동산": ["Real estate economics", "Mortgage loan", "Hyundai Engineering & Construction", "Samsung C&T", "Real estate bubble"],
    "가상자산": ["Bitcoin", "Cryptocurrency", "Ethereum", "Stablecoin", "Upbit"],
}

# 구글 트렌드 한국 검색어 (투자 관심을 보려고 '…주' 형태 위주)
TRENDS = {
    "반도체": "반도체주", "2차전지": "2차전지주", "AI": "AI 관련주", "로봇": "로봇주",
    "바이오·제약": "바이오주", "방산": "방산주", "원전": "원전주", "조선": "조선주",
    "전력기기": "전력기기", "자동차": "자동차주", "우주항공": "우주항공", "수소": "수소주",
    "신재생에너지": "태양광", "게임": "게임주", "엔터": "엔터주", "화장품": "화장품주",
    "금융": "은행주", "인터넷·플랫폼": "플랫폼주", "건설·부동산": "건설주", "가상자산": "비트코인",
}


def get(url, **kw):
    for t in range(4):
        try:
            r = requests.get(url, headers=UA, timeout=30, **kw)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
        except Exception as e:
            print("  다시 시도:", e)
        time.sleep(2 + t * 3)
    return None


def titles_for(en_titles):
    """영어 문서 → {언어: [문서 제목]} (넘겨주기 정리, 언어 연결 따라가기)"""
    out = {l: [] for l in LANGS}
    for t in en_titles:
        j = get("https://en.wikipedia.org/w/api.php", params={
            "action": "query", "titles": t, "redirects": 1, "prop": "langlinks",
            "lllimit": 500, "format": "json"})
        if not j:
            print("  문서 못 찾음:", t)
            continue
        for p in j.get("query", {}).get("pages", {}).values():
            if "missing" in p:
                print("  없는 문서:", t)
                continue
            out["en"].append(p["title"])
            for ll in p.get("langlinks", []):
                if ll["lang"] in out and ll["lang"] != "en":
                    out[ll["lang"]].append(ll["*"])
    return out


def views(lang, title, end):
    url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
           f"{lang}.wikipedia/all-access/user/{quote(title.replace(' ', '_'), safe='')}/daily/"
           f"{START:%Y%m%d}00/{end:%Y%m%d}00")
    j = get(url)
    out = {}
    for it in (j or {}).get("items", []):
        out[it["timestamp"][:8]] = it["views"]
    return out


def wiki_all(end):
    ndays = (end - START).days + 1
    days = [(START + timedelta(i)).strftime("%Y%m%d") for i in range(ndays)]
    data, used, detail = {}, {}, {}
    for th, en in WIKI.items():
        tl = titles_for(en)
        used[th] = tl
        data[th] = {}
        detail[th] = {}
        for lang in LANGS:
            tot = [0] * ndays
            for title in tl[lang]:
                v = views(lang, title, end)
                for i, d in enumerate(days):
                    tot[i] += v.get(d, 0)
                mon = {}
                for d, n in v.items():
                    mon[d[:6]] = mon.get(d[:6], 0) + n
                detail[th].setdefault(lang, {})[title] = mon     # 문서별 달 합계 (어떤 문서가 치솟았는지 확인용)
            data[th][lang] = tot
        print(th, {l: sum(data[th][l]) for l in LANGS})
    return data, used, detail


def trends_all(old):
    """구글 트렌드: 테마마다 한 번씩 (서로 비교하지 않고 자기 평소와만 비교)"""
    try:
        from pytrends.request import TrendReq
    except Exception as e:
        print("구글 트렌드 프로그램 없음:", e)
        return old, False
    tr = TrendReq(hl="ko-KR", tz=-540, timeout=(10, 30))
    tf = f"{START:%Y-%m-%d} {date.today():%Y-%m-%d}"
    out, ok = dict(old), 0
    todo = list(TRENDS.items())
    for rnd in range(2):                     # 막힌 테마는 한 번 더 (1분 쉬고)
        if rnd:
            todo = [(th, kw) for th, kw in todo if th not in done]
            if not todo:
                break
            time.sleep(60)
        done = set()
        for th, kw in todo:
            if _one(tr, th, kw, tf, out):
                done.add(th)
                ok += 1
            time.sleep(12)
    return out, ok > 0


def _one(tr, th, kw, tf, out):
        try:
            tr.build_payload([kw], timeframe=tf, geo="KR")
            df = tr.interest_over_time()
            if df is not None and len(df) and kw in df:
                out[th] = {i.strftime("%Y%m%d"): int(v) for i, v in df[kw].items()}
                print("트렌드", th, len(out[th]))
                return True
            print("트렌드 자료 없음", th)
            return True
        except Exception as e:
            print("트렌드 막힘", th, str(e)[:80])
            time.sleep(30)
            return False


def main():
    end = date.today() - timedelta(days=1)
    old = {}
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT, encoding="utf-8"))
        except Exception:
            old = {}
    data, used, detail = wiki_all(end)
    # 아직 집계 안 된 마지막 날(모든 문서 0) 잘라내기
    nd = len(next(iter(next(iter(data.values())).values())))
    while nd and all(not a[nd - 1] for L in data.values() for a in L.values()):
        nd -= 1
    for L in data.values():
        for l in L:
            L[l] = L[l][:nd]
    end = START + timedelta(days=nd - 1)
    tr, tr_ok = trends_all(old.get("trends", {}))
    res = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "start": START.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "wiki": data,
        "wiki_titles": used,
        "wiki_detail": detail,
        "trends": tr,
        "trends_terms": TRENDS,
        "trends_updated": (datetime.now(timezone.utc).strftime("%Y-%m-%d") if tr_ok else old.get("trends_updated")),
    }
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("저장:", OUT, "위키", len(data), "트렌드", len(tr))


if __name__ == "__main__":
    main()

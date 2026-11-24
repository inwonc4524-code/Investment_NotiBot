"""1월~11월 테마별 기사 수 — GDELT 원본 파일(15분마다 한 개, 기사 제목 포함)로 다시 세기 (사용자 요청 2026-11-24)

GDELT 검색 창구는 9월 중순부터 구멍이 많지만, 원본 파일은 하루 96개씩 빠짐없이 있음.
원본 파일의 기사 제목에 봇과 똑같은 기준(news_stats.relevant + 스팸·광고·부고 거르기)을 적용해 셈.
  - 영어 파일 + 번역 파일(한·중·일 등 원래 언어 제목)을 모두 봄
  - 같은 날 같은 제목은 한 번만 (여러 사이트에 그대로 실린 기사)
  - 나라는 사이트 주소 끝(.kr .jp .cn .tw .hk .sg)과 제목 글자로 나눔 (봇의 나라 구분과는 조금 다를 수 있음)
결과: gkg_bf/{달}.json = {"days": {날짜: {테마: {나라: 수}}}, "files": {날짜: 받은 파일 수}, "seen": {날짜: 본 기사 수}}

사용: python gkg_count.py 2026-01        (그 달 전체, 어제까지)
"""
import html
import io
import json
import os
import re
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import requests

import news_bot as nb
import news_stats as ns

BASE = "http://data.gdeltproject.org/gdeltv2/"
OUTDIR = os.path.join(nb.HERE, "gkg_bf")
TITLE = re.compile(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", re.S)
HANGUL = re.compile(r"[가-힣]")
KANA = re.compile(r"[ぁ-ゟ゠-ヿ]")
HAN = re.compile(r"[一-鿿]")
TLD = {"kr": "kr", "jp": "jp", "cn": "cn", "tw": "tw", "hk": "hk", "sg": "sg"}
SES = requests.Session()

# 테마마다 빠른 1차 거르기 (진짜 판정은 news_stats.relevant 로 다시)
PRE = {}
for th in ns.STAT_THEMES:
    terms = nb._rel_terms(th)
    pats = []
    for w in terms:
        if re.fullmatch(r"[a-z0-9&.\- ]+", w):
            pats.append(r"(?<![a-z0-9])" + re.escape(w))
        else:
            pats.append(re.escape(w))
    PRE[th["name"]] = (th, re.compile("|".join(pats)) if pats else None)


# 보충용 (2026-11-24): 기사가 적은 테마를 더 잡으려고 — 기사에 나온 회사 이름(GDELT 회사 태그)·추가 영어 단어
# 결과는 따로("days_x") 저장해서, 원래 방식("days")과 맞춰보기 오차를 비교한 뒤 더 나은 쪽을 씀
EXTRA = {
    "반도체": (["sk hynix", "micron technology", "asml", "taiwan semiconductor", "applied materials", "lam research", "broadcom", "qualcomm", "intel corp"],
               ["chipmakers", "memory chips", "foundry", "wafer", "nvidia chips"]),
    "2차전지": (["catl", "lg energy solution", "panasonic energy", "samsung sdi", "sk on", "albemarle", "quantumscape"],
               ["battery maker", "ev battery", "lithium", "battery plant", "cathode"]),
    "로봇": (["boston dynamics", "figure ai", "unitree", "agility robotics", "intuitive surgical", "fanuc"],
             ["robot", "robots", "robotaxi", "humanoid"]),
    "바이오·제약": (["eli lilly", "novo nordisk", "pfizer", "moderna", "merck", "samsung biologics", "celltrion", "amgen", "regeneron"],
                ["drugmaker", "fda approval", "clinical trial", "weight-loss drug", "biotech"]),
    "방산": (["lockheed martin", "raytheon", "northrop grumman", "general dynamics", "rheinmetall", "hanwha aerospace", "bae systems", "pentagon"],
             ["defense contractor", "arms deal", "fighter jet", "missile system", "defense spending", "howitzer"]),
    "원전": (["westinghouse", "nuscale", "korea hydro", "kepco", "cameco", "oklo", "constellation energy", "terrapower"],
             ["nuclear plant", "nuclear reactor", "reactors", "uranium", "nuclear energy"]),
    "조선": (["hd hyundai heavy", "hanwha ocean", "samsung heavy industries", "huntington ingalls", "austal", "fincantieri"],
             ["shipyard", "shipyards", "shipbuilder", "shipbuilders", "lng carrier", "warship"]),
    "전력기기": (["ls electric", "hd hyundai electric", "hyosung heavy", "siemens energy", "ge vernova", "hitachi energy", "eaton", "schneider electric"],
                ["transformer shortage", "transformers", "power grid", "grid equipment", "switchgear", "substation"]),
    "자동차": (["hyundai motor", "kia", "toyota", "general motors", "ford motor", "volkswagen", "stellantis", "byd"],
               ["automaker", "automakers", "carmaker", "carmakers", "auto tariffs"]),
    "우주항공": (["spacex", "blue origin", "rocket lab", "boeing", "airbus", "korea aerospace industries", "nasa"],
                ["rocket launch", "satellite", "satellites", "starship", "aerospace"]),
    "수소": (["plug power", "bloom energy", "nel asa", "ballard power", "air products"],
             ["hydrogen", "fuel cell", "electrolyzer"]),
    "신재생에너지": (["first solar", "nextera energy", "orsted", "vestas", "enphase", "sunrun"],
                  ["solar", "wind farm", "offshore wind", "renewables", "clean energy"]),
    "게임": (["nintendo", "sony interactive", "electronic arts", "take-two", "krafton", "nexon", "ubisoft", "roblox"],
             ["video game", "video games", "gaming", "game studio"]),
    "엔터": (["hybe", "sm entertainment", "jyp entertainment", "yg entertainment", "bts", "blackpink"],
             ["k-pop", "kpop", "k-drama", "boy band", "girl group"]),
    "화장품": (["amorepacific", "lg household", "estee lauder", "l'oreal", "olive young", "ulta beauty", "e.l.f. beauty"],
               ["k-beauty", "skincare", "cosmetics", "beauty brand"]),
    "금융": (["jpmorgan", "goldman sachs", "morgan stanley", "bank of america", "wells fargo", "citigroup", "federal reserve", "kb financial"],
             ["bank stocks", "big banks", "lender", "interest rates"]),
    "인터넷·플랫폼": (["alphabet", "meta platforms", "amazon", "naver", "kakao", "coupang", "netflix"],
                  ["big tech", "tech giants", "online platform", "e-commerce"]),
    "건설·부동산": (["d.r. horton", "lennar", "zillow", "redfin", "samsung c&t", "hyundai engineering"],
                ["housing market", "home prices", "mortgage rates", "homebuilder", "real estate"]),
    "가상자산": (["coinbase", "binance", "microstrategy", "upbit", "tether", "blackrock bitcoin"],
                ["crypto", "stablecoin", "bitcoin etf", "ether", "altcoin"]),
    "AI": (["openai", "anthropic", "nvidia", "deepmind", "xai", "perplexity"],
           ["chatgpt", "generative ai", "large language model", "ai model", "data center"]),
}
XORG = {k: set(v[0]) for k, v in EXTRA.items()}
XPAT = {k: re.compile("|".join(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z])" for w in v[1])) for k, v in EXTRA.items() if v[1]}


def orgs_of(field):
    out = set()
    for part in (field or "").split(";"):
        name = part.split(",")[0].strip().lower()
        if name:
            out.add(name)
    return out


def region_of(domain, title):
    d = (domain or "").lower().rstrip(".")
    tld = d.rsplit(".", 1)[-1] if "." in d else ""
    if tld in TLD:
        return TLD[tld]
    if HANGUL.search(title):
        return "kr"
    if KANA.search(title):
        return "jp"
    if HAN.search(title):
        return "cn"
    if tld in ("com", "net", "org", "us", "news", "io", "co", "biz", "info", "gov", "edu", ""):
        return "us"
    return "world"


def get_file(stamp, kind):
    url = f"{BASE}{stamp}.{kind}gkg.csv.zip"
    for t in range(4):
        try:
            r = SES.get(url, timeout=60)
            if r.status_code == 404:
                return None
            if r.ok:
                z = zipfile.ZipFile(io.BytesIO(r.content))
                return z.read(z.namelist()[0]).decode("utf-8", "replace")
        except Exception:
            pass
        time.sleep(2 + t * 3)
    return None


def rows(text):
    for line in text.split("\n"):
        f = line.split("\t")
        if len(f) < 27:
            continue
        m = TITLE.search(f[26])
        if not m:
            continue
        yield f[3], f[4], html.unescape(m.group(1)).strip(), f[13]


def ok_item(theme, title, domain, url):
    return not (nb.EXCLUDE.search(title) or ns.SPAM.search(title) or ns.SHOP.search(title)
                or ns.NOT_NEWS.search(title) or domain.lower() in ns.STAT_SRC_SKIP
                or nb.is_blocked(domain, url))


def count_day(d):
    stamps = [f"{d:%Y%m%d}{h:02d}{m:02d}00" for h in range(24) for m in (0, 15, 30, 45)]
    jobs = [(s, k) for s in stamps for k in ("", "translation.")]
    with ThreadPoolExecutor(24) as ex:
        texts = list(ex.map(lambda a: get_file(*a), jobs))
    got = sum(1 for t in texts if t)
    out, outx, seen_t, seen_u, n = {}, {}, set(), set(), 0
    for text in texts:
        if not text:
            continue
        for domain, url, title, orgf in rows(text):
            if url in seen_u:
                continue
            seen_u.add(url)
            key = re.sub(r"\W+", "", title.lower())[:80]
            if not key or key in seen_t:          # 같은 날 같은 제목은 한 번만
                continue
            seen_t.add(key)
            n += 1
            low = title.lower()
            rk = None
            orgs = None
            for name, (th, pre) in PRE.items():
                hit = pre is not None and pre.search(low) and ns.relevant(th, title)
                if not hit:                                    # 보충: 회사 태그 또는 추가 단어
                    xp = XPAT.get(name)
                    if not (xp is not None and xp.search(low)):
                        if orgs is None:
                            orgs = orgs_of(orgf)
                        if not (XORG.get(name) and orgs & XORG[name]):
                            continue
                if not ok_item(th, title, domain, url):
                    continue
                rk = rk or region_of(domain, title)
                if hit:
                    v = out.setdefault(name, {})
                    v[rk] = v.get(rk, 0) + 1
                v = outx.setdefault(name, {})
                v[rk] = v.get(rk, 0) + 1
    return out, outx, got, n


def main(month):
    y, m = map(int, month.split("-"))
    a = date(y, m, 1)
    b = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
    b = min(b, date.today() - timedelta(days=1))
    os.makedirs(OUTDIR, exist_ok=True)
    path = os.path.join(OUTDIR, f"{month}.json")
    res = {"days": {}, "days_x": {}, "files": {}, "seen": {}}
    if os.path.exists(path):
        res = json.load(open(path, encoding="utf-8"))
        res.setdefault("days_x", {})
    d = a
    t0 = time.time()
    while d <= b:
        k = d.isoformat()
        if res["files"].get(k, 0) >= 180 and k in res["days_x"]:   # 이미 거의 다 받은 날은 건너뜀
            d += timedelta(days=1)
            continue
        out, outx, got, n = count_day(d)
        res["days"][k], res["days_x"][k], res["files"][k], res["seen"][k] = out, outx, got, n
        tot = sum(sum(v.values()) for v in out.values())
        totx = sum(sum(v.values()) for v in outx.values())
        print(f"{k}: 파일 {got}/192 · 기사 {n:,} · 테마 기사 {tot:,} · 보충 포함 {totx:,} ({time.time() - t0:.0f}초)", flush=True)
        json.dump(res, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        d += timedelta(days=1)


if __name__ == "__main__":
    if sys.argv[1] == "auto":       # 매일: 어제가 든 달(1일이면 지난달도) — 봇과 겹치는 날이 쌓여 보정이 점점 정확해짐
        y = date.today() - timedelta(days=1)
        for mo in sorted({(y - timedelta(days=1)).strftime("%Y-%m"), y.strftime("%Y-%m")}):
            main(mo)
    else:
        main(sys.argv[1])

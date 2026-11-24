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
        yield f[3], f[4], html.unescape(m.group(1)).strip()


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
    out, seen_t, seen_u, n = {}, set(), set(), 0
    for text in texts:
        if not text:
            continue
        for domain, url, title in rows(text):
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
            for name, (th, pre) in PRE.items():
                if pre is None or not pre.search(low):
                    continue
                if not ns.relevant(th, title) or not ok_item(th, title, domain, url):
                    continue
                rk = rk or region_of(domain, title)
                v = out.setdefault(name, {})
                v[rk] = v.get(rk, 0) + 1
    return out, got, n


def main(month):
    y, m = map(int, month.split("-"))
    a = date(y, m, 1)
    b = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
    b = min(b, date.today() - timedelta(days=1))
    os.makedirs(OUTDIR, exist_ok=True)
    path = os.path.join(OUTDIR, f"{month}.json")
    res = {"days": {}, "files": {}, "seen": {}}
    if os.path.exists(path):
        res = json.load(open(path, encoding="utf-8"))
    d = a
    t0 = time.time()
    while d <= b:
        k = d.isoformat()
        if res["files"].get(k, 0) >= 180:          # 이미 거의 다 받은 날은 건너뜀
            d += timedelta(days=1)
            continue
        out, got, n = count_day(d)
        res["days"][k], res["files"][k], res["seen"][k] = out, got, n
        tot = sum(sum(v.values()) for v in out.values())
        print(f"{k}: 파일 {got}/192 · 기사 {n:,} · 테마 기사 {tot:,} ({time.time() - t0:.0f}초)", flush=True)
        json.dump(res, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        d += timedelta(days=1)


if __name__ == "__main__":
    main(sys.argv[1])

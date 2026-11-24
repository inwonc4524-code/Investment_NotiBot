"""기사 수 출처 점검 (일회용): 1월~11월 기사를 빠짐없이 셀 수 있는 곳 찾기"""
import gzip
import io
import re
import time
import zipfile
from collections import Counter
from datetime import date, timedelta

import requests

UA = {"User-Agent": "Mozilla/5.0 (Investment_NotiBot source check)"}


def head(url, **kw):
    try:
        r = requests.get(url, headers=UA, timeout=60, **kw)
        return r
    except Exception as e:
        print("   ! 실패", url[:80], e)
        return None


print("=== 1) GDELT 원본 파일 (15분마다 하나) — 날짜별 파일 수 ===")
r = head("http://data.gdeltproject.org/gdeltv2/masterfilelist.txt")
if r is not None and r.ok:
    per = Counter()
    for line in r.text.splitlines():
        m = re.search(r"/gdeltv2/(\d{8})\d{6}\.gkg\.csv\.zip", line)
        if m and m.group(1) >= "20260101":
            per[m.group(1)] += 1
    days = [(date(2026, 1, 1) + timedelta(i)).strftime("%Y%m%d") for i in range(330)]
    holes = [d for d in days if per.get(d, 0) < 80 and d <= "20261123"]
    print("   날짜 수", len(per), "· 파일 80개 미만인 날", len(holes), holes[:40])
    for mo in range(1, 12):
        k = [v for d, v in per.items() if d[4:6] == f"{mo:02d}"]
        print(f"   {mo}월: 하루 평균 파일 {sum(k)/max(1,len(k)):.0f}개 ({len(k)}일)")
else:
    print("   마스터 목록 못 받음")


def gkg_titles(stamp):
    url = f"http://data.gdeltproject.org/gdeltv2/{stamp}.gkg.csv.zip"
    r = head(url)
    if r is None or not r.ok:
        return None, None
    z = zipfile.ZipFile(io.BytesIO(r.content))
    raw = z.read(z.namelist()[0]).decode("utf-8", "replace")
    rows = raw.splitlines()
    titles = 0
    for row in rows:
        if "<PAGE_TITLE>" in row:
            titles += 1
    sample = re.findall(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", raw)[:5]
    return len(rows), (titles, sample, len(r.content))


print("\n=== 2) GDELT 원본 파일 안에 기사 제목이 있나 (1월·10월·11월 한 파일씩) ===")
for st in ["20260115030000", "20261020030000", "20261118030000"]:
    n, info = gkg_titles(st)
    if n is None:
        print("  ", st, "파일 없음")
    else:
        print("  ", st, "기사", n, "· 제목 있는 기사", info[0], "· 크기", info[2] // 1024, "KB")
        for t in info[1]:
            print("      ·", t[:90])

print("\n=== 3) Common Crawl 뉴스 보관소 (CC-NEWS) 달별 파일 ===")
for mo in range(1, 12):
    r = head(f"https://data.commoncrawl.org/crawl-data/CC-NEWS/2026/{mo:02d}/warc.paths.gz")
    if r is not None and r.ok:
        paths = gzip.decompress(r.content).decode().split()
        days = Counter(re.search(r"CC-NEWS-(\d{8})", p).group(1) for p in paths if re.search(r"CC-NEWS-(\d{8})", p))
        print(f"   {mo}월: 파일 {len(paths)}개 · 날짜 {len(days)}일 · 하루 최소 {min(days.values()) if days else 0}")
    else:
        print(f"   {mo}월: 목록 없음 ({getattr(r, 'status_code', '오류')})")

print("\n=== 4) 구글 뉴스 날짜 검색 — 같은 검색어 'semiconductor' 하루치 결과 수 ===")
for d in ["2026-01-15", "2026-05-15", "2026-09-15", "2026-11-10", "2026-11-20"]:
    a = date.fromisoformat(d)
    q = f"semiconductor after:{a} before:{a + timedelta(days=1)}"
    r = head("https://news.google.com/rss/search", params={"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    n = r.text.count("<item>") if r is not None and r.ok else None
    print("  ", d, "결과", n, "(최대 100)")
    time.sleep(2)

print("\n=== 5) 야후·빙 뉴스 — 지난 날짜로 찾을 수 있나 ===")
for name, url, params in [
    ("야후 뉴스 검색", "https://news.search.yahoo.com/search", {"p": "semiconductor", "fr2": "time"}),
    ("야후 파이낸스 RSS", "https://finance.yahoo.com/rss/headline", {"s": "NVDA"}),
    ("빙 뉴스 RSS", "https://www.bing.com/news/search", {"q": "semiconductor", "format": "rss"}),
]:
    r = head(url, params=params)
    if r is None:
        continue
    dates = re.findall(r"<pubDate>([^<]+)</pubDate>", r.text)
    print(f"   {name}: 응답 {r.status_code} · 기사 {len(dates)}개 · 가장 오래된 {dates[-1] if dates else '-'} (날짜 지정 검색 기능 없음)")

print("\n=== 6) GDELT 검색 창구 — 10월 말~11월 하루 숫자 (지난번 시험 재확인) ===")
r = head("https://api.gdeltproject.org/api/v2/doc/doc", params={
    "query": "semiconductor sourcecountry:US", "mode": "timelinevolraw", "format": "json",
    "startdatetime": "20261020000000", "enddatetime": "20261123235959"})
if r is not None and r.ok and r.text.lstrip().startswith("{"):
    data = r.json().get("timeline", [{}])[0].get("data", [])
    print("   ", " ".join(f"{p['date'][4:8]}:{p['value']}" for p in data))
else:
    print("   응답", getattr(r, "status_code", None))

# -*- coding: utf-8 -*-
"""
📈 테마별 뉴스 장기 추이 (2025년 1월 ~ 지금)
- 구글 뉴스는 지난 날짜 검색이 하루 몇 건밖에 안 나와서, 과거 통계는 GDELT(전 세계 뉴스 기록 프로젝트)의
  '날짜별 기사 수' 자료로 만듭니다. 65개 언어 기사를 영어로 번역해 두고 세기 때문에
  아래 영어 검색어 하나로 한국·중국·일본 언론 기사까지 셀 수 있어요.
- 매일 한 번 최근 2주를 다시 받아서 최신으로 유지하고, 처음 한 번은 2025-01-01부터 전부 채웁니다.
  (GDELT 는 5초에 한 번만 물어볼 수 있어서 처음 채우는 데 1~2시간, 여러 번에 나눠 이어서 받음)
- 결과는 history.json → 뉴스 페이지 📊 통계 탭의 '장기 추이' 에서 월별 그래프로 봅니다.

※ 3시간마다 세는 일별 통계(news_stats.py, 기사 제목 기준)와는 세는 방법이 달라
   숫자 크기는 서로 비교하지 말고, 흐름(늘었나 줄었나)만 보세요.
   GDELT 는 기사 본문까지 보고 세서, 그 단어가 나온 기사 수예요.
"""
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(HERE, "history.json")
KST = timezone(timedelta(hours=9))
SINCE = date(2025, 1, 1)
API = "https://api.gdeltproject.org/api/v2/doc/doc"
REFRESH_DAYS = 14          # 매일 최근 며칠을 다시 받을지 (GDELT 는 며칠 늦게 들어오는 기사가 있음)
TIME_BUDGET = 45 * 60      # 한 번 실행에 최대 몇 초까지 받을지 (넘으면 저장하고 다음 실행에서 이어서)
GAP = 6                    # 요청 사이 간격 (초) — GDELT 규칙: 5초에 한 번

# 나라 (GDELT 나라 코드) — 일별 통계 탭의 나라 키와 같게
REGIONS = [("kr", "KS"), ("us", "US"), ("cn", "CH"), ("tw", "TW"), ("hk", "HK"), ("jp", "JA"), ("sg", "SN")]

# 테마별 영어 검색어 — GDELT 는 본문까지 찾으니, 너무 흔한 단어(banks, Amazon 등)는 빼고 구체적으로
THEMES = [
    ("반도체", ['semiconductor', 'chipmaker', '"memory chip"', 'TSMC', 'HBM']),
    ("2차전지", ['"EV battery"', '"lithium-ion"', '"battery maker"', '"cathode material"', '"secondary battery"']),
    ("AI", ['"artificial intelligence"', '"generative AI"', 'OpenAI', 'ChatGPT']),
    ("로봇", ['robotics', 'humanoid', '"industrial robot"', '"robot maker"']),
    ("바이오·제약", ['biotech', 'pharmaceutical', 'drugmaker', '"clinical trial"', '"FDA approval"']),
    ("방산", ['"defense industry"', '"defense contractor"', '"arms deal"', '"arms exports"', '"defense spending"']),
    ("원전", ['"nuclear power"', '"nuclear reactor"', '"small modular reactor"', 'uranium']),
    ("조선", ['shipbuilding', 'shipbuilder', 'shipyard']),
    ("전력기기", ['"power grid"', '"electrical equipment"', '"power transformer"', '"grid investment"']),
    ("자동차", ['automaker', '"car sales"', '"electric vehicle"', '"auto industry"']),
    ("우주항공", ['satellite', 'SpaceX', '"rocket launch"', '"space industry"', 'aerospace']),
    ("수소", ['hydrogen', '"fuel cell"']),
    ("신재생에너지", ['"solar power"', '"wind power"', '"renewable energy"', '"offshore wind"', '"solar panel"']),
    ("게임", ['"video game"', '"game publisher"', '"gaming industry"', 'Nintendo']),
    ("엔터", ['"K-pop"', '"entertainment industry"', '"music streaming"', '"entertainment company"']),
    ("화장품", ['cosmetics', '"K-beauty"', '"beauty brand"']),
    ("금융", ['"bank stocks"', '"financial sector"', '"banking sector"', 'JPMorgan', '"Goldman Sachs"']),
    ("인터넷·플랫폼", ['"big tech"', 'Alphabet', '"Meta Platforms"', '"online platform"', '"internet company"']),
    ("건설·부동산", ['homebuilder', '"real estate"', '"housing market"', '"construction company"']),
    ("가상자산", ['bitcoin', 'cryptocurrency', 'crypto', 'ethereum', 'stablecoin']),
]


def load():
    try:
        with open(FILE, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and d.get("since") == SINCE.isoformat():
            return d
    except Exception:
        pass
    return {"since": SINCE.isoformat(), "s": {}, "done": {}}


def save(h):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


_last = [0.0]


def fetch(words, code, start, end):
    """[start, end] 날짜별 기사 수 {날짜: 수}. 실패하면 None"""
    q = "(" + " OR ".join(words) + ")" + f" sourcecountry:{code}"
    params = {"query": q, "mode": "timelinevolraw", "format": "json",
              "startdatetime": start.strftime("%Y%m%d000000"), "enddatetime": end.strftime("%Y%m%d235959")}
    for attempt in range(6):
        wait = GAP - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            r = requests.get(API, params=params, timeout=60)
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                out = {}
                for s in r.json().get("timeline", [])[:1]:
                    for p in s.get("data", []):
                        out[p["date"][:4] + "-" + p["date"][4:6] + "-" + p["date"][6:8]] = int(p["value"])
                return out
            if r.status_code == 200:                    # 검색어 문제 등 (예: 너무 짧은 단어)
                print(f"    ! GDELT 응답 이상: {r.text[:150]}")
                return None
            time.sleep(10 + attempt * 10)               # 429(너무 자주 물어봄) → 점점 길게 쉬고 다시
        except Exception as e:
            print(f"    ! {e}")
            time.sleep(10)
    return None


def put(h, theme, rk, counts, start, end):
    """받은 숫자를 배열(2025-01-01 부터 하루 한 칸)에 넣기. 자료가 없는 날은 null"""
    n_days = (end - SINCE).days + 1
    arr = h["s"].setdefault(theme, {}).setdefault(rk, [])
    if len(arr) < n_days:
        arr.extend([None] * (n_days - len(arr)))
    d = start
    while d <= end:
        if d.isoformat() in counts:           # GDELT 에 그날 자료가 없으면 null 그대로 (그래프에서 빈칸)
            arr[(d - SINCE).days] = counts[d.isoformat()]
        d += timedelta(days=1)


def main():
    t0 = time.time()
    h = load()
    today = datetime.now(KST).date()
    end = today - timedelta(days=1)            # 어제까지 (오늘은 진행 중이라 뺌)
    # 할 일: ① 아직 안 받은 연도 묶음(처음 채우기) ② 최근 2주 다시 받기
    jobs = []
    for theme, words in THEMES:
        for rk, code in REGIONS:
            y = SINCE.year
            while y <= end.year:
                a, b = max(SINCE, date(y, 1, 1)), min(end, date(y, 12, 31))
                key = f"{theme}|{rk}|{y}"
                # 지난 해는 한 번 받으면 끝, 올해는 처음 한 번만 통째로 받고 이후엔 최근 2주만
                if not h["done"].get(key):
                    jobs.append((0, theme, words, rk, code, a, b, key))
                y += 1
    # 며칠 실행이 빠졌어도 구멍이 안 나게: 마지막으로 다 받은 날 이후부터 (최소 최근 2주)
    a = end - timedelta(days=REFRESH_DAYS - 1)
    if h.get("through"):
        a = min(a, date.fromisoformat(h["through"]) - timedelta(days=2))
    a = max(SINCE, a)
    for theme, words in THEMES:
        for rk, code in REGIONS:
            jobs.append((1, theme, words, rk, code, a, end, None))
    first = sum(1 for j in jobs if j[0] == 0)
    print(f"처음 채우기 남은 묶음 {first}개 · 최근 {REFRESH_DAYS}일 갱신 {len(jobs) - first}개")

    ok = fail = 0
    refresh_all = True
    fresh = set()                             # 이번 실행에서 통째로 받은 칸 → 최근 2주 다시 받기는 건너뜀
    for kind, theme, words, rk, code, a, b, key in jobs:
        if time.time() - t0 > TIME_BUDGET:
            print("시간이 다 돼서 여기까지 저장 → 다음 실행에서 이어서 받음")
            refresh_all = False
            break
        if kind == 1 and (theme, rk, b.year) in fresh:
            continue
        if kind == 1 and not h["done"].get(f"{theme}|{rk}|{b.year}"):
            refresh_all = False
            continue                          # 아직 처음 채우기가 안 끝난 칸은 그때 같이 받음
        c = fetch(words, code, a, b)
        if c is None:
            fail += 1
            if kind == 1:
                refresh_all = False
            print(f"  ✗ {theme} {rk} {a}~{b}")
            continue
        put(h, theme, rk, c, a, b)
        ok += 1
        if key:
            h["done"][key] = True
            fresh.add((theme, rk, a.year))
            print(f"  ✓ {theme} {rk} {a.year}: {sum(c.values()):,}건 ({len(c)}일)")
        if ok % 20 == 0:
            h["updated"] = datetime.now(KST).strftime("%m/%d %H:%M")
            save(h)                           # 중간중간 저장 (도중에 멈춰도 받은 만큼은 남게)

    # 모든 줄 길이를 어제까지로 맞추기
    n_days = (end - SINCE).days + 1
    for theme in h["s"]:
        for rk, arr in h["s"][theme].items():
            if len(arr) < n_days:
                arr.extend([None] * (n_days - len(arr)))
    h["themes"] = [t for t, _ in THEMES]
    h["regions"] = [rk for rk, _ in REGIONS]
    h["end"] = end.isoformat()
    if refresh_all:
        h["through"] = end.isoformat()
    h["complete"] = all(h["done"].get(f"{t}|{rk}|{y}") for t, _ in THEMES for rk, _ in REGIONS
                        for y in range(SINCE.year, end.year + 1))
    h["updated"] = datetime.now(KST).strftime("%m/%d %H:%M")
    save(h)
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as f:
        f.write(f"more={'false' if h['complete'] else 'true'}\n")   # 아직 덜 채웠으면 워크플로가 바로 이어서 한 번 더
    print(f"완료: 받기 {ok} · 실패 {fail} · 처음 채우기 {'끝' if h['complete'] else '진행 중'} · {time.time() - t0:.0f}초")


if __name__ == "__main__":
    main()

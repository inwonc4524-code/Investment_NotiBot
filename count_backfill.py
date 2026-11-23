# -*- coding: utf-8 -*-
"""
올해 1월부터 테마별 기사 수 다시 모으기 (사용자 요청 2026-11-23)

통계(1시간마다 센 숫자)는 11/15부터 있어서, 그 전 날짜는 구글 뉴스 날짜 검색(after:/before:)으로
테마·나라·하루씩 다시 찾아 셉니다. 셀 때 거르는 기준(스팸·광고·부고·테마 무관 등)과
'한 기사는 처음 잡힌 나라 한 곳에만' 규칙은 평소 통계와 똑같아요.

구글 뉴스는 한 번 검색에 100개까지라, 꽉 차면 검색어를 하나씩 나눠 더 찾고,
그래도 꽉 차면 그 칸은 '상한(+)'으로 표시해요.

사용:
  python count_backfill.py --calib                 # 이미 센 날(11/16~18)로 다시 세는 방법이 얼마나 맞는지 비교
  python count_backfill.py 2026-01-01 2026-01-31   # 그 기간 다시 세서 count_bf/2026-01-01.json 에 저장
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta

import news_bot as nb
import news_stats as ns

OUTDIR = os.path.join(nb.HERE, "count_bf")
SAT = ns.SATURATED


def _ok(theme, it):
    t = it["title"]
    return not (nb.EXCLUDE.search(t) or ns.SPAM.search(t) or ns.SHOP.search(t) or ns.NOT_NEWS.search(t)
                or (it.get("source") or "").strip().lower() in ns.STAT_SRC_SKIP
                or nb.is_blocked(it["source"], it.get("src_url", "")) or not ns.relevant(theme, t))


def get(region, words, rng):
    for attempt in range(4):
        got = ns._rss(nb.search_url(region, words, when=None, sites=rng))
        time.sleep(0.5)
        if got is not None:
            return got
        time.sleep(20 * (attempt + 1))        # 구글이 잠깐 막으면 쉬었다가 다시
    return None


def count_day(d):
    """하루 → ({테마: {나라: 개수}}, [상한 칸], 실패 수)"""
    d0 = datetime.strptime(d, "%Y-%m-%d")
    rng = f"after:{(d0 - timedelta(days=1)).strftime('%Y-%m-%d')} before:{(d0 + timedelta(days=1)).strftime('%Y-%m-%d')}"
    out, capped, fails = {}, [], 0
    for th in ns.STAT_THEMES:
        taken = set()
        for region in nb.REGIONS:
            words = th.get(region["words"]) or []
            if not words:
                continue
            items = get(region, words, rng)
            if items is None:
                fails += 1
                continue
            cap = False
            if len(items) >= SAT:
                if len(words) > 1:
                    for w in words:
                        more = get(region, [w], rng)
                        if more:
                            items += more
                            cap = cap or len(more) >= SAT
                else:
                    cap = True
            n = 0
            for it in items:
                pub = it.get("published")
                if not pub or pub.astimezone(nb.KST).strftime("%Y-%m-%d") != d or not _ok(th, it):
                    continue
                k = nb.title_key(it["title"])[:40]
                if not k or k in taken:
                    continue
                taken.add(k)
                n += 1
            if n:
                out.setdefault(th["name"], {})[region["key"]] = n
            if cap:
                capped.append(f'{th["name"]}|{region["key"]}')
    return out, capped, fails


def calib():
    st = ns.load_stats()
    for d in ["2026-11-16", "2026-11-17", "2026-11-18"]:
        t0 = time.time()
        got, capped, fails = count_day(d)
        live = st["days"].get(d, {})
        a = sum(sum(v.values()) for v in got.values()); b = sum(sum(v.values()) for v in live.values())
        print(f"== {d}: 다시 센 수 {a} / 1시간마다 센 수 {b} = {a / max(1, b):.0%} · 상한 칸 {len(capped)} · 실패 {fails} · {time.time() - t0:.0f}초", flush=True)
        for th in ns.STAT_THEMES:
            x = sum(got.get(th["name"], {}).values()); y = sum(live.get(th["name"], {}).values())
            print(f"   {th['name']}: {x} / {y} = {x / max(1, y):.0%}", flush=True)


def run(start, end):
    os.makedirs(OUTDIR, exist_ok=True)
    path = os.path.join(OUTDIR, f"{start}.json")
    res = {"days": {}, "capped": {}}
    if os.path.exists(path):
        res = json.load(open(path, encoding="utf-8"))
    d = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d")
    while d <= e:
        k = d.strftime("%Y-%m-%d")
        if k not in res["days"]:
            t0 = time.time()
            got, capped, fails = count_day(k)
            if fails > 20:                     # 너무 많이 실패한 날은 저장하지 않고 다음에 다시
                print(f"{k}: 실패 {fails} — 건너뜀 (다음에 다시)", flush=True)
            else:
                res["days"][k] = got
                if capped:
                    res["capped"][k] = capped
                json.dump(res, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
                print(f"{k}: {sum(sum(v.values()) for v in got.values())}건 · 상한 {len(capped)} · 실패 {fails} · {time.time() - t0:.0f}초", flush=True)
        d += timedelta(days=1)


if __name__ == "__main__":
    if "--calib" in sys.argv:
        calib()
    else:
        run(sys.argv[1], sys.argv[2])

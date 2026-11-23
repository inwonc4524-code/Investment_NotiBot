# -*- coding: utf-8 -*-
"""
올해 1월~11/14 테마별 긍정·부정·중립 '비율' — 월별 표본을 모아 Claude 가 판정 (사용자 요청 2026-11-24)

그 기간은 기사 수를 믿을 수 없어서(오래된 날짜는 구글 검색에서 많이 빠짐) 숫자 대신 비율만 보여 줘요.
달마다 8일을 골라 테마·나라별 기사를 구글 뉴스 날짜 검색으로 모으고, 평소 통계와 같은 기준으로 거른 뒤
테마·달마다 40건을 뽑아요. 나라별 몫은 1시간마다 센 최근 기사 수(11/16~21)의 나라 비율대로 나눠요.

사용: python ratio_backfill.py 2026-01   →  ratio_bf/2026-01.json {"month", "days", "items": [{k, t, d, th, rk}]}
"""
import calendar
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta

import news_bot as nb
import news_stats as ns
from count_backfill import get, _ok

OUTDIR = os.path.join(nb.HERE, "ratio_bf")
SAMPLE = 40
DAYS_PER_MONTH = 8
LAST = "2026-11-14"
REF = ["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20", "2026-11-21"]


def region_weights(st):
    w = {}
    for d in REF:
        for th, regs in st.get("days", {}).get(d, {}).items():
            for rk, n in regs.items():
                w.setdefault(th, {}).setdefault(rk, 0)
                w[th][rk] += n
    return w


def main(month):
    y, m = map(int, month.split("-"))
    days = [f"{y}-{m:02d}-{d:02d}" for d in range(1, calendar.monthrange(y, m)[1] + 1)]
    days = [d for d in days if d <= LAST]
    random.seed(int(month.replace("-", "")))
    pick = sorted(random.sample(days, min(DAYS_PER_MONTH, len(days))))
    st = ns.load_stats()
    W = region_weights(st)
    R = {r["key"]: r for r in nb.REGIONS}
    items = []
    for th in ns.STAT_THEMES:
        name = th["name"]
        cand, taken = {}, set()
        for d in pick:
            d0 = datetime.strptime(d, "%Y-%m-%d")
            rng = f"after:{(d0 - timedelta(days=1)).strftime('%Y-%m-%d')} before:{(d0 + timedelta(days=1)).strftime('%Y-%m-%d')}"
            for rk in [r["key"] for r in nb.REGIONS]:
                words = th.get(R[rk]["words"]) or []
                if not words:
                    continue
                for it in get(R[rk], words, rng) or []:
                    pub = it.get("published")
                    if not pub or pub.astimezone(nb.KST).strftime("%Y-%m-%d") != d or not _ok(th, it):
                        continue
                    k = nb.title_key(it["title"])[:40]
                    if not k or k in taken:
                        continue
                    taken.add(k)
                    cand.setdefault(rk, []).append((k, it["title"], d))
        w = W.get(name) or {rk: len(v) for rk, v in cand.items()}
        tot = sum(w.get(rk, 0) for rk in cand) or 1
        got = 0
        for rk, lst in cand.items():
            q = min(len(lst), max(1, round(SAMPLE * w.get(rk, 0) / tot))) if w.get(rk, 0) else 0
            for k, t, d in random.sample(lst, q):
                items.append({"k": k, "t": t, "d": d, "th": name, "rk": rk})
                got += 1
        print(f"{month} {name}: 모은 기사 {sum(len(v) for v in cand.values())} · 표본 {got}", flush=True)
    os.makedirs(OUTDIR, exist_ok=True)
    json.dump({"month": month, "days": pick, "items": items},
              open(os.path.join(OUTDIR, f"{month}.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main(sys.argv[1])

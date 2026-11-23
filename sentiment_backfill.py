# -*- coding: utf-8 -*-
"""
지난주(11/15~11/21) 긍정·부정·중립 — 표본을 다시 모아 판정 (한 번만 돌리는 작업, 사용자 결정 2026-11-23)

그때는 기사 수만 세고 제목은 저장하지 않아서, 구글 뉴스 날짜 검색(after:/before:)으로 테마·날짜·나라별 기사를
다시 모아 표본을 뽑고, 평소와 같은 방법(낱말 판정 + 무료 AI 판정, 다르면 Claude 검토)으로 판정해요.
통계에서는 그날 실제 기사 수를 표본 비율로 나눠 '≈ 표본 기준' 숫자로 보여 줘요 (news_stats.apply_backfill).

결과: sentiment_backfill.json {"days": [...], "items": [{k, t, d, th, rk, f, lx, ai}]}
"""
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta

import news_bot as nb
import news_stats as ns
import sentiment

OUT = os.path.join(nb.HERE, "sentiment_backfill.json")
DAYS = ["2026-11-15", "2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20", "2026-11-21"]
SAMPLE = 40          # 테마·날짜마다 판정할 기사 수 (나라별 실제 기사 수 비율대로 나눔)


def gather():
    st = ns.load_stats()
    R = {r["key"]: r for r in nb.REGIONS}
    items = []
    random.seed(7)
    for d in DAYS:
        d0 = datetime.strptime(d, "%Y-%m-%d")
        rng = f"after:{(d0 - timedelta(days=1)).strftime('%Y-%m-%d')} before:{(d0 + timedelta(days=1)).strftime('%Y-%m-%d')}"
        for th in ns.STAT_THEMES:
            name = th["name"]
            cand = {}                                  # 나라 → [(기사표시, 제목)]
            taken = set()
            for rk in [r["key"] for r in nb.REGIONS]:  # 기사 수 셀 때와 같은 나라 순서로 (같은 기사는 처음 나라에만)
                words = th.get(R[rk]["words"]) or []
                if not words:
                    continue
                got = ns._rss(nb.search_url(R[rk], words, when=None, sites=rng)) or []
                time.sleep(0.4)
                for it in got:
                    pub = it.get("published")
                    if not pub or pub.astimezone(nb.KST).strftime("%Y-%m-%d") != d:
                        continue
                    t = it["title"]
                    if nb.EXCLUDE.search(t) or ns.SPAM.search(t) or nb.is_blocked(it["source"], it.get("src_url", "")) \
                            or not ns.relevant(th, t):
                        continue
                    k = nb.title_key(t)[:40]
                    if k in taken:
                        continue
                    taken.add(k)
                    cand.setdefault(rk, []).append((k, t))
            # 나라별 실제 기사 수 비율대로 표본 나누기 (그날 기사 수가 없으면 모은 개수 비율)
            real = st.get("days", {}).get(d, {}).get(name, {})
            tot = sum(real.values()) or sum(len(v) for v in cand.values()) or 1
            for rk, lst in cand.items():
                w = (real.get(rk, 0) if real else len(lst)) / tot
                q = min(len(lst), max(1, round(SAMPLE * w)))
                for k, t in random.sample(lst, q):
                    items.append({"k": k, "t": t, "d": d, "th": name, "rk": rk})
            print(f"{d} {name}: 모은 기사 {sum(len(v) for v in cand.values())} · 표본 {sum(1 for i in items if i['d'] == d and i['th'] == name)}", flush=True)
    return items


def main():
    if os.path.exists(OUT) and "--judge-only" in sys.argv:
        data = json.load(open(OUT, encoding="utf-8"))
        items = data["items"]
    else:
        items = gather()
        json.dump({"days": DAYS, "items": items}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    todo = [i for i in items if i.get("f") in (None, "?")]
    print(f"판정할 기사 {len(todo)}건", flush=True)
    t0 = time.time()
    for s in range(0, len(todo), 200):            # 200건씩 판정하고 바로 저장 (도중에 멈춰도 남게)
        part = todo[s:s + 200]
        det = sentiment.judge_detail([i["t"] for i in part])
        for i, (f, lx, ai) in zip(part, det):
            i["f"], i["lx"], i["ai"] = f, lx, ai
        json.dump({"days": DAYS, "items": items}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
        c = {k: sum(1 for i in items if i.get("f") == k) for k in "pnux"}
        print(f"  {min(s + 200, len(todo))}/{len(todo)} · 긍정 {c['p']} 부정 {c['n']} 중립 {c['u']} 판정다름 {c['x']} · {time.time() - t0:.0f}초", flush=True)


if __name__ == "__main__":
    main()

# 임시 점검: 통계 집계가 제대로 세는지 실제 자료로 확인 (점검 후 삭제)
import json, random, re, time, sys
from datetime import datetime, timedelta
import news_bot as nb, news_stats as ns
random.seed(1)
now = datetime.now(nb.KST)
live = {now.strftime("%Y-%m-%d"), (now - timedelta(days=1)).strftime("%Y-%m-%d")}
R = {r["key"]: r for r in nb.REGIONS}
T = {t["name"]: t for t in ns.STAT_THEMES}
out = {"sample": {}, "reject": {}, "window": {}, "gdelt": []}

print("=== A. 관련성 표본 ===")
for tn in ["AI", "게임", "금융", "인터넷·플랫폼", "2차전지", "바이오·제약", "엔터", "자동차", "전력기기", "방산", "조선", "로봇", "가상자산", "건설·부동산", "원전", "수소", "우주항공", "신재생에너지", "화장품", "반도체"]:
    th = T[tn]
    for rk in ["kr", "us", "cn", "tw", "jp"]:
        r = R[rk]; words = th.get(r["words"]) or []
        if not words: continue
        items, sat = ns.fetch_theme(r, words); time.sleep(0.5)
        if items is None: print("fail", tn, rk); continue
        ok, rej = [], []
        seen = set()
        for it in items:
            pub = it.get("published")
            if not pub or pub.astimezone(nb.KST).strftime("%Y-%m-%d") not in live: continue
            t = it["title"]
            if nb.EXCLUDE.search(t) or nb.is_blocked(it["source"], it.get("src_url", "")): continue
            if not nb.is_relevant(th, t): rej.append(t); continue
            k = nb.title_key(t)[:40]
            if k in seen: continue
            seen.add(k); ok.append(t)
        out["sample"][f"{tn}|{rk}"] = random.sample(ok, min(10, len(ok)))
        out["reject"][f"{tn}|{rk}"] = [len(items), len(ok), len(rej), rej[:3]]
        print(f"## {tn}|{rk} 받음 {len(items)} · 셈 {len(ok)} · 관련없어 뺌 {len(rej)} · 상한 {sat}")
        for t in out["sample"][f"{tn}|{rk}"]: print("   ·", t[:110])

print("=== B. 검색 시간 창 ===")
for tn, rk in [("AI", "us"), ("금융", "us"), ("가상자산", "kr"), ("AI", "kr"), ("건설·부동산", "kr")]:
    r = R[rk]; w = T[tn][r["words"]]
    row = {}
    for win in ["1d", "12h", "6h", "3h", "1h"]:
        its = ns._rss(nb.search_url(r, w, when=win)) or []
        ages = [(now - i["published"]).total_seconds() / 3600 for i in its if i.get("published")]
        row[win] = [len(its), round(max(ages), 1) if ages else None]
        time.sleep(0.5)
    out["window"][f"{tn}|{rk}"] = row
    print(tn, rk, row)

print("=== C. GDELT 대조 ===")
import news_history as nh
h = json.load(open("history.json"))
since = datetime.fromisoformat(h["since"]).date()
for tn, rk in [("반도체", "us"), ("2차전지", "cn"), ("반도체", "kr")]:
    words = dict(nh.THEMES)[tn]; code = dict(nh.REGIONS)[rk]
    a = datetime(2025, 9, 1).date(); b = datetime(2025, 9, 30).date()
    c = nh.fetch(words, code, a, b)
    if c is None: print("GDELT 실패", tn, rk); continue
    arr = h["s"].get(tn, {}).get(rk, [])
    diff = []
    for d, v in sorted(c.items()):
        i = (datetime.fromisoformat(d).date() - since).days
        sv = arr[i] if 0 <= i < len(arr) else "없음"
        if sv != v: diff.append((d, v, sv))
    print(f"{tn}|{rk} 2025-09: GDELT {sum(c.values())} / 저장 {sum(x or 0 for x in arr[(a-since).days:(b-since).days+1])} · 다른 날 {len(diff)} {diff[:4]}")
json.dump(out, open("probe_out.json", "w"), ensure_ascii=False)

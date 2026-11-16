# 임시 점검 스크립트 (점검 끝나면 지움)
import json, random, sys, time, re
from datetime import date, timedelta
import news_bot as nb
import news_stats as ns
import news_history as nh

random.seed(1)
print("===== 2. GDELT 대조")
h = json.load(open("history.json"))
since = date.fromisoformat(h["since"])
words = dict(nh.THEMES); codes = dict(nh.REGIONS)
for th, rk, y, m in [("반도체","kr",2023,3), ("방산","jp",2025,9), ("인터넷·플랫폼","cn",2024,2), ("가상자산","us",2021,12)]:
    a = date(y, m, 1); b = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1))
    c = nh.fetch(words[th], codes[rk], a, b)
    arr = h["s"][th][rk]
    diff = []
    d = a
    while d <= b:
        sv = arr[(d - since).days]; gv = (c or {}).get(d.isoformat())
        if sv != gv: diff.append((d.isoformat(), sv, gv))
        d += timedelta(days=1)
    print(f"## {th}|{rk} {y}-{m:02d}: 저장 합 {sum(x or 0 for x in arr[(a-since).days:(b-since).days+1])} · GDELT 합 {sum((c or {}).values()) if c else None} · 다른 날 {len(diff)}", diff[:10])


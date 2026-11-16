# 임시 점검 스크립트 (점검 끝나면 지움)
import json, random, sys, time, re
from datetime import date, timedelta
import news_bot as nb
import news_stats as ns
import news_history as nh

random.seed(1)
print("===== 1. 통계 표본")
TH = {t["name"]: t for t in ns.STAT_THEMES}
RG = {r["key"]: r for r in nb.REGIONS}
cells = [("AI","kr"),("AI","jp"),("금융","us"),("금융","tw"),("인터넷·플랫폼","us"),("자동차","cn"),
         ("우주항공","us"),("건설·부동산","kr"),("바이오·제약","kr"),("가상자산","world"),("원전","us"),("전력기기","us")]
for th, rk in cells:
    t, r = TH[th], RG[rk]
    items, sat = ns.fetch_theme(r, t[r["words"]], "6h")
    if items is None:
        print(f"## {th}|{rk}: 가져오기 실패"); continue
    ok, out = [], 0
    seen = set()
    for it in items:
        title = it["title"]
        if nb.EXCLUDE.search(title) or ns.SPAM.search(title) or nb.is_blocked(it["source"], it.get("src_url", "")) or not ns.relevant(t, title):
            out += 1; continue
        k = nb.title_key(title)[:40]
        if k in seen: continue
        seen.add(k); ok.append(f'{it["source"][:14]} | {title[:110]}')
    print(f"## {th}|{rk}: 받은 {len(items)} · 셈 {len(ok)} · 거름 {out} · 꽉참 {sat}")
    for x in random.sample(ok, min(25, len(ok))):
        print("   ", x)
    time.sleep(1)

print("===== 2. GDELT 대조")
h = json.load(open("history.json"))
since = date.fromisoformat(h["since"])
words = dict(nh.THEMES); codes = dict(nh.REGIONS)
for th, rk, y, m in [("바이오·제약","hk",2021,6), ("신재생에너지","us",2024,8), ("금융","us",2026,7)]:
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

print("===== 3. 번역 시험")
for s in ["Tech Stocks Slide as Nvidia, Anthropic Tests Await: Markets Wrap",
          "Asian shares fall before Nvidia earnings, Anthropic IPO test tech rally",
          "Stock Futures Slip Ahead of Pivotal Week for AI Trade With Nvidia, Anthropic in Focus",
          "黃仁勳跌落神壇！Anthropic IPO超額認購近7倍 華爾街押注AI淘金新主角",
          "Dow, S&P 500, Nasdaq Futures Edge Lower As Markets Brace For Nvidia Earnings, Anthropic IPO, Fed Minutes: SMMT, NBIS, HELP, MSTR In Focus",
          "Anthropic Is About to Become the World's Most Important AI Stock"]:
    nb._translate_cache.pop(s, None)
    print("  ", s, "\n   →", nb.translate_ko(s))
print("===== 4. 속보 표시 시험")
for s in ["ランドネット[2991]：2026年10月度 月次実績速報 2026年11月16日(適時開示)", "【速報】日経平均、一時1000円超下落", "決算速報：トヨタ", "株価速報 日経平均"]:
    print("  ", bool(nb.GLOBAL_BREAKING_MARK.search(s)), s)

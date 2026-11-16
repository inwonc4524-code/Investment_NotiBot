# 임시 검증: 고친 집계가 제대로 세는지 실제 자료로 다시 확인 (검증 후 삭제)
import json, random, time
from datetime import datetime, timedelta
import news_bot as nb, news_stats as ns, news_history as nh
random.seed(2)
now = datetime.now(nb.KST)
live = {now.strftime("%Y-%m-%d"), (now - timedelta(days=1)).strftime("%Y-%m-%d")}
R = {r["key"]: r for r in nb.REGIONS}; T = {t["name"]: t for t in ns.STAT_THEMES}
def count(tn, rk, when):
    th = T[tn]; r = R[rk]; items, sat = ns.fetch_theme(r, th[r["words"]], when); time.sleep(0.5)
    ok, seen = [], set()
    for it in items or []:
        pub = it.get("published")
        if not pub or pub.astimezone(nb.KST).strftime("%Y-%m-%d") not in live: continue
        t = it["title"]
        if nb.EXCLUDE.search(t) or ns.SPAM.search(t) or nb.is_blocked(it["source"], it.get("src_url", "")) or not ns.relevant(th, t): continue
        k = nb.title_key(t)[:40]
        if k in seen: continue
        seen.add(k); ok.append(t)
    return ok, sat
print("=== 검증 1: 고친 칸 표본 ===")
for tn, rk in [("인터넷·플랫폼","jp"),("방산","cn"),("방산","tw"),("원전","us"),("2차전지","tw"),("2차전지","jp"),("조선","cn"),("건설·부동산","kr"),("엔터","jp"),("AI","jp"),("로봇","tw"),("수소","us")]:
    ok, sat = count(tn, rk, "1d")
    print(f"## {tn}|{rk} 셈 {len(ok)}")
    for t in random.sample(ok, min(12, len(ok))): print("   ·", t[:100])
print("=== 검증 2: 시간 창 효과 (24시간 1번 vs 4시간 창) ===")
for tn, rk in [("금융","us"),("건설·부동산","us"),("바이오·제약","us"),("게임","kr"),("화장품","kr"),("반도체","us")]:
    a, sa = count(tn, rk, "1d"); b, sb = count(tn, rk, "4h")
    print(f"{tn}|{rk}: 24시간 창 {len(a)}건(상한 {sa}) · 4시간 창 {len(b)}건(상한 {sb}) → 4시간 창으로 24시간이면 약 {len(b)*6}건 추정")
print("=== 검증 3: GDELT 저장값 대조 ===")
h = json.load(open("history.json")); since = datetime.fromisoformat(h["since"]).date()
nh.GAP = 12
for tn, rk, y, m in [("반도체","kr",2025,9),("2차전지","cn",2025,6),("AI","us",2026,3),("로봇","cn",2025,11)]:
    words = dict(nh.THEMES)[tn]; code = dict(nh.REGIONS)[rk]
    a = datetime(y, m, 1).date(); b = (datetime(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)).date()
    c = None
    for _ in range(3):
        c = nh.fetch(words, code, a, b)
        if c is not None: break
        time.sleep(30)
    if c is None: print("GDELT 실패", tn, rk); continue
    arr = h["s"].get(tn, {}).get(rk, [])
    if not arr: print(f"{tn}|{rk}: 아직 안 받은 칸"); continue
    diff = [(d, v, arr[(datetime.fromisoformat(d).date() - since).days]) for d, v in sorted(c.items()) if arr[(datetime.fromisoformat(d).date() - since).days] != v]
    print(f"{tn}|{rk} {y}-{m:02d}: GDELT {sum(c.values())} / 저장 {sum(x or 0 for x in arr[(a-since).days:(b-since).days+1])} · 다른 날 {len(diff)} {diff[:4]}")

# 임시 점검 스크립트 (점검 끝나면 지움)
import sys, json, time, calendar
from datetime import date
import news_bot as nb, news_stats as ns, news_history as nh
REG = {r["key"]: r for r in nb.REGIONS}
TH = {t["name"]: t for t in ns.STAT_THEMES}
cells = [("반도체","us"),("자동차","jp"),("가상자산","kr"),("방산","us"),("조선","cn"),("전력기기","kr"),("우주항공","sg"),("AI","kr"),("수소","jp"),("금융","us"),("인터넷·플랫폼","us"),
         ("엔터","kr"),("게임","us"),("바이오·제약","tw"),("원전","cn"),("화장품","jp"),("건설·부동산","hk"),("2차전지","us")]
if len(sys.argv) > 1 and sys.argv[1] == "stats":
    for th, rk in cells:
        r = REG[rk]; t = TH[th]
        items, sat = ns.fetch_theme(r, t[r["words"]], "12h")
        if items is None:
            print("## FAIL", th, rk); continue
        keep, drop = [], []
        for it in items:
            title = it["title"]
            bad = nb.EXCLUDE.search(title) or ns.SPAM.search(title) or ns.SHOP.search(title) or (it.get("source") or "").strip().lower() in ns.STAT_SRC_SKIP or nb.is_blocked(it["source"], it.get("src_url", ""))
            (keep if (not bad and ns.relevant(t, title)) else drop).append(f'{title} [{it["source"]}]')
        print(f"## {th}|{rk} 전체 {len(items)} 셈 {len(keep)} 버림 {len(drop)} 상한 {sat}")
        for x in keep[:30]: print("  +", x)
        for x in drop[:8]: print("  -", x)
        time.sleep(1)
else:
    TW = dict(nh.THEMES); RC = dict(nh.REGIONS)
    h = json.load(open("history.json"))
    for th, rk, y, m in [("화장품","sg",2022,10),("AI","jp",2026,10),("가상자산","jp",2022,1)]:
        a = date(y, m, 1); b = date(y, m, calendar.monthrange(y, m)[1])
        c = nh.fetch(TW[th], RC[rk], a, b)
        arr = h["s"][th][rk]; diff = 0; n = 0
        if c is None: print("## GDELT FAIL", th, rk, y, m); continue
        for d in range((b - a).days + 1):
            dd = date.fromordinal(a.toordinal() + d)
            saved = arr[(dd - nh.SINCE).days]; got = c.get(dd.isoformat())
            n += 1
            if saved != got:
                diff += 1; print("   차이", dd, "저장", saved, "GDELT", got)
        print(f"## GDELT {th}|{rk} {y}-{m:02d}: {n}일 중 다른 날 {diff}, 합 저장 {sum(x or 0 for x in arr[(a-nh.SINCE).days:(b-nh.SINCE).days+1])} / GDELT {sum(c.values())}")

# 임시 점검 스크립트 (점검 끝나면 지움)
import sys, json, time, calendar
from datetime import date
import news_bot as nb, news_stats as ns, news_history as nh
REG = {r["key"]: r for r in nb.REGIONS}
TH = {t["name"]: t for t in ns.STAT_THEMES}
cells = [("금융","us"),("게임","us"),("인터넷·플랫폼","us"),("자동차","jp"),("반도체","kr"),("AI","us"),("방산","kr"),("조선","kr"),("전력기기","us"),("바이오·제약","us"),("가상자산","us"),("엔터","jp"),("화장품","kr"),("원전","us"),("우주항공","us"),("2차전지","kr"),("건설·부동산","cn"),("수소","kr"),("AI","cn"),("반도체","tw"),("로봇","us"),("신재생에너지","jp")]
if len(sys.argv) > 1 and sys.argv[1] == "stats":
    for th, rk in cells:
        r = REG[rk]; t = TH[th]
        items, sat = ns.fetch_theme(r, t[r["words"]], "12h")
        if items is None:
            print("## FAIL", th, rk); continue
        keep, drop = [], []
        for it in items:
            title = it["title"]
            bad = nb.EXCLUDE.search(title) or ns.SPAM.search(title) or ns.SHOP.search(title) or ns.NOT_NEWS.search(title) or (it.get("source") or "").strip().lower() in ns.STAT_SRC_SKIP or nb.is_blocked(it["source"], it.get("src_url", ""))
            (keep if (not bad and ns.relevant(t, title)) else drop).append(f'{title} [{it["source"]}]')
        print(f"## {th}|{rk} 전체 {len(items)} 셈 {len(keep)} 버림 {len(drop)} 상한 {sat}")
        for x in keep[:30]: print("  +", x)
        for x in drop[:8]: print("  -", x)
        time.sleep(1)
else:
    TW = dict(nh.THEMES); RC = dict(nh.REGIONS)
    h = json.load(open("history.json"))
    for th, rk, y, m in [("반도체","kr",2024,3),("원전","jp",2023,11)]:
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

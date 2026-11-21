import json, sys, time, re
from datetime import date, timedelta
import news_bot as nb, news_stats as ns, news_history as nh
CELLS = sys.argv[1].split(",")
for cell in CELLS:
    tn, rk = cell.split("|")
    theme = next(t for t in ns.STAT_THEMES if t["name"] == tn)
    region = next(r for r in nb.REGIONS if r["key"] == rk)
    items, sat = ns.fetch_theme(region, theme.get(region["words"]) or [], "1d")
    print(f"\n## {cell} n={len(items or [])} sat={sat}")
    for it in (items or [])[:400]:
        t = it["title"]; src = (it.get("source") or "")
        why = ("EXCL" if nb.EXCLUDE.search(t) else "SPAM" if ns.SPAM.search(t) else "SHOP" if ns.SHOP.search(t)
               else "NOTNEWS" if ns.NOT_NEWS.search(t) else "SRC" if src.strip().lower() in ns.STAT_SRC_SKIP
               else "BLOCK" if nb.is_blocked(src, it.get("src_url", "")) else "NOTREL" if not ns.relevant(theme, t) else "COUNT")
        print(f"  {why:7} | {t[:150]} | {src[:30]}")
    time.sleep(1)
h = json.load(open("history.json"))
since = date.fromisoformat(h["since"])
for spec in sys.argv[2].split(","):
    tn, rk, ym = spec.split("|")
    words = dict(nh.THEMES)[tn]; code = dict(nh.REGIONS)[rk]
    y, m = map(int, ym.split("-")); s = date(y, m, 1); e = (date(y + m // 12, m % 12 + 1, 1) - timedelta(days=1))
    got = nh.fetch(words, code, s, e)
    arr = h["s"][tn][rk]
    if got is None:
        print("GDELT", spec, "fail"); continue
    diff = []
    d = s
    while d <= e:
        a = arr[(d - since).days]; b = got.get(d.isoformat())
        if a != b: diff.append((d.isoformat(), a, b))
        d += timedelta(days=1)
    print("GDELT", spec, "days", (e - s).days + 1, "diff", len(diff), diff[:5], "sum", sum(got.values()))

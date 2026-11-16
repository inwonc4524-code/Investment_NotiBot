import requests, time, json, re
G="https://api.gdeltproject.org/api/v2/doc/doc"
def g(q, s="20250101000000", e="20251231000000", mode="timelinevolraw"):
    for i in range(4):
        r=requests.get(G, params={"query":q,"mode":mode,"format":"json","startdatetime":s,"enddatetime":e}, timeout=60)
        if r.status_code==200 and r.text.strip().startswith("{"): return r.json()
        print("  retry", r.status_code, r.text[:120]); time.sleep(8)
for q in ["semiconductor sourcecountry:KS", "semiconductor sourcecountry:US", "(semiconductor OR chipmaker) sourcecountry:CH",
          "반도체", "semiconductor sourcelang:korean", "robot sourcecountry:JA"]:
    j=g(q); time.sleep(6)
    if not j: print(q, "FAIL"); continue
    tl=j.get("timeline",[])
    for s in tl:
        d=s["data"]; print(q, "|", s.get("series"), "points", len(d), "first", d[:2], "last", d[-1:])
        tot=sum(x["value"] for x in d); print("   sum", tot, "sample norm", d[100].get("norm") if len(d)>100 else "")
# Google News 과거 날짜 확인
for q in ["반도체 after:2025-03-03 before:2025-03-04", "semiconductor after:2025-03-03 before:2025-03-04"]:
    hl = "ko" if "반도체" in q else "en-US"; gl = "KR" if hl=="ko" else "US"
    r=requests.get("https://news.google.com/rss/search", params={"q":q,"hl":hl,"gl":gl,"ceid":f"{gl}:{hl.split('-')[0]}"}, timeout=30)
    items=re.findall(r"<pubDate>(.*?)</pubDate>", r.text)
    print("GNEWS", q, len(items), items[:3])

import json, time
import news_bot as nb
S = ["恒指走勢丨半日低收266點 京東插8%",
     "美股先升後急插2%，道指失守五萬點，納指創逾七個月低，港股今日預料低開逾200點。",
     "【美股收市】黑色星期五英偉達插14%傳遭SEC調查納指瀉5.3% 道指倒跌949點 AI拆倉潮Anthropic挫8.5%",
     "港股插水500點 科指跌3%", "插電式混合動力車銷量增長", "Anthropic rings Nasdaq opening bell ahead of stock-market debut | CNN Business"]
base_pre = dict(nb.GLOSSARY.get("pre") or {})
for label, extra in [("COMMITTED", {})]:
    nb.GLOSSARY["pre"] = dict(base_pre, **extra)
    nb._translate_cache.clear()
    print("\n#####", label)
    for s in S:
        print("  ", nb.translate_ko(s), "  <=", s[:50])
        time.sleep(0.5)

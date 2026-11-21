import json, time
import news_bot as nb
S = ["Anthropic rings Nasdaq opening bell ahead of stock-market debut | CNN Business",
     "Treasury Yields Rise Amid Anthropic Euphoria",
     "Nasdaq Dives 1,261 Points as Anthropic, AI Stocks Sink: Stock Market Today",
     "Anthropic shares fall a day after blockbuster IPO",
     "US Stock Futures Dip as Anthropic Premiere Disappoints Investors",
     "Anthropic starts trading on Wall Street",
     "Anthropic Tests Investors' Appetite",
     "Banks feast on ANT offering",
     "Anthropic Shares Slide After Banks Exercise 'Greenshoe'",
     "【美股收市】黑色星期五英偉達插14%傳遭SEC調查納指瀉5.3% 道指倒跌949點 AI拆倉潮Anthropic挫8.5%",
     "アンソロピック株急落、Anthropicの上場2日目",
     "OpenAI and Anthropic race to court enterprise customers"]
base_pre = dict(nb.GLOSSARY.get("pre") or {})
for label, extra in [("BASE", {}), ("CAPS", {"Anthropic": "ANTHROPIC"}), ("INC", {"Anthropic": "Anthropic Inc."}), ("AICO", {"Anthropic": "Anthropic AI"})]:
    nb.GLOSSARY["pre"] = dict(base_pre, **extra)
    nb.GLOSSARY["names"]["ANTHROPIC"] = "앤트로픽"
    nb._translate_cache.clear()
    print("\n#####", label)
    for s in S:
        print("  ", nb.translate_ko(s), "  <=", s[:50])
        time.sleep(0.5)

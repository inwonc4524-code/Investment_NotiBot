import time, news_bot as nb
S = ["“AI抛售”拖累金银铜；Anthropic数学家称证明黎曼猜想| 一周国际财经",
     "英特尔(INTC)跌3.59%，AMD跌6.18%，Anthropic(ANT)跌9.17%。",
     "【美股盘前】Anthropic跌近7%，上市首日开盘涨34%后回吐半数涨幅",
     "167年黎曼猜想被破解 數學家與Claude合作找出證明 Anthropic股價挫",
     "AI拆倉潮Anthropic挫8.5%", "Anthropic逼近发行价"]
import copy
base = copy.deepcopy(nb.GLOSSARY)
for label, rep in [("NOW", None), ("GONGSI", "Anthropic公司"), ("NAME", "Anthropic（Claude开发商）")]:
    nb.GLOSSARY = copy.deepcopy(base)
    if rep:
        nb.GLOSSARY["pre_hans"]["Anthropic"] = rep; nb.GLOSSARY["pre_hant"]["Anthropic"] = rep.replace("发", "發")
    nb._translate_cache.clear(); print("#####", label)
    for s in S:
        print("  ", nb.translate_ko(s), " <=", s[:40]); time.sleep(0.5)

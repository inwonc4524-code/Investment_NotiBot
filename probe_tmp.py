# 임시 점검: AI 지시문(기준 반영) 비교 + 판정 규칙 비교 — 점검 후 삭제
import json, time, sentiment as se
g = json.load(open("sentiment_gold.json"))
D = g["set3"] + g["set4"]; T = [t for t, _ in D]; G = [l for _, l in D]
lex = [se.lexicon_label(t) for t in T]
NEW = ("You judge stock-market news headlines (any language: Korean, English, Chinese, Japanese) for investors in the "
       "companies, sector or market the headline is about. positive = good for their share prices (prices or index rising, "
       "strong or better-than-expected earnings, losses narrowing, new orders or contracts, approvals, demand growth, "
       "subsidies or easing rules, upgrades, buybacks, optimistic outlook). negative = bad for them (prices falling, "
       "selloff or correction, weak or worse-than-expected earnings, losses, cancellations, halts or delays, recalls, fires "
       "or accidents, lawsuits, probes, sanctions, tariffs or export curbs, downgrades, rate hikes, bubble or recession "
       "warnings, fears). neutral = plain facts with no clear good or bad effect (events, appointments, schedules, product "
       "or technology introductions, mixed news, questions, stock-pick lists, press releases). Judge by the main point of "
       "the headline. If unsure, answer neutral. Answer with one word: positive, negative, or neutral.")
res = {}
for name, sysmsg in [("지금 지시문", se.SYSTEM), ("기준 넣은 지시문", NEW)]:
    se.SYSTEM = sysmsg
    t0 = time.time(); ai = se.model_labels(T); sec = time.time() - t0
    ag = [i for i in range(len(T)) if ai[i] == lex[i]]
    ab = [i for i in range(len(T)) if lex[i] == "u" and ai[i] != "u"]    # 낱말이 신호를 못 찾았을 때 AI 가 고른 것
    print(f"[{name}] AI 혼자 {sum(a==b for a,b in zip(ai,G))}/{len(T)} · 낱말과 같음 {len(ag)} 중 정답 {sum(ai[i]==G[i] for i in ag)} "
          f"· 낱말 중립·AI 긍부정 {len(ab)} 중 AI 정답 {sum(ai[i]==G[i] for i in ab)} · {sec:.0f}초", flush=True)
    res[name] = ai
print("낱말 혼자", sum(a == b for a, b in zip(lex, G)), "/", len(T))
json.dump({"lex": lex, **res}, open("probe_res.json", "w"))

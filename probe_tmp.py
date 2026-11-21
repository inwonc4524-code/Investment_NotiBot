# 임시 검증: 실제 판정 과정(낱말 + Qwen)을 새 정답 표본(set4)으로 확인 — 검증 후 삭제
import json, time, sentiment as se
g = json.load(open("sentiment_gold.json"))
for name in ["set3", "set4"]:
    D = g[name]; T = [t for t, _ in D]; G = [l for _, l in D]
    t0 = time.time(); fin = se.judge(T); mod = se.model_labels(T); lex = [se.lexicon_label(t) for t in T]
    agree = [i for i in range(len(T)) if fin[i] != "x"]
    print(f"[{name}] 낱말 {sum(a==b for a,b in zip(lex,G))}/60 · AI {sum(a==b for a,b in zip(mod,G))}/60 · "
          f"둘이 같음 {len(agree)}/60 중 정답 {sum(fin[i]==G[i] for i in agree)} · 판정다름 {60-len(agree)} · {time.time()-t0:.0f}초", flush=True)
    for i in range(len(T)):
        if fin[i] != "x" and fin[i] != G[i]:
            print(f"   틀림: 판정 {fin[i]} 정답 {G[i]} | {T[i][:80]}")

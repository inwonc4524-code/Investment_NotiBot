# 임시 점검: 무료로 쓸 수 있는 판정 방법들의 정확도 비교 (실제 기사 120건, 사람이 정답을 붙임) — 점검 후 삭제
import json, time, torch, sentiment as se
S = json.load(open("probe_sets.json")); D = S["set2"] + S["set3"]
titles = [t for t, _ in D]; gold = [g for _, g in D]
torch.set_num_threads(4)
res = {}
def score(name, pred, sec):
    ok = sum(a == b for a, b in zip(pred, gold)); res[name] = pred
    print(f"[{name}] 정확도 {ok}/{len(gold)} ({ok*100//len(gold)}%) · {sec:.1f}초", flush=True)

t0 = time.time(); score("낱말", [se.lexicon_label(t) for t in titles], time.time() - t0)

from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
# (b) 감정 모델 — 확률 부호로
t0 = time.time()
p = pipeline("text-classification", model="tabularisai/multilingual-sentiment-analysis", top_k=None, truncation=True, max_length=96)
out = []
for r in p(titles, batch_size=32):
    d = {x["label"].lower(): x["score"] for x in r}
    s = d.get("very positive", 0) + d.get("positive", 0) - d.get("very negative", 0) - d.get("negative", 0)
    out.append("p" if s > 0.2 else "n" if s < -0.2 else "u")
score("감정모델", out, time.time() - t0)

# (c) 다국어 NLI 영(0)샷
t0 = time.time()
z = pipeline("zero-shot-classification", model="MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7")
labs = ["good news for investors", "bad news for investors", "neutral news"]
out = []
for r in z(titles, candidate_labels=labs, hypothesis_template="This headline is {}.", batch_size=16):
    top = r["labels"][0]; out.append("p" if top.startswith("good") else "n" if top.startswith("bad") else "u")
score("NLI", out, time.time() - t0)

# (d) 작은 무료 AI 언어모델 (Qwen2.5 1.5B Instruct) — 다음 낱말 확률로 고르기
for mid in ["Qwen/Qwen2.5-1.5B-Instruct", "Qwen/Qwen2.5-3B-Instruct"]:
    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(mid); tok.padding_side = "left"
    m = AutoModelForCausalLM.from_pretrained(mid, torch_dtype=torch.float32); m.eval()
    cand = {"p": "positive", "n": "negative", "u": "neutral"}
    ids = {k: tok.encode(v, add_special_tokens=False)[0] for k, v in cand.items()}
    def prompt(t):
        msg = [{"role": "system", "content": "You classify stock-market news headlines (any language) by whether the news is good or bad for the companies, sector or stock market involved. Answer with one word: positive, negative, or neutral."},
               {"role": "user", "content": f"Headline: {t}\nAnswer:"}]
        return tok.apply_chat_template(msg, tokenize=False, add_generation_prompt=True)
    out = []
    with torch.no_grad():
        for i in range(0, len(titles), 16):
            enc = tok([prompt(t) for t in titles[i:i+16]], return_tensors="pt", padding=True)
            lg = m(**enc).logits[:, -1, :]
            for row in lg:
                out.append(max(ids, key=lambda k: row[ids[k]].item()))
    score(mid.split("/")[1], out, time.time() - t0)
    del m

names = list(res)
for a in range(len(names)):
    for b in range(a + 1, len(names)):
        A, B = res[names[a]], res[names[b]]
        agree = [i for i in range(len(gold)) if A[i] == B[i]]
        ok = sum(A[i] == gold[i] for i in agree)
        pn = [i for i in agree if A[i] != "u"]
        print(f"  {names[a]} + {names[b]}: 같음 {len(agree)}/{len(gold)} · 그중 정답 {ok} ({ok*100//max(1,len(agree))}%) · 긍정/부정으로 셈 {len(pn)}건 중 정답 {sum(A[i]==gold[i] for i in pn)}")
json.dump(res, open("probe_res.json", "w"))
print("완료")

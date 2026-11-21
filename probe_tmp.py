# 임시 점검 2: 작은 AI 언어모델 속도 줄이기 (0.5B / 1.5B 8비트) 정확도·속도 — 점검 후 삭제
import json, time, torch, sentiment as se
S = json.load(open("probe_sets.json")); D = S["set2"] + S["set3"]
titles = [t for t, _ in D]; gold = [g for _, g in D]
torch.set_num_threads(4)
from transformers import AutoTokenizer, AutoModelForCausalLM
lex = [se.lexicon_label(t) for t in titles]
SYS = "Classify the stock news headline as good, bad, or neutral for the companies or market. One word: positive, negative, or neutral."
def run(mid, quant):
    tok = AutoTokenizer.from_pretrained(mid); tok.padding_side = "left"
    m = AutoModelForCausalLM.from_pretrained(mid, torch_dtype=torch.float32); m.eval()
    if quant:
        m = torch.ao.quantization.quantize_dynamic(m, {torch.nn.Linear}, dtype=torch.qint8)
    ids = {k: tok.encode(v, add_special_tokens=False)[0] for k, v in {"p": "positive", "n": "negative", "u": "neutral"}.items()}
    P = lambda t: tok.apply_chat_template([{"role": "system", "content": SYS}, {"role": "user", "content": t}], tokenize=False, add_generation_prompt=True)
    out = []; t0 = time.time()
    with torch.no_grad():
        for i in range(0, len(titles), 16):
            enc = tok([P(t) for t in titles[i:i+16]], return_tensors="pt", padding=True)
            lg = m(**enc).logits[:, -1, :]
            out += [max(ids, key=lambda k: r[ids[k]].item()) for r in lg]
    sec = time.time() - t0
    ok = sum(a == b for a, b in zip(out, gold))
    ag = [i for i in range(len(gold)) if out[i] == lex[i]]
    print(f"[{mid.split('/')[1]}{' 8비트' if quant else ''}] 정확도 {ok}/120 · {sec:.0f}초 ({sec/len(titles):.2f}초/건) · 낱말과 같음 {len(ag)} 중 정답 {sum(out[i]==gold[i] for i in ag)} · 표본3만 {sum(a==b for a,b in zip(out[60:],gold[60:]))}/60", flush=True)
    return out
run("Qwen/Qwen2.5-0.5B-Instruct", False)
run("Qwen/Qwen2.5-1.5B-Instruct", True)
run("Qwen/Qwen2.5-1.5B-Instruct", False)
print("완료")

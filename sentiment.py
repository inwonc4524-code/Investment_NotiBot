# -*- coding: utf-8 -*-
"""
기사 제목 → 긍정(p) · 부정(n) · 중립(u) 판정 — 돈이 안 드는 두 가지 방법으로 따로 판정하고 서로 맞춰 봄(교차 검증)

① 낱말 판정 (lexicon_label): 경제 기사에 자주 나오는 좋은 말·나쁜 말 목록(한국어·영어·중국어·일본어)으로 점수
   - '적자 축소', 'loss narrows' 처럼 나쁜 말이 들어 있어도 좋은 소식인 표현은 먼저 찾아서 따로 셈
② AI 판정 (model_labels): 무료 공개 AI 언어모델 Qwen2.5-1.5B-Instruct (한·영·중·일 모두 이해)
   - GitHub Actions 컴퓨터에서 직접 돌려요(돈·열쇠 필요 없음). 모델 파일은 처음 한 번 받아 두고 재사용
   - 한 건에 약 2초 → 한 번 실행에 정해 둔 시간만 판정하고, 남은 건 다음 실행에서 이어서

최종: 두 판정이 같으면 그 판정, 다르면 'x'(판정 다름) — 확실한 것만 긍정·부정·중립으로 셈
"""
import re

# ── ① 낱말 판정 ─────────────────────────────────────────
# 뒤집히는 표현(나쁜 말 + 좋아짐 / 좋은 말 + 나빠짐)은 먼저 찾아서 점수 주고 지움
FLIP_POS = [
    "적자 축소", "적자폭 축소", "적자 폭 축소", "적자 감소", "손실 축소", "손실 감소", "적자 탈출", "흑자 전환", "흑자전환",
    "우려 해소", "우려 완화", "불확실성 해소", "하락 멈", "낙폭 축소", "반등", "규제 완화", "관세 인하", "관세 유예",
    "loss narrows", "narrower loss", "narrowed loss", "losses narrow", "beats estimates", "beat estimates", "tops estimates",
    "fears ease", "concerns ease", "eases concerns", "rebounds", "rebound", "recovers", "recovery",
    "亏损收窄", "虧損收窄", "扭亏", "扭虧", "轉虧為盈", "转亏为盈", "止跌", "反弹", "反彈",
    "赤字縮小", "黒字転換", "黒字化", "反発", "懸念後退", "上方修正",
]
FLIP_NEG = [
    "흑자 축소", "이익 감소", "성장 둔화", "상승 제한", "상승폭 축소", "수요 둔화", "실적 부진", "어닝 쇼크", "어닝쇼크",
    "적자 확대", "적자전환", "적자 전환", "손실 확대", "하향 조정", "목표가 하향",
    "misses estimates", "missed estimates", "falls short", "cuts guidance", "cuts forecast", "lowers guidance",
    "lowers forecast", "profit warning", "growth slows", "demand slows", "loss widens", "wider loss",
    "盈利下滑", "獲利衰退", "转亏", "轉虧", "下修", "下调", "下調",
    "下方修正", "減益", "赤字転落", "赤字拡大",
]
POS = [
    # 한국어
    "급등", "상승", "강세", "신고가", "최고치", "사상 최고", "최대 실적", "호실적", "실적 개선", "깜짝 실적", "어닝 서프라이즈",
    "흑자", "수주", "공급 계약", "계약 체결", "승인", "허가 획득", "돌파", "호조", "수혜", "순항", "회복", "상향",
    "자사주 매입", "배당 확대", "증액", "랠리", "훈풍", "청신호", "질주", "껑충", "날개", "신기록", "최대치", "기대감",
    "성장", "증가", "확대", "늘어", "늘려", "투자 유치", "상장 성공",
    # 영어
    "surge", "surges", "soar", "soars", "jump", "jumps", "rally", "rallies", "gain", "gains", "rise", "rises", "rose",
    "climb", "climbs", "record high", "all-time high", "beats", "tops", "upgrade", "upgraded", "upgrades",
    "raises guidance", "raises forecast", "boosts", "boost", "outperform", "wins", "win", "approval", "approved",
    "strong demand", "bullish", "breakthrough", "expands", "expansion", "record profit", "profit rises", "buyback",
    "upbeat", "optimism", "optimistic", "record sales", "record revenue",
    # 중국어 (간체·번체)
    "大涨", "大漲", "上涨", "上漲", "涨停", "漲停", "走强", "走強", "新高", "盈利增长", "獲利成長", "增长", "成長",
    "订单", "訂單", "中标", "得標", "获批", "獲批", "利好", "利多", "看好", "突破", "回升", "强劲", "強勁", "飙升", "飆升",
    # 일본어
    "上昇", "急騰", "続伸", "最高値", "上場来高値", "増益", "黒字", "受注", "承認", "好調", "増配", "自社株買い", "好決算",
    "過去最高", "大幅高", "拡大", "%高", "％高", "買い",
    # 2026-11-22 실제 기사 표본에서 빠졌던 말
    "기회", "↑", "增", "崛起", "提速", "拐点", "拐點", "订光", "訂光", "降本", "增利", "热销", "熱銷", "供不应求", "供不應求",
]
NEG = [
    # 한국어
    "급락", "하락", "약세", "폭락", "신저가", "적자", "손실", "부진", "감소", "둔화", "악화", "우려", "리콜", "소송",
    "제재", "규제", "압수수색", "파산", "부도", "철수", "중단", "지연", "취소", "감산", "하향", "경고", "쇼크", "위기",
    "타격", "먹구름", "빨간불", "적신호", "추락", "곤두박질", "불안", "화재", "폭발", "사고", "해킹", "유출", "횡령",
    "줄어", "줄였", "털썩", "뚝", "급감", "폭탄 관세", "관세 폭탄", "구조조정", "감원", "희망퇴직",
    # 영어
    "plunge", "plunges", "plummet", "plummets", "slump", "slumps", "tumble", "tumbles", "sink", "sinks", "fall", "falls",
    "fell", "drop", "drops", "decline", "declines", "slide", "slides", "loss", "losses", "miss", "misses", "downgrade",
    "downgraded", "lawsuit", "sued", "sues", "probe", "investigation", "recall", "recalls", "ban", "bans", "sanction",
    "sanctions", "layoffs", "job cuts", "bankruptcy", "default", "warning", "warns", "delay", "delays", "halt", "halts",
    "suspend", "suspends", "crash", "fears", "concerns", "worries", "bearish", "selloff", "sell-off", "weak", "weaker",
    "slowdown", "fraud", "hack", "breach", "fire", "explosion", "tariff", "tariffs",
    # 중국어
    "大跌", "下跌", "跌停", "走弱", "暴跌", "新低", "亏损", "虧損", "下滑", "减少", "減少", "利空", "制裁", "调查", "調查",
    "召回", "诉讼", "訴訟", "裁员", "裁員", "破产", "破產", "暂停", "暫停", "警告", "衰退", "疲软", "疲軟", "拖累", "重挫",
    # 일본어
    "下落", "急落", "続落", "安値", "赤字", "不振", "懸念", "減少", "縮小", "停止", "延期", "撤退", "制裁", "リコール",
    "破綻", "大幅安", "減収", "低迷",
    # 2026-11-22 실제 기사 표본에서 빠졌던 말
    "correction", "fear", "panic", "rout", "turmoil", "batters", "batter", "worst", "crisis", "hawkish", "rate hike",
    "breaking point", "turmoil", "slides", "sell off", "lower",
    "검은 금요일", "패닉", "↓", "투매", "공포", "폭락", "조정 진입", "약세장", "손절",
    "跌", "瀉", "泻", "挫", "崩", "蒸發", "蒸发", "拋售", "抛售", "恐慌", "加息", "失守", "血流成河", "大火", "自燃",
    "发不出", "發不出", "欠薪", "暴雷", "爆雷", "低迷",
    "売り圧力", "失速", "%安", "％安", "売り",
    "反落", "跌破", "波动加剧", "波動加劇",
]


def _norm(t):
    return " " + re.sub(r"\s+", " ", (t or "").lower()) + " "


def _count(t, words):
    n = 0
    for w in words:
        wl = w.lower()
        if re.search(r"[a-z]", wl):          # 영어는 낱말 단위로 (예: 'win' 이 'wind' 에 안 걸리게)
            pat = r"(?<![a-z])" + re.escape(wl) + r"(?![a-z])"
            c = len(re.findall(pat, t))
            if c:
                t = re.sub(pat, " ", t)
        else:
            c = t.count(wl)
            if c:
                t = t.replace(wl, " ")
        n += c
    return n, t


NEUTRAL = ["增资", "增資", "증자"]       # 좋은 말 글자를 품었지만 뜻은 중립인 말 → 먼저 지움


def lexicon_label(title):
    """제목 → 'p' / 'n' / 'u'"""
    t = _norm(title)
    _, t = _count(t, NEUTRAL)
    fp, t = _count(t, FLIP_POS)
    fn, t = _count(t, FLIP_NEG)
    p, t = _count(t, POS)
    n, t = _count(t, NEG)
    score = (fp + p) - (fn + n)
    return "p" if score > 0 else "n" if score < 0 else "u"


# ── ② AI 모델 판정 ─────────────────────────────────────
# 무료 공개 AI 언어모델 Qwen2.5-1.5B-Instruct(알리바바, Apache 2.0)를 GitHub Actions 컴퓨터에서 직접 돌림.
# 2026-11-22 실제 기사 120건 시험: 혼자 71% · 낱말 판정과 같을 때 93% 정답 (감정모델·NLI·0.5B·8비트보다 나음)
MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"
SYSTEM = ("You classify stock-market news headlines (any language) by whether the news is good or bad for the "
          "companies, sector or stock market involved. Answer with one word: positive, negative, or neutral.")
_model = {}


def _load():
    if "m" in _model:
        return _model["m"]
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        torch.set_num_threads(4)
        tok = AutoTokenizer.from_pretrained(MODEL_NAME)
        tok.padding_side = "left"
        m = AutoModelForCausalLM.from_pretrained(MODEL_NAME, torch_dtype=torch.float32)
        m.eval()
        ids = {k: tok.encode(v, add_special_tokens=False)[0] for k, v in {"p": "positive", "n": "negative", "u": "neutral"}.items()}
        _model["m"] = (torch, tok, m, ids)
    except Exception as e:                     # 모델을 못 받으면 이번엔 판정 보류('?') → 다음 실행에서 다시
        print(f"  ! 판정 AI 모델을 못 불러옴: {e}")
        _model["m"] = None
    return _model["m"]


def model_labels(titles, deadline=None):
    """제목 목록 → ['p'|'n'|'u'|None, ...] (시간이 다 되면 남은 건 None, 모델을 못 쓰면 None)"""
    import time
    mm = _load()
    if mm is None:
        return None
    torch, tok, m, ids = mm
    prompt = lambda t: tok.apply_chat_template(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Headline: {t}\nAnswer:"}],
        tokenize=False, add_generation_prompt=True)
    out = []
    with torch.no_grad():
        for i in range(0, len(titles), 16):
            if deadline and time.time() > deadline:
                out += [None] * (len(titles) - len(out))
                break
            enc = tok([prompt(t[:200]) for t in titles[i:i + 16]], return_tensors="pt", padding=True)
            lg = m(**enc).logits[:, -1, :]
            out += [max(ids, key=lambda k: r[ids[k]].item()) for r in lg]
    return out


def judge(titles, deadline=None):
    """제목 목록 → 최종 판정 목록. 두 판정이 같으면 그 판정, 다르면 'x', 아직 못 본 건 '?'(다음 실행에서 다시)"""
    if not titles:
        return []
    mod = model_labels(titles, deadline)
    if mod is None:
        return ["?"] * len(titles)
    return ["?" if b is None else (a if a == b else "x") for a, b in zip((lexicon_label(t) for t in titles), mod)]

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


# ── 2026-11-23 폭넓게 늘린 낱말·표현 (SENTIMENT_GUIDE.md 기준) ──
FLIP_POS += [
    "감소폭 축소", "하락폭 축소", "낙폭 만회", "손실 줄", "적자 줄", "적자폭 줄", "우려 불식", "악재 해소", "규제 해제",
    "제재 해제", "관세 철회", "관세 면제", "소송 승소", "리스크 해소", "예상 상회", "예상치 상회", "컨센서스 상회", "기대 이상",
    "fears ease", "worries ease", "eases fears", "ease concerns", "recovers from", "rebounds from", "bounce back",
    "bounces back", "lifts ban", "ban lifted", "tariff relief", "pauses tariffs", "tariffs paused", "wins lawsuit",
    "above expectations", "better than expected", "better-than-expected", "exceeds expectations", "tops forecasts",
    "跌幅收窄", "止跌回升", "减亏", "減虧", "超预期", "超預期", "优于预期", "優於預期",
    "下げ幅縮小", "予想上回る", "予想を上回",
]
FLIP_NEG += [
    "상승분 반납", "상승폭 축소", "흑자폭 축소", "기대 못 미쳐", "기대 이하", "예상 하회", "예상치 하회", "컨센서스 하회",
    "수주 취소", "목표가 하향", "투자의견 하향", "실적 악화", "수요 감소", "수요 부진",
    "gains erased", "erases gains", "wipes out gains", "gives up gains", "pares gains", "profit falls", "profit drops",
    "slower growth", "below expectations", "short of expectations", "worse than expected", "worse-than-expected",
    "cuts jobs", "cut jobs", "cuts outlook", "cut outlook", "cut forecast",
    "涨幅收窄", "漲幅收窄", "回吐涨幅", "抹去涨幅", "抹去年内涨幅", "涨幅全回吐", "漲幅全回吐", "转盈为亏", "由盈转亏",
    "不及预期", "不如預期", "低于预期", "低於預期",
    "上げ幅縮小", "伸び悩み", "利益減少", "予想下回る", "予想を下回",
    "적자 급증", "적자 증가", "손실 급증", "손실 증가", "难乐观", "難樂觀",
]
POS += [
    # 한국어
    "호재", "상승세", "오름세", "강세장", "상한가", "최고가", "역대 최대", "역대 최고", "사상 최대", "흑자 행진", "실적 호조",
    "매출 증가", "영업익 증가", "이익 증가", "순익 증가", "고성장", "수요 급증", "수요 증가", "주문 폭주", "품귀", "완판",
    "수주 잔고", "대규모 수주", "협력 확대", "파트너십", "지원 대상", "보조금", "세제 혜택", "규제 완화", "품목허가",
    "임상 성공", "목표가 상향", "투자의견 상향", "매수 추천", "비중 확대", "순매수", "자금 유입", "회복세", "턴어라운드",
    "개선", "호황", "슈퍼사이클", "붐", "탄력", "쑥", "급증", "사상 첫", "승소", "해소", "증설", "밝아", "밝은", "낙관",
    "상장 첫날", "선정", "유치", "강세",
    # 영어
    "soared", "surged", "jumped", "rallied", "gained", "climbed", "advanced", "rebounded", "highs", "outperforms",
    "topped", "exceeds", "exceeded", "raises", "raised", "lifts", "lifted", "overweight", "buy rating", "approves",
    "clears", "cleared", "won", "secures", "secured", "awarded", "contract", "orders surge", "new orders",
    "demand surges", "booming", "boom", "growth accelerates", "profit jumps", "revenue jumps", "record revenue",
    "turnaround", "milestone", "partnership", "boosted", "tailwind", "tailwinds", "upside", "strong",
    # 중국어
    "涨", "漲", "上扬", "上揚", "走高", "拉升", "飙涨", "飆漲", "大增", "激增", "翻倍", "历史新高", "歷史新高", "看涨", "看漲",
    "买入", "買進", "增持", "回购", "回購", "分红", "分紅", "签约", "簽約", "接单", "接單", "合作", "批准", "回暖", "复苏",
    "復甦", "业绩增长", "淨利成長", "净利增长", "景气", "景氣", "爆单", "爆單", "机遇", "機遇", "商机", "商機", "受惠",
    "受益", "红利", "紅利", "补贴", "補貼",
    # 일본어
    "高値", "年初来高値", "買われ", "増収", "最高益", "黒字化", "契約", "提携", "認可", "回復", "改善", "追い風", "期待",
    "恩恵", "需要増", "好感", "堅調", "強気", "格上げ", "引き上げ",
    "乐观", "樂觀", "强势", "強勢",
]
NEG += [
    # 한국어
    "악재", "하락세", "내림세", "하한가", "최저가", "역대 최저", "적자 지속", "매출 감소", "영업손실", "순손실", "감익",
    "역성장", "재고 증가", "공급 과잉", "가격 하락", "단가 하락", "출혈 경쟁", "계약 해지", "무산", "좌초", "연기", "차질",
    "가동 중단", "생산 중단", "셧다운", "파업", "결함", "불량", "사망", "부상", "피소", "고소", "고발", "기소", "구속",
    "조사 착수", "과징금", "벌금", "규제 강화", "관세 부과", "관세 인상", "수출 통제", "금지", "퇴출", "상장폐지", "거래정지",
    "배임", "분식", "유상증자", "블록딜", "매도 의견", "순매도", "자금 유출", "이탈", "매도세", "휘청", "비상", "경고등",
    "찬물", "충격", "침체", "법정관리", "워크아웃", "디폴트", "어둡", "비관", "붕괴", "축소", "반납",
    # 영어
    "plunged", "slumped", "tumbled", "sank", "slid", "dropped", "declined", "lost", "weakness", "downturn", "recession",
    "crashed", "bear market", "worry", "concern", "cancels", "canceled", "cancelled", "investigates", "fine", "fined",
    "penalty", "banned", "curbs", "restrictions", "export controls", "underweight", "sell rating", "missed",
    "disappoints", "disappointing", "shortfall", "writedown", "write-down", "impairment", "scandal", "outage", "strike",
    "headwind", "headwinds", "overvalued", "bubble", "pressure", "pressured", "struggles", "struggling", "woes",
    "wipeout", "wipe out", "wiped out", "lowest", "plummeted", "halted", "suspended", "delayed", "lays off",
    # 중국어
    "下挫", "走低", "跳水", "崩盘", "崩盤", "看空", "卖出", "賣出", "减持", "減持", "亏", "虧", "萎缩", "萎縮", "警示",
    "风险", "風險", "担忧", "擔憂", "危机", "危機", "泡沫", "禁令", "管制", "关税", "關稅", "罚款", "罰款", "停产", "停產",
    "停工", "违约", "違約", "火灾", "火災", "起火", "爆炸", "事故", "承压", "承壓", "压力", "壓力", "升息", "鹰派", "鷹派",
    # 일본어
    "年初来安値", "売られ", "最終赤字", "減配", "無配", "損失", "不安", "警戒", "逆風", "中止", "減産", "人員削減", "リストラ",
    "提訴", "規制強化", "関税", "不正", "火災", "事故", "格下げ", "引き下げ", "弱気", "暴落", "急反落", "利上げ",
    "火警", "燒了", "烧了",
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


NEUTRAL = ["增资", "增資", "증자", "화재 예방", "화재예방", "화재 감지", "사고 예방", "안전 강화"]       # 좋은 말 글자를 품었지만 뜻은 중립인 말 → 먼저 지움


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


# 두 판정이 다를 때 정하는 규칙 — Claude 가 실제 판정다름 기사 578건을 직접 판정해 본 결과로 정함 (2026-11-23)
#  · 낱말 중립 + AI 긍정 → 중립 (83% 가 중립. 작은 AI 는 회사 소식이면 대부분 긍정이라고 함)
#  · 낱말 중립 + AI 부정 → 부정 (62% 가 부정. 낱말이 못 찾은 나쁜 소식을 AI 가 잡음)
#  · 낱말 긍정 + AI 중립 → 중립 (71% 가 중립)
#  · 나머지(긍정↔부정이 엇갈리는 등)는 그대로 판정 다름 → Claude 가 검토
RESOLVE = {("u", "p"): "u", ("u", "n"): "n", ("p", "u"): "u"}


def combine(a, b):
    if b is None:
        return "?"
    if a == b:
        return a
    return RESOLVE.get((a, b), "x")


def judge_detail(titles, deadline=None):
    """제목 목록 → [(최종, 낱말, AI), ...]  최종: 같으면 그 판정, 다르면 규칙(RESOLVE)으로, 그래도 못 정하면 'x', 아직 못 본 건 '?'"""
    if not titles:
        return []
    mod = model_labels(titles, deadline)
    lex = [lexicon_label(t) for t in titles]
    if mod is None:
        return [("?", a, None) for a in lex]
    return [(combine(a, b), a, b) for a, b in zip(lex, mod)]


def judge(titles, deadline=None):
    """제목 목록 → 최종 판정 목록 (judge_detail 의 최종만)"""
    return [x[0] for x in judge_detail(titles, deadline)]

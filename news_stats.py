# -*- coding: utf-8 -*-
"""
📊 테마별 뉴스 통계 봇
- 증시 주요 테마 20개가 나라별로 하루에 뉴스가 몇 개 나왔는지 셉니다.
- 1시간마다 모아서 같은 기사는 한 번만 세고, 날짜(한국 시간)별로 쌓아요.
  (구글 뉴스 영어판·번체판은 나라끼리 같은 기사가 겹쳐서, 한 기사는 처음 잡힌 나라 한 곳에만 셈:
   한국 → 미국 → 중국 → 대만 → 홍콩 → 일본 → 싱가포르 → 세계 순)
- 매일 아침 어제 통계를 휴대폰으로 알려 주고, 뉴스 페이지의 📊 통계 탭에서 추이를 볼 수 있어요.

★ 테마나 검색어를 바꾸고 싶으면 아래 STAT_THEMES 만 고치면 됩니다.
   kr=한국어, en=영어(미국·싱가포르·세계), zh=번체(대만·홍콩), cn=간체(중국), ja=일본어
   기사 제목에 이 단어 중 하나라도 있어야 그 테마 기사로 셉니다.
"""
import hashlib
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

import news_bot as nb

STAT_THEMES = [
    {"name": "반도체",
     "kr": ["반도체", "HBM", "SK하이닉스", "파운드리", "메모리 반도체"],
     "en": ["semiconductor", "semiconductors", "chipmaker", "chip stocks", "HBM", "TSMC"],
     "zh": ["半導體", "晶片", "台積電", "記憶體"], "cn": ["半导体", "芯片", "存储芯片", "晶圆"],
     "ja": ["半導体", "メモリー", "ファウンドリー"]},
    {"name": "2차전지",
     "kr": ["2차전지", "이차전지", "배터리", "양극재", "리튬"],
     "en": ["EV battery", "batteries", "lithium", "battery maker", "cathode"],
     "zh": ["鋰電池", "動力電池", "儲能電池", "電池廠", "寧德時代", "正極材料"], "cn": ["动力电池", "锂电池", "宁德时代", "碳酸锂"],
     "ja": ["リチウムイオン電池", "車載電池", "全固体電池", "蓄電池", "電池材料"]},
    {"name": "AI",
     "kr": ["AI", "인공지능", "생성형"],
     "en": ["AI", "artificial intelligence", "generative AI", "OpenAI"],
     "zh": ["AI", "人工智慧", "生成式"], "cn": ["AI", "人工智能", "大模型", "算力"],
     "ja": ["AI", "人工知能", "生成AI"]},
    {"name": "로봇",
     "kr": ["로봇", "휴머노이드", "로보틱스"], "en": ["robot", "robots", "robotics", "humanoid"],
     "zh": ["機器人", "人形機器人"], "cn": ["机器人", "人形机器人"], "ja": ["ロボット", "ヒューマノイド"]},
    {"name": "바이오·제약",
     "kr": ["바이오", "제약", "신약", "임상", "셀트리온"],
     "en": ["biotech", "pharma", "pharmaceutical", "drugmaker", "FDA approval", "clinical trial"],
     "zh": ["生技", "製藥", "新藥"], "cn": ["生物医药", "创新药", "医药"], "ja": ["バイオ", "製薬", "新薬", "創薬"]},
    {"name": "방산",
     "kr": ["방산", "방위산업", "한화에어로스페이스", "LIG넥스원", "현대로템"],
     "en": ["defense stocks", "defense contractor", "defense spending", "arms deal", "Lockheed"],
     "zh": ["軍工", "國防產業", "國防工業", "軍購"], "cn": ["军工", "国防工业", "军工股", "军贸"], "ja": ["防衛産業", "防衛費", "防衛装備"]},
    {"name": "원전",
     "kr": ["원전", "원자력", "SMR", "두산에너빌리티", "한수원"],
     "en": ["nuclear power", "nuclear reactor", "SMR", "uranium stocks", "uranium miner", "uranium price"],
     "zh": ["核電", "核能"], "cn": ["核电", "核能"], "ja": ["原発", "原子力"]},
    {"name": "조선",
     "kr": ["조선업", "조선주", "조선사", "HD현대중공업", "한화오션", "삼성중공업", "LNG선", "HD한국조선해양"],
     "en": ["shipbuilding", "shipbuilder", "shipbuilders", "shipyard"],
     "zh": ["造船", "船廠", "造船業"], "cn": ["造船", "船企", "造船厂", "船舶工业"], "ja": ["造船"]},
    {"name": "전력기기",
     "kr": ["전력기기", "변압기", "전력망", "HD현대일렉트릭", "효성중공업", "LS ELECTRIC", "LS일렉트릭"],
     "en": ["power grid", "power transformer", "power transformers", "electrical transformer", "transformer shortage",
            "transformer maker", "transformer makers", "electrical equipment", "grid investment"],   # 그냥 transformer 는 영화·게임 '트랜스포머'·AI 모델이 섞임
     "zh": ["重電", "變壓器", "電網"], "cn": ["电网", "变压器", "特高压"], "ja": ["送電網", "変圧器", "電力設備"]},
    {"name": "자동차",
     "kr": ["자동차", "현대차", "기아", "전기차"],
     "en": ["automaker", "automakers", "car sales", "electric vehicle", "Tesla"],
     "zh": ["汽車", "電動車"], "cn": ["汽车", "新能源车", "电动车"], "ja": ["自動車", "トヨタ"]},
    {"name": "우주항공",
     "kr": ["우주항공", "우주산업", "위성", "발사체", "누리호"],
     "en": ["satellite", "satellites", "SpaceX", "rocket launch", "space industry"],
     "zh": ["太空", "衛星", "航太"], "cn": ["航天", "卫星", "商业航天"], "ja": ["宇宙産業", "衛星", "ロケット"]},
    {"name": "수소",
     "kr": ["수소", "연료전지"], "en": ["hydrogen", "fuel cell"],
     "zh": ["氫能", "燃料電池"], "cn": ["氢能", "燃料电池"], "ja": ["水素", "燃料電池"]},
    {"name": "신재생에너지",
     "kr": ["태양광", "풍력", "신재생", "재생에너지"],
     "en": ["solar power", "solar panel", "wind power", "renewable energy", "offshore wind"],
     "zh": ["太陽能", "風電", "綠能"], "cn": ["光伏", "风电", "新能源"], "ja": ["太陽光", "風力", "再生可能エネルギー"]},
    {"name": "게임",
     "kr": ["게임주", "게임사", "게임 업계", "넥슨", "엔씨소프트", "크래프톤", "넷마블"],
     "en": ["video game", "video games", "Nintendo", "game publisher", "gaming industry"],
     "zh": ["遊戲股", "電玩"], "cn": ["游戏股", "网游", "游戏公司"], "ja": ["ゲーム会社", "任天堂"]},
    {"name": "엔터",
     "kr": ["엔터", "K팝", "K-팝", "하이브", "JYP", "SM엔터", "YG엔터"],
     "en": ["K-pop", "entertainment stocks", "music streaming"],
     "zh": ["韓流", "K-pop"], "cn": ["韩流", "K-pop"], "ja": ["K-POP", "エンタメ株", "芸能事務所"]},
    {"name": "화장품",
     "kr": ["화장품", "K-뷰티", "K뷰티", "아모레퍼시픽", "LG생활건강", "코스맥스"],
     "en": ["cosmetics", "beauty brand", "K-beauty"],
     "zh": ["化妝品", "美妝"], "cn": ["化妆品", "美妆"], "ja": ["化粧品"]},
    {"name": "금융",
     "kr": ["은행", "증권사", "금융지주", "보험사", "KB금융", "신한지주"],
     "en": ["bank stocks", "banks", "JPMorgan", "Goldman Sachs", "lender", "lenders"],
     "zh": ["銀行", "金控", "券商"], "cn": ["银行", "券商", "保险公司"], "ja": ["銀行", "メガバンク", "証券会社"]},
    {"name": "인터넷·플랫폼",
     "kr": ["네이버", "카카오", "플랫폼 기업", "쿠팡", "빅테크"],
     "en": ["Meta", "Alphabet", "Amazon", "Microsoft", "big tech"],
     "zh": ["騰訊", "阿里巴巴", "網路平台"], "cn": ["互联网", "腾讯", "阿里巴巴", "字节跳动"], "ja": ["楽天", "LINEヤフー", "プラットフォーマー", "IT大手"]},
    {"name": "건설·부동산",
     "kr": ["건설사", "건설주", "부동산", "아파트값", "아파트 분양", "아파트 매매", "집값", "재건축"],
     "en": ["homebuilder", "homebuilders", "real estate", "housing market"],
     "zh": ["營建", "房地產", "房市"], "cn": ["房地产", "楼市", "房企"], "ja": ["不動産", "住宅市場", "ゼネコン"]},
    {"name": "가상자산",
     "kr": ["비트코인", "가상자산", "암호화폐", "이더리움", "스테이블코인"],
     "en": ["bitcoin", "crypto", "cryptocurrency", "ethereum", "stablecoin"],
     "zh": ["比特幣", "加密貨幣", "虛擬資產"], "cn": ["比特币", "加密货币", "虚拟货币"], "ja": ["ビットコイン", "暗号資産"]},
]

STATS_FILE = os.path.join(nb.HERE, "stats.json")
# 세지 않을 광고성 글 (제목 앞에 보이지 않는 글자를 넣은 성인 사이트 홍보 글 등)
SPAM = re.compile(r"^[\u200b-\u200d\ufeff]|porn|nsfw|ポルノ|アダルト|ミルフ|成人聊天|性愛機器人|成人向け", re.I)
# 테마 단어를 품고 있지만 뜻이 다른 말 → 관련 여부 볼 때 지우고 봄 (실제 기사 표본 점검에서 찾은 것)
STAT_FALSE = ["보조배터리", "아파트 화재", "아파트서 화재", "제약이", "제약을 받", "시간 제약",
              "gemini 4 hydrogen", "uranium enrichment", "smr hdd", "at amazon", "on amazon", "amazon rainforest",
              "central bank", "food bank", "木造船", "太陽電池", "한수원과 wk리그", "hydrogen peroxide",
              "楽天・", "楽天イーグルス", "楽天競馬", "楽天で", "楽天ブックス", "楽天 日本株", "楽天・日本株",
              # 조류인플루엔자(AI) 기사 — 인공지능 아님 (2026-11 표본 점검)
              "고병원성 AI", "AI 항원", "H5형 AI", "H5N1형 AI", "H5N6형 AI", "조류 AI", "AI 방역", "AI 확진",
              "AI 차단방역", "AI 위기경보", "AI 의심축", "AI 의심 신고", "AI 발생 농장",
              "제약 요인", "제약요인",
              # 수소가 들어간 다른 물질·건강 상품 (수소 에너지 아님)
              "フッ化水素", "過酸化水素", "硫化水素", "水素水", "水素吸入", "과산화수소", "황화수소", "불화수소", "수소수", "수소 흡입",
              # 사람 이름 Banks (은행 아님) — 2026-11-21 표본 점검
              "Sen. Banks", "Jim Banks", "Carl Banks", "Tanner Banks", "Tyra Banks", "Elizabeth Banks", "Azealia Banks",
              "Ernie Banks", "Lloyd Banks", "Russell Banks",
              # 고속도로 이름 (山陽自動車道 통행금지 등 — 자동차 산업 아님)
              "自動車道", "자동차전용도로", "자동차 전용도로",
              # 2026-11-21 3차 표본 점검: 지명·사람 이름 Banks, 농구장 이름 (은행·가상자산 아님)
              "Outer Banks", "Banks County", "Beyond the Banks", "Caleb Banks",
              "Crypto.com Arena", "Crypto Arena"]
# 쇼핑 할인 글 (예: 'Switch 2 is on sale for $469 ($30 off)', '$209 ... is now $159 at Amazon') — 산업 뉴스 아님
SHOP = re.compile(r"\$\d[\d,.]*\s*(?:off\b|discount)|\bon sale for \$|\bis now \$\d|\$\d[\d,.]* at amazon\b|"
                  r"\b\d+% off\b|\bblack friday deals?\b|\bcyber monday deals?\b|"
                  r"\bprime day deals?\b|\bbest [\w\s-]{0,30}deals\b|\bplus \d+ more deals\b|"
                  # 2026-11-21 2차 점검: 'Black Friday 2026 deals: Save $50'·'Black Friday Sale Is Now Live: Shop Deals'·'Black Friday bundle'
                  r"\bblack friday (?:20\d\d )?deals?\b|\bblack friday sale is (?:now )?live\b|\bblack friday bundle\b|"
                  r"\bsave \$\d|\bshop deals\b", re.I)
# 기사지만 산업 뉴스가 아닌 것 — 부고, 교통사고 (2026-11-21 2차 표본 점검: 조선에 '[부음] … 삼성중공업 프로 별세',
# 일본 자동차에 '軽自動車とトラックが正面衝突'·'踏切で立ち往生の軽自動車')
NOT_NEWS = re.compile(r"\[부음\]|\[부고\]|본인상\]|모친상|부친상|별세\]|"
                      r"正面衝突|衝突事故|追突事故|踏切で|立ち往生|意識不明|死亡事故|ひき逃げ|交通事故|"
                      # 야후 재팬 종목·펀드 시세 안내 페이지 (기사 아님 — 2026-11-21 3차: 일본 반도체 93건 중 14건, 부동산에도 많음)
                      r"株価\s*[・･]\s*株式情報|基準価格\s*[・･]\s*投資信託情報", re.I)
# 기사가 아닌 회사 기술 블로그·점수 모음 사이트
STAT_SRC_SKIP = {"amazon web services (aws)", "theshortcut.com"}
KEEP_DAYS = 735            # 날짜별 숫자를 며칠치 보관할지 (1년 통계 + 그 전 1년과 비교)
NOTIFY_HOUR = 7            # 한국 시간 이 시각 이후 첫 수집 때 '어제 통계' 알림
SATURATED = 95             # 검색 한 번에 이만큼 넘게 나오면 검색어를 나눠서 더 찾음 (구글 뉴스는 한 번에 최대 100개)


def relevant(theme, title):
    t = title
    for ff in STAT_FALSE:
        t = re.sub(re.escape(ff), " ", t, flags=re.I)
    return nb.is_relevant(theme, t)


def load_stats():
    try:
        with open(STATS_FILE, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            return d
    except Exception:
        pass
    return {}


def save_stats(st):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _rss(url):
    for attempt in range(3):
        try:
            r = requests.get(url, headers=nb.HEADERS, timeout=30)
            if r.status_code == 429:
                time.sleep(10 + attempt * 10)
                continue
            r.raise_for_status()
            return nb.parse_rss(r.text)
        except Exception as e:
            print(f"  ! 가져오기 실패 ({attempt + 1}/3): {e}")
            time.sleep(3)
    return None


def fetch_theme(region, words, when="1d"):
    """한 테마·한 나라의 최근 기사 (검색 결과가 꽉 차면 검색어를 하나씩 나눠서 더 찾음)"""
    items = _rss(nb.search_url(region, words, when=when))
    if items is None:
        return None, False
    saturated = len(items) >= SATURATED
    if saturated and len(words) > 1:
        for w in words:
            more = _rss(nb.search_url(region, [w], when=when))
            time.sleep(0.4)
            if more:
                items += more
                # 단어 하나로도 꽉 차면 '최근 1시간'만 한 번 더 찾음 (1시간마다 수집하니 이어 붙으면 빠짐이 줄어듦 — 2026-11-21 상한 칸 줄이기)
                if len(more) >= SATURATED and when != "1h":
                    recent = _rss(nb.search_url(region, [w], when="1h"))
                    time.sleep(0.4)
                    if recent:
                        items += recent
    elif saturated and when != "1h":
        recent = _rss(nb.search_url(region, words, when="1h"))
        time.sleep(0.4)
        if recent:
            items += recent
    return items, saturated


def collect():
    st = load_stats()
    st["themes"] = [t["name"] for t in STAT_THEMES]
    st["regions"] = [{"k": r["key"], "l": r["label"]} for r in nb.REGIONS]
    days = st.setdefault("days", {})          # {날짜: {테마: {나라: 개수}}}
    keys = st.setdefault("keys", {})          # 최근 2일치 기사 표시 (중복 방지)
    capped = st.setdefault("capped", {})      # {날짜: ["테마|나라", ...]} 검색 상한에 걸려 실제보다 적을 수 있는 곳
    # 긍정·부정·중립 (2026-11-22~): 새로 센 기사마다 판정해서 더함 (기사 수와 같은 기준 — 같은 기사는 한 번만)
    st.setdefault("senti", {})                # {날짜: {테마: {나라: [긍정, 부정, 중립, 판정다름]}}}
    spend = st.setdefault("spend", [])        # 아직 판정 못 한 기사 [[날짜, 테마, 나라, 제목], ...]
    scache = st.setdefault("scache", {})      # 최근 판정한 기사 {기사표시: [판정, 날짜]} — 같은 기사가 다른 테마로 또 나오면 재사용
    now = datetime.now(nb.KST)
    today = now.strftime("%Y-%m-%d")
    yday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    live = {today, yday}
    if st.get("dedup") != 1:        # 나라 간 중복 제거 방식으로 바뀌기 전 숫자는 지우고 다시 셈
        for d in live:
            days.pop(d, None)
        st["keys"] = keys = {}
        st["dedup"] = 1
    st.setdefault("senti_since", today)
    # 같은 테마에서 이미 다른 나라로 센 기사 (한 기사는 처음 잡힌 나라 한 곳에만 셈)
    seen_theme = {}
    for d, slots in keys.items():
        for slot, ks in slots.items():
            seen_theme.setdefault((d, slot.split("|")[0]), set()).update(ks)
    fails = 0
    t0 = time.time()
    # 검색 시간 창 = 지난번 수집 이후 + 1시간 겹침 (구글 뉴스는 한 번에 100개까지라, 창이 짧을수록 빠짐없이 셈)
    # 겹치는 기사는 위의 기사 표시로 한 번만 셈. 실행이 오래 빠졌으면 최대 24시간
    try:
        gap = (now - datetime.fromisoformat(st["last_ok"])).total_seconds() / 3600
    except Exception:
        gap = 24
    win_h = min(24, max(2, math.ceil(gap) + 1))
    when = "1d" if win_h >= 24 else f"{win_h}h"
    print(f"검색 시간 창: 최근 {when}")

    # 지난번에 가져오기 실패한 칸은 그 칸을 마지막으로 받은 때부터 다시 찾음 (예전엔 그 칸의 그 시간 기사가 빠졌음)
    miss = st.setdefault("miss", {})          # {"테마|나라": 그 칸을 마지막으로 제대로 받은 시각}
    for theme in STAT_THEMES:
        line = []
        for region in nb.REGIONS:
            words = theme.get(region["words"]) or []
            if not words:
                continue
            slot = f'{theme["name"]}|{region["key"]}'
            w = when
            if slot in miss:
                try:
                    g = (now - datetime.fromisoformat(miss[slot])).total_seconds() / 3600
                    w = "1d" if g + 1 >= 24 else f"{max(win_h, math.ceil(g) + 1)}h"
                except Exception:
                    w = "1d"
            items, saturated = fetch_theme(region, words, w)
            time.sleep(0.4)
            if items is None:
                fails += 1
                miss.setdefault(slot, st.get("last_ok") or (now - timedelta(hours=win_h)).isoformat())
                continue
            if slot in miss:
                print(f"  ↺ 지난번 실패한 칸 다시 받음: {slot} (최근 {w})")
                miss.pop(slot, None)
            added = 0
            hit_days = set()                   # 검색 결과에 나온 날짜 (상한에 걸렸을 때 그 날짜에 + 표시)
            for it in items:
                pub = it.get("published")
                if not pub:
                    continue
                d = pub.astimezone(nb.KST).strftime("%Y-%m-%d")
                if d not in live:
                    continue
                hit_days.add(d)
                title = it["title"]
                if nb.EXCLUDE.search(title) or SPAM.search(title) or SHOP.search(title) or NOT_NEWS.search(title) \
                        or (it.get("source") or "").strip().lower() in STAT_SRC_SKIP \
                        or nb.is_blocked(it["source"], it.get("src_url", "")) or not relevant(theme, title):
                    continue
                k = nb.title_key(title)[:40]
                if not k:
                    continue
                taken = seen_theme.setdefault((d, theme["name"]), set())
                if k in taken:                 # 이미 다른 나라(또는 이번 나라)로 셈
                    continue
                taken.add(k)
                keys.setdefault(d, {}).setdefault(slot, []).append(k)
                if k in scache and scache[k][0] in "pnux":
                    add_senti(st, d, theme["name"], region["key"], scache[k][0])
                else:
                    spend.append([d, theme["name"], region["key"], title])
                added += 1
            for d in live:
                n = len(keys.get(d, {}).get(slot, []))
                if n:
                    days.setdefault(d, {}).setdefault(theme["name"], {})[region["key"]] = n
            if saturated:                      # 자정 직후엔 검색 창이 거의 어제라서, 오늘이 아니라 기사가 나온 날짜에 표시
                for d in (hit_days or {today}):
                    lst = capped.setdefault(d, [])
                    if slot not in lst:
                        lst.append(slot)
            line.append(f'{region["key"]}+{added}')
        print(f'■ {theme["name"]}: ' + " ".join(line))

    judge_pending(st, now)

    # 오래된 기록 정리
    cutoff = (now - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    st["days"] = {d: v for d, v in days.items() if d >= cutoff}
    st["keys"] = {d: v for d, v in keys.items() if d in live}
    st["senti"] = {d: v for d, v in st["senti"].items() if d >= cutoff}
    st["capped"] = {d: v for d, v in capped.items() if d >= cutoff}
    st["updated"] = now.strftime("%m/%d %H:%M")
    if fails < 40:                              # 대부분 받았을 때만 '지난번 수집' 시각으로 기록
        st["last_ok"] = now.isoformat()
    save_stats(st)
    total = sum(sum(v.values()) for v in st["days"].get(today, {}).values())
    print(f"완료 {st['updated']} · 오늘 누적 {total}건 · 가져오기 실패 {fails} · {time.time() - t0:.0f}초")

    if now.hour >= NOTIFY_HOUR and st.get("notified") != today and st["days"].get(yday):
        if send_daily(st, yday):
            st["notified"] = today
            save_stats(st)
    if fails and fails == sum(1 for t in STAT_THEMES for r in nb.REGIONS if t.get(r["words"])):
        sys.exit(1)


REVIEW_FILE = os.path.join(nb.HERE, "sentiment_review.jsonl")   # Claude 가 검토할 기사 기록 (최근 며칠만)
CLAUDE_FILE = os.path.join(nb.HERE, "claude_labels.json")        # Claude 가 기준(SENTIMENT_GUIDE.md)대로 판정한 결과
JUDGE_MINUTES = 40   # 한 번 실행에서 긍정·부정 판정에 쓸 최대 시간 (한 건 약 2초 → 약 1,200건). 남으면 다음 실행에서 이어서
PEND_DAYS = 4        # 판정을 기다리는 기사를 며칠까지 들고 있을지


def add_senti(st, d, theme, rk, lab):
    v = st["senti"].setdefault(d, {}).setdefault(theme, {}).setdefault(rk, [0, 0, 0, 0])
    v["pnux".index(lab)] += 1


def judge_pending(st, now):
    """판정을 기다리는 기사를 낱말 판정 + AI 판정으로 함께 판정 → 같으면 그 판정, 다르면 x(판정 다름)"""
    import sentiment
    cut = (now - timedelta(days=PEND_DAYS)).strftime("%Y-%m-%d")
    pend = [p for p in st["spend"] if p[0] >= cut]
    if pend:
        t0 = time.time()
        uniq = {}                                    # 같은 기사(제목)는 한 번만 판정
        for p in pend:
            uniq.setdefault(nb.title_key(p[3])[:40], p[3])
        ks = list(uniq)
        try:
            det = sentiment.judge_detail([uniq[k] for k in ks], deadline=t0 + JUDGE_MINUTES * 60)
        except Exception as e:
            print(f"  ! 긍정·부정 판정 실패: {e}")
            det = [("?", None, None)] * len(ks)
        labs = [x[0] for x in det]
        got = {k: l for k, l in zip(ks, labs) if l != "?"}
        for k, l in list(got.items())[:12]:          # 실행 기록에 판정 예 몇 개 (점검용)
            print(f"   판정 예 [{ {'p':'긍정','n':'부정','u':'중립','x':'판정다름'}[l] }] {uniq[k][:80]}")
        rest = []
        for p in pend:
            lab = got.get(nb.title_key(p[3])[:40])
            if lab:
                add_senti(st, p[0], p[1], p[2], lab)
            else:
                rest.append(p)
        for k, l in got.items():
            st["scache"][k] = [l, now.strftime("%Y-%m-%d")]
        # Claude 검토용 기록: 판정 다름 전부 + 확정 기사 20건 중 1건(맞았는지 표본 점검)
        refs = {}
        for p in pend:
            kk = nb.title_key(p[3])[:40]
            if kk in got:
                refs.setdefault(kk, []).append([p[0], p[1], p[2]])
        lines = []
        for (k, (f, lx, ai)) in zip(ks, det):
            if f == "?" or k not in refs:
                continue
            h = int(hashlib.md5(k.encode()).hexdigest(), 16)
            if f == "x" or (lx != ai and h % 4 == 0) or h % 20 == 0:   # 판정 다름 전부 + 규칙으로 정한 것 1/4 + 같은 것 1/20
                lines.append(json.dumps({"k": k, "t": uniq[k], "f": f, "lx": lx, "ai": ai, "r": refs[k]}, ensure_ascii=False))
        if lines:
            with open(REVIEW_FILE, "a", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
        st["spend"] = rest
        c = {k: list(got.values()).count(k) for k in "pnux"}
        print(f"긍정·부정 판정: 기사 {len(got)}/{len(ks)}개 판정 · 긍정 {c['p']} 부정 {c['n']} 중립 {c['u']} 판정다름 {c['x']} "
              f"· 남은 것 {len(rest)}건(다음 실행에서) · {time.time() - t0:.0f}초")
    else:
        st["spend"] = []
    keep = (now - timedelta(days=3)).strftime("%Y-%m-%d")
    st["scache"] = {k: v for k, v in st["scache"].items() if v[1] >= keep}
    apply_claude(st, now)
    apply_backfill(st)


BACKFILL_FILE = os.path.join(nb.HERE, "sentiment_backfill.json")


def apply_backfill(st):
    import sentiment
    """지난주(제목이 안 남은 날) 표본 판정 → 그날 실제 기사 수를 표본 비율로 나눈 추정치('≈')로 senti 에 넣음.
    나라 칸 표본이 5건 이상이면 그 나라 비율, 아니면 그 테마·날짜 전체 비율. Claude 판정이 있으면 그걸로."""
    try:
        bf = json.load(open(BACKFILL_FILE, encoding="utf-8"))
    except Exception:
        return
    try:
        labels = json.load(open(CLAUDE_FILE, encoding="utf-8")).get("labels", {})
    except Exception:
        labels = {}
    cells, themes = {}, {}
    for it in bf.get("items", []):
        f = labels.get(it["k"])
        if not f:
            f = sentiment.combine(it.get("lx"), it.get("ai")) if it.get("ai") else it.get("f")   # 지금 규칙으로 다시 정함
        if f not in ("p", "n", "u", "x"):
            continue
        i = "pnux".index(f)
        cells.setdefault((it["d"], it["th"], it["rk"]), [0, 0, 0, 0])[i] += 1
        themes.setdefault((it["d"], it["th"]), [0, 0, 0, 0])[i] += 1
    est_days = []
    for d in bf.get("days", []):
        if d >= st.get("senti_since", "9999"):
            continue
        out = {}
        for th, regs in st.get("days", {}).get(d, {}).items():
            for rk, cnt in regs.items():
                if not cnt:
                    continue
                v = cells.get((d, th, rk))
                if not v or sum(v) < 5:
                    v = themes.get((d, th))
                if not v or not sum(v):
                    continue
                e = [cnt * x / sum(v) for x in v]
                r = [int(x) for x in e]
                for j in sorted(range(4), key=lambda j: -(e[j] - r[j]))[:cnt - sum(r)]:
                    r[j] += 1                    # 반올림해도 합이 그날 기사 수와 같게
                out.setdefault(th, {})[rk] = r
        if out:
            st["senti"][d] = out
            est_days.append(d)
    st["senti_est"] = est_days


def apply_claude(st, now):
    """Claude 판정(claude_labels.json)을 통계에 반영: 그 기사를 센 칸에서 이전 판정을 빼고 Claude 판정을 더함 (기사마다 한 번)"""
    try:
        labels = json.load(open(CLAUDE_FILE, encoding="utf-8")).get("labels", {})
    except Exception:
        labels = {}
    done = st.setdefault("capplied", {})
    keep = (now - timedelta(days=PEND_DAYS + 1)).strftime("%Y-%m-%d")
    lines = []
    try:
        lines = [json.loads(x) for x in open(REVIEW_FILE, encoding="utf-8") if x.strip()]
    except Exception:
        pass
    n = 0
    for e in lines:
        lab = labels.get(e["k"])
        if lab not in ("p", "n", "u") or e["k"] in done:
            continue
        for d, th, rk in e["r"]:
            v = st["senti"].get(d, {}).get(th, {}).get(rk)
            if not v:
                continue
            i = "pnux".index(e["f"])
            if v[i] > 0:
                v[i] -= 1
                v["pnux".index(lab)] += 1
                n += 1
                st.setdefault("cdone", {})[d] = st.setdefault("cdone", {}).get(d, 0) + 1
        done[e["k"]] = max((r[0] for r in e["r"]), default=now.strftime("%Y-%m-%d"))
    if n:
        print(f"Claude 검토 반영: {n}건")
    st["capplied"] = {k: d for k, d in done.items() if d >= keep}
    st["cdone"] = {d: c for d, c in st.get("cdone", {}).items() if d >= (now - timedelta(days=400)).strftime("%Y-%m-%d")}
    # 검토 기록은 최근 며칠만 남김
    kept = [x for x in lines if max((r[0] for r in x["r"]), default="") >= keep]
    if len(kept) != len(lines):
        with open(REVIEW_FILE, "w", encoding="utf-8") as fh:
            fh.write("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in kept))


def day_total(st, day, theme):
    return sum((st.get("days", {}).get(day, {}).get(theme) or {}).values())


def send_daily(st, day):
    """어제 테마별 뉴스 순위 알림"""
    prev = (datetime.strptime(day, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    rows = []
    for name in st["themes"]:
        n, p = day_total(st, day, name), day_total(st, prev, name)
        rows.append((name, n, p))
    rows.sort(key=lambda x: -x[1])
    if not rows or rows[0][1] == 0:
        return False

    def chg(n, p):
        if not p:
            return "신규" if n else ""
        pct = round((n - p) / p * 100)
        return f"▲{pct}%" if pct > 0 else (f"▼{-pct}%" if pct < 0 else "–")

    lines = [f"{i}. {name} {n:,}건 {chg(n, p)}".rstrip() for i, (name, n, p) in enumerate(rows[:10], 1) if n > 0]
    jumps = [r for r in rows if r[2] >= 20 and r[1] >= r[2] * 1.5]
    jumps.sort(key=lambda r: -(r[1] / r[2]))
    msg = "\n".join(lines)
    if jumps:
        msg += "\n\n🔺 급증: " + ", ".join(f"{name} {chg(n, p)}" for name, n, p in jumps[:3])
    md = day[5:].replace("-", "/")
    page = f"https://{nb.REPO.split('/')[0].lower()}.github.io/{nb.REPO.split('/')[1]}/#stats"
    return nb.notify(f"📊 어제({md}) 테마별 뉴스 수", msg, click=page,
                     actions=[{"action": "view", "label": "통계 보기", "url": page}],
                     tags=["bar_chart"], priority=3,
                     card={"paper": "뉴스 통계", "kicker": f"{md} 테마별 뉴스 수",
                           "headline": f"1위 {rows[0][0]} {rows[0][1]:,}건",
                           "lines": lines[:8], "footer": "눌러서 📊 통계 탭에서 추이 보기"})


if __name__ == "__main__":
    collect()

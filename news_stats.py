# -*- coding: utf-8 -*-
"""
📊 테마별 뉴스 통계 봇
- 증시 주요 테마 20개가 나라별로 하루에 뉴스가 몇 개 나왔는지 셉니다.
- 3시간마다 모아서 같은 기사는 한 번만 세고, 날짜(한국 시간)별로 쌓아요.
  (구글 뉴스 영어판·번체판은 나라끼리 같은 기사가 겹쳐서, 한 기사는 처음 잡힌 나라 한 곳에만 셈:
   한국 → 미국 → 중국 → 대만 → 홍콩 → 일본 → 싱가포르 → 세계 순)
- 매일 아침 어제 통계를 휴대폰으로 알려 주고, 뉴스 페이지의 📊 통계 탭에서 추이를 볼 수 있어요.

★ 테마나 검색어를 바꾸고 싶으면 아래 STAT_THEMES 만 고치면 됩니다.
   kr=한국어, en=영어(미국·싱가포르·세계), zh=번체(대만·홍콩), cn=간체(중국), ja=일본어
   기사 제목에 이 단어 중 하나라도 있어야 그 테마 기사로 셉니다.
"""
import json
import os
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
     "zh": ["電池", "鋰電池", "寧德時代", "正極材料"], "cn": ["动力电池", "锂电池", "宁德时代", "碳酸锂"],
     "ja": ["電池", "リチウムイオン電池", "車載電池"]},
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
     "zh": ["軍工", "國防", "軍購"], "cn": ["军工", "国防"], "ja": ["防衛産業", "防衛費", "防衛装備"]},
    {"name": "원전",
     "kr": ["원전", "원자력", "SMR", "두산에너빌리티", "한수원"],
     "en": ["nuclear power", "nuclear reactor", "SMR", "uranium"],
     "zh": ["核電", "核能"], "cn": ["核电", "核能"], "ja": ["原発", "原子力"]},
    {"name": "조선",
     "kr": ["조선업", "조선주", "조선사", "HD현대중공업", "한화오션", "삼성중공업", "LNG선", "HD한국조선해양"],
     "en": ["shipbuilding", "shipbuilder", "shipbuilders", "shipyard"],
     "zh": ["造船", "船舶"], "cn": ["造船", "船舶"], "ja": ["造船"]},
    {"name": "전력기기",
     "kr": ["전력기기", "변압기", "전력망", "HD현대일렉트릭", "효성중공업", "LS ELECTRIC", "LS일렉트릭"],
     "en": ["power grid", "transformer", "transformers", "electrical equipment", "grid investment"],
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
     "zh": ["韓流", "K-pop"], "cn": ["韩流", "K-pop"], "ja": ["K-POP", "エンタメ"]},
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
     "zh": ["騰訊", "阿里巴巴", "網路平台"], "cn": ["互联网", "腾讯", "阿里巴巴", "字节跳动"], "ja": ["楽天", "LINEヤフー", "プラットフォーム"]},
    {"name": "건설·부동산",
     "kr": ["건설사", "건설주", "부동산", "아파트", "재건축"],
     "en": ["homebuilder", "homebuilders", "real estate", "housing market"],
     "zh": ["營建", "房地產", "房市"], "cn": ["房地产", "楼市", "房企"], "ja": ["不動産", "住宅市場", "ゼネコン"]},
    {"name": "가상자산",
     "kr": ["비트코인", "가상자산", "암호화폐", "이더리움", "스테이블코인"],
     "en": ["bitcoin", "crypto", "cryptocurrency", "ethereum", "stablecoin"],
     "zh": ["比特幣", "加密貨幣", "虛擬資產"], "cn": ["比特币", "加密货币", "虚拟货币"], "ja": ["ビットコイン", "暗号資産"]},
]

STATS_FILE = os.path.join(nb.HERE, "stats.json")
KEEP_DAYS = 120            # 날짜별 숫자를 며칠치 보관할지
NOTIFY_HOUR = 7            # 한국 시간 이 시각 이후 첫 수집 때 '어제 통계' 알림
SATURATED = 95             # 검색 한 번에 이만큼 넘게 나오면 검색어를 나눠서 더 찾음 (구글 뉴스는 한 번에 최대 100개)


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


def fetch_theme(region, words):
    """한 테마·한 나라의 최근 24시간 기사 (검색 결과가 꽉 차면 검색어를 하나씩 나눠서 더 찾음)"""
    items = _rss(nb.search_url(region, words, when="1d"))
    if items is None:
        return None, False
    saturated = len(items) >= SATURATED
    if saturated and len(words) > 1:
        for w in words:
            more = _rss(nb.search_url(region, [w], when="1d"))
            time.sleep(0.4)
            if more:
                items += more
    return items, saturated


def collect():
    st = load_stats()
    st["themes"] = [t["name"] for t in STAT_THEMES]
    st["regions"] = [{"k": r["key"], "l": r["label"]} for r in nb.REGIONS]
    days = st.setdefault("days", {})          # {날짜: {테마: {나라: 개수}}}
    keys = st.setdefault("keys", {})          # 최근 2일치 기사 표시 (중복 방지)
    capped = st.setdefault("capped", {})      # {날짜: ["테마|나라", ...]} 검색 상한에 걸려 실제보다 적을 수 있는 곳
    now = datetime.now(nb.KST)
    today = now.strftime("%Y-%m-%d")
    yday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    live = {today, yday}
    if st.get("dedup") != 1:        # 나라 간 중복 제거 방식으로 바뀌기 전 숫자는 지우고 다시 셈
        for d in live:
            days.pop(d, None)
        st["keys"] = keys = {}
        st["dedup"] = 1
    # 같은 테마에서 이미 다른 나라로 센 기사 (한 기사는 처음 잡힌 나라 한 곳에만 셈)
    seen_theme = {}
    for d, slots in keys.items():
        for slot, ks in slots.items():
            seen_theme.setdefault((d, slot.split("|")[0]), set()).update(ks)
    fails = 0
    t0 = time.time()

    for theme in STAT_THEMES:
        line = []
        for region in nb.REGIONS:
            words = theme.get(region["words"]) or []
            if not words:
                continue
            items, saturated = fetch_theme(region, words)
            time.sleep(0.4)
            if items is None:
                fails += 1
                continue
            slot = f'{theme["name"]}|{region["key"]}'
            added = 0
            for it in items:
                pub = it.get("published")
                if not pub:
                    continue
                d = pub.astimezone(nb.KST).strftime("%Y-%m-%d")
                if d not in live:
                    continue
                title = it["title"]
                if nb.EXCLUDE.search(title) or nb.is_blocked(it["source"], it.get("src_url", "")) \
                        or not nb.is_relevant(theme, title):
                    continue
                k = nb.title_key(title)[:40]
                if not k:
                    continue
                taken = seen_theme.setdefault((d, theme["name"]), set())
                if k in taken:                 # 이미 다른 나라(또는 이번 나라)로 셈
                    continue
                taken.add(k)
                keys.setdefault(d, {}).setdefault(slot, []).append(k)
                added += 1
            for d in live:
                n = len(keys.get(d, {}).get(slot, []))
                if n:
                    days.setdefault(d, {}).setdefault(theme["name"], {})[region["key"]] = n
            if saturated:
                lst = capped.setdefault(today, [])
                if slot not in lst:
                    lst.append(slot)
            line.append(f'{region["key"]}+{added}')
        print(f'■ {theme["name"]}: ' + " ".join(line))

    # 오래된 기록 정리
    cutoff = (now - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    st["days"] = {d: v for d, v in days.items() if d >= cutoff}
    st["keys"] = {d: v for d, v in keys.items() if d in live}
    st["capped"] = {d: v for d, v in capped.items() if d >= cutoff}
    st["updated"] = now.strftime("%m/%d %H:%M")
    save_stats(st)
    total = sum(sum(v.values()) for v in st["days"].get(today, {}).values())
    print(f"완료 {st['updated']} · 오늘 누적 {total}건 · 가져오기 실패 {fails} · {time.time() - t0:.0f}초")

    if now.hour >= NOTIFY_HOUR and st.get("notified") != today and st["days"].get(yday):
        if send_daily(st, yday):
            st["notified"] = today
            save_stats(st)
    if fails and fails == sum(1 for t in STAT_THEMES for r in nb.REGIONS if t.get(r["words"])):
        sys.exit(1)


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

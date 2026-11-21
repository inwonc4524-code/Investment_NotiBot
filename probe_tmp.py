# 임시 점검: 긍정·부정 판정 정확도 (낱말 판정 / AI 모델 / 둘이 같을 때) — 점검 후 삭제
import time, sentiment as se
G = [  # (제목, 정답)
("SK하이닉스, HBM 호실적에 사상 최고가 경신","p"),("두산에너빌리티, 체코 원전 주기기 수주","p"),("LG엔솔 3분기 적자 축소…흑자 전환 눈앞","p"),("현대차, 美 판매 사상 최대 기록","p"),
("삼성SDI 주가 급락…전기차 수요 둔화 직격탄","n"),("에코프로비엠 4분기 적자 확대 우려","n"),("한미반도체 대표 검찰 압수수색","n"),("코스피 외국인 매도에 2% 넘게 하락","n"),
("정부, 반도체 특별법 국회 논의 착수","u"),("삼성전자 내일 3분기 실적 발표","u"),("포스코퓨처엠 신임 대표 선임","u"),("한화에어로스페이스, 주주총회 개최","u"),
("Nvidia shares surge after earnings beat estimates","p"),("Rivian loss narrows as deliveries rise","p"),("Eli Lilly wins FDA approval for new obesity drug","p"),("Micron raises forecast on strong AI memory demand","p"),
("Tesla stock falls after deliveries miss expectations","n"),("Boeing faces new FAA probe over safety lapses","n"),("Intel to cut 15% of workforce amid losses","n"),("Oil prices plunge on demand worries","n"),
("Fed officials to meet next week","u"),("Apple to hold product event in September","u"),("Amazon names new head of AWS","u"),("What to watch in markets this week","u"),
("宁德时代股价大涨 创历史新高","p"),("比亚迪10月销量同比增长40%","p"),("台積電法說會 獲利成長優於預期","p"),("小米汽车交付量突破新纪录","p"),
("比亚迪股价下跌 销量下滑引担忧","n"),("鸿海遭美国调查 股价重挫","n"),("某电池厂宣布裁员并暂停扩产","n"),("恒生指数大跌逾3%","n"),
("国务院召开常务会议","u"),("台積電將於下週舉行法說會","u"),("华为发布新款手机","u"),("央行公布最新货币政策报告","u"),
("トヨタ、上方修正 過去最高益を更新","p"),("ソニー株が急騰 好決算を好感","p"),("日立、大型受注を獲得","p"),("キーエンス、増配を発表","p"),
("日経平均、続落 半導体株が安い","n"),("日産、赤字転落 リストラ拡大へ","n"),("パナソニック電池工場の稼働延期","n"),("東芝に行政処分 不正会計で","n"),
("ソフトバンクG、決算発表へ","u"),("日銀、金融政策決定会合を開催","u"),("ホンダ、新社長を発表","u"),("東京株式市場の見通し","u"),
]
titles=[t for t,_ in G]; gold=[g for _,g in G]
t0=time.time(); mod=se.model_labels(titles); t1=time.time()
lex=[se.lexicon_label(t) for t in titles]
fin=[a if a==b else "x" for a,b in zip(lex,mod)]
def acc(p): return sum(a==b for a,b in zip(p,gold))
print(f"모델 시간 {t1-t0:.1f}초 ({len(titles)}건)")
print(f"낱말 판정 정확도 {acc(lex)}/{len(G)} · AI 모델 {acc(mod)}/{len(G)}")
agree=[i for i,f in enumerate(fin) if f!='x']
print(f"둘이 같은 기사 {len(agree)}/{len(G)} 중 정답 {sum(fin[i]==gold[i] for i in agree)}")
for (t,g),a,b in zip(G,lex,mod): print(f"  정답 {g} 낱말 {a} 모델 {b} {'✓' if a==b==g else ('x' if a!=b else '✗틀림')} {t}")
# 속도: 1000건
t0=time.time(); se.model_labels(titles*21); print(f"1000건 판정 시간 {time.time()-t0:.1f}초")

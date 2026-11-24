"""GDELT 9~11월 자료가 다시 받으면 채워지는지 시험 (일회용 점검)"""
from datetime import date
import news_history as nh
TH = dict(nh.THEMES); RG = dict(nh.REGIONS)
for th, rk in [("AI", "us"), ("반도체", "kr"), ("자동차", "us"), ("가상자산", "us")]:
    c = nh.fetch(TH[th], RG[rk], date(2026, 8, 25), date(2026, 11, 23))
    if c is None:
        print(th, rk, "실패"); continue
    ks = sorted(c)
    print(th, rk, len(ks), "일")
    print("  ", " ".join(f"{k[5:]}:{c[k]}" for k in ks))

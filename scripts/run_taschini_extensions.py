"""Taschini 이론확장 산출: 불확실성 밴드·옵션가치·CCR 비교.

입력:  outputs/runs/msr_results_v1.0.json (run_model.py v1.0 산출; step MACC 모드)
       data/K-ETS_마스터데이터.xlsx (Taschini 모수; add_taschini_sheets.py로 생성)
산출:  outputs/runs/taschini_ext_v0.1.json
       outputs/csv/taschini_uncertainty_band.csv   — KT2019 위험조정 밴드(연도별)
       outputs/csv/taschini_floor_option_value.csv — GT2011 가격하한 풋옵션가치
       outputs/csv/taschini_ccr_vs_tnac.csv        — BRT2025 CCR vs K-MSR 공급조정

모든 모수는 엑셀에서 로드(하드코딩 없음). 보고서 §7.3·§8·§9 다음단계(ii~iv) 대응.
"""

import sys, json, csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from kets.config import get_param, get_sheet, load_cap_path_df, load_eua_forecast_df
from kets.taschini_extensions import (
    risk_adjusted_band, price_floor_put_value, ccr_vs_tnac_summary,
)

RESULTS = PROJECT_ROOT / "outputs" / "runs" / "msr_results_v1.0.json"
OUT_JSON = PROJECT_ROOT / "outputs" / "runs" / "taschini_ext_v0.2.json"
MACC_MODE = "step"          # 본 분석 MACC (exponential은 강건성용)
CSV_DIR = PROJECT_ROOT / "outputs" / "csv"

# ── 모수 로드 (엑셀 Taschini 카테고리) ──
GAMMA = float(get_param("Taschini", "risk_aversion_gamma"))
SIGMA_BANK = float(get_param("Taschini", "banking_vol_sigma"))
KAPPA = float(get_param("Taschini", "premium_scale_kappa"))
OPT_RF = float(get_param("Taschini", "option_rf_rate"))
OPT_VOL = float(get_param("Taschini", "option_vol_sigma"))
CCR_PHI = float(get_param("Taschini", "ccr_gain_phi"))
CCR_RATIO = float(get_param("Taschini", "ccr_target_ratio"))
CCR_MAXADJ = float(get_param("Taschini", "ccr_max_adjust"))

with open(RESULTS, encoding="utf-8") as f:
    res = json.load(f)["modes"][MACC_MODE]   # v1.0: modes[macc_mode] 하위에 results

cap_df = load_cap_path_df()
eua_df = load_eua_forecast_df()
eua_by_year = {int(r["year"]): float(r["eua_price_krw"]) for _, r in eua_df.iterrows()}


def cap_total(sid, yr):
    sub = cap_df[(cap_df["scenario_id"] == sid) & (cap_df["year"] == yr)]
    return float(sub["cap_tCO2"].sum())


# MSR 강도 모수(L3 적극) — CCR과 비교할 K-MSR 대표 설계
auc_df = get_sheet("유상할당레버")
AUCTION_CUR = float(auc_df[auc_df["lever_id"] == "A_cur"]["auction_ratio"].iloc[0])

msr_df = get_sheet("MSR설계")
l3 = msr_df[msr_df["level_id"] == "L3"].iloc[0]
RHO = float(l3["rho_intake"]); THETA_PLUS = float(l3["theta_plus_Mt"]) * 1e6

BASE_YEAR = 2026

# ═══════════════════════════════════════════════════════════════
# 1. KT2019 불확실성 밴드 — base 시나리오 L0/L3 가격경로에 적용
# ═══════════════════════════════════════════════════════════════
band_rows = []
for sid in ("base", "middle", "ideal"):
    for lvl in ("L0", "L3"):
        path = res["results"][sid][lvl]["path"]
        for p in path:
            yr = p["year"]
            b = risk_adjusted_band(p["kau"], p["bank_Mt"] * 1e6, cap_total(sid, yr),
                                   GAMMA, SIGMA_BANK, KAPPA)
            band_rows.append({
                "scenario": sid, "msr_level": lvl, "year": yr,
                "kau_central": round(b["central"]),
                "premium_pct": round(100 * b["premium_ratio"], 1),
                "kau_lower": round(b["lower"]), "kau_upper": round(b["upper"]),
                "bank_Mt": p["bank_Mt"],
            })

# ═══════════════════════════════════════════════════════════════
# 2. GT2011 가격하한 풋옵션가치 — 정책그리드의 가격하한 평가
# ═══════════════════════════════════════════════════════════════
floor_df = get_sheet("MSR가격하한")
floors = [{"id": r["floor_id"], "f26": float(r["floor_2026_krw"]), "f40": float(r["floor_2040_krw"])}
          for _, r in floor_df.iterrows()
          if isinstance(r["floor_id"], str) and r["floor_id"].startswith("M") and r["floor_id"] != "M0"]
# 펀더멘털가(base L0)
fund = {p["year"]: p["kau"] for p in res["results"]["base"]["L0"]["path"]}
years = sorted(fund.keys())

opt_rows = []
for fl in floors:
    for yr in years:
        floor_yr = fl["f26"] + (fl["f40"] - fl["f26"]) * (yr - BASE_YEAR) / (years[-1] - BASE_YEAR)
        T = yr - BASE_YEAR
        put_val = price_floor_put_value(fund[yr], floor_yr, OPT_VOL, T, OPT_RF)
        cap = cap_total("base", yr)
        auction_cap = AUCTION_CUR * cap   # 현행 유상할당 방어용량(유상할당레버 A_cur, 식6)
        opt_rows.append({
            "floor_id": fl["id"], "year": yr,
            "fundamental_kau": round(fund[yr]), "floor_kau": round(floor_yr),
            "put_value_krw_per_t": round(put_val),
            "moneyness": "ITM(방어필요)" if floor_yr > fund[yr] else "OTM",
            "implied_defense_cost_trillion": round(put_val * auction_cap / 1e12, 2),
        })

# ═══════════════════════════════════════════════════════════════
# 3. BRT2025 CCR vs K-MSR(TNAC) — base 시나리오 연도별 공급조정 비교
# ═══════════════════════════════════════════════════════════════
ccr_rows = []
base_path = res["results"]["base"]["L0"]["path"]
for p in base_path:
    yr = p["year"]
    target = CCR_RATIO * eua_by_year[yr]
    s = ccr_vs_tnac_summary(p["kau"], target, p["bank_Mt"] * 1e6, cap_total("base", yr),
                            CCR_PHI, THETA_PLUS, RHO, CCR_MAXADJ)
    ccr_rows.append({
        "year": yr, "kau": p["kau"], "eua": eua_by_year[yr],
        "ccr_target_kau": round(target), "price_gap_pct": s["price_gap_pct"],
        "ccr_supply_change_Mt": round(s["ccr_supply_change_Mt"], 1),
        "tnac_Mt": p["bank_Mt"], "tnac_supply_change_Mt": round(s["tnac_supply_change_Mt"], 1),
    })


# ── CSV 출력 ──
def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"  CSV: {path.relative_to(PROJECT_ROOT)}  ({len(rows)}행)")


CSV_DIR.mkdir(parents=True, exist_ok=True)
write_csv(CSV_DIR / "taschini_uncertainty_band.csv", band_rows)
write_csv(CSV_DIR / "taschini_floor_option_value.csv", opt_rows)
write_csv(CSV_DIR / "taschini_ccr_vs_tnac.csv", ccr_rows)

OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
with open(OUT_JSON, "w", encoding="utf-8") as f:
    json.dump({
        "version": "taschini_ext_0.3 (msr v1.0 기반)", "macc_mode": MACC_MODE,
        "params": {"gamma": GAMMA, "sigma_bank": SIGMA_BANK, "kappa": KAPPA,
                   "opt_rf": OPT_RF, "opt_vol": OPT_VOL, "ccr_phi": CCR_PHI,
                   "ccr_target_ratio": CCR_RATIO, "ccr_max_adjust": CCR_MAXADJ},
        "uncertainty_band": band_rows,
        "floor_option_value": opt_rows,
        "ccr_vs_tnac": ccr_rows,
    }, f, ensure_ascii=False, indent=2)
print(f"  JSON: {OUT_JSON.relative_to(PROJECT_ROOT)}")

# ── 콘솔 요약 ──
print("\n" + "=" * 76)
print("Taschini 확장 산출 요약")
print("=" * 76)
print("\n[1] KT2019 불확실성 밴드 — base L0 (위험회피 γ=%.1f, σ=%.0f%%)" % (GAMMA, 100 * SIGMA_BANK))
print(f"  {'연도':>6}{'중심가':>10}{'±프리미엄':>10}{'하단':>10}{'상단':>10}")
for r in band_rows:
    if r["scenario"] == "base" and r["msr_level"] == "L0" and r["year"] in (2026, 2030, 2035, 2040):
        print(f"  {r['year']:>6}{r['kau_central']:>10,}{r['premium_pct']:>9.1f}%"
              f"{r['kau_lower']:>10,}{r['kau_upper']:>10,}")
print("  → 잉여 큰 초기(2026)일수록 밴드폭↑. 위험회피 기업의 MSR 잉여기 가격하락 채널(워터베드 상쇄).")

print("\n[2] GT2011 가격하한 풋옵션가치 (Black-76, σ=%.0f%%)" % (100 * OPT_VOL))
print(f"  {'하한':>8}{'연도':>6}{'펀더멘털':>10}{'하한가':>10}{'풋가치':>10}{'방어비용(조원)':>14}")
for r in opt_rows:
    if r["year"] in (2030, 2040):
        print(f"  {r['floor_id']:>8}{r['year']:>6}{r['fundamental_kau']:>10,}"
              f"{r['floor_kau']:>10,}{r['put_value_krw_per_t']:>10,}"
              f"{r['implied_defense_cost_trillion']:>14.2f}")
print("  → 하한이 펀더멘털가 위일수록 풋가치↑=정부 방어부담↑. 현행 유상할당 방어용량으로 본 내재비용.")

print("\n[3] BRT2025 CCR(가격규칙) vs K-MSR(TNAC 물량규칙) — base 시나리오")
print(f"  {'연도':>6}{'KAU':>9}{'목표가':>9}{'가격갭%':>9}{'CCR공급조정Mt':>14}{'TNAC공급조정Mt':>15}")
for r in ccr_rows:
    if r["year"] in (2026, 2030, 2035, 2040):
        print(f"  {r['year']:>6}{r['kau']:>9,}{r['ccr_target_kau']:>9,}{r['price_gap_pct']:>8}%"
              f"{r['ccr_supply_change_Mt']:>14.1f}{r['tnac_supply_change_Mt']:>15.1f}")
print("  → CCR은 가격갭(KAU<목표)에 즉시 비례반응(긴축), TNAC은 물량잉여 소진 후 흡수정지.")
print("    저유동성 한국: CCR은 빠르나 신뢰가능 가격신호 필요, TNAC은 thin trading에 견고.")

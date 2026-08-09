"""K-ETS 가격전망 모형 v1.0 — 엔진 기반 thin runner + 정책패키지 v4(운영규칙 프레임).

v4 프레임(2026-07-03 확정): K-MSR은 법제화된 제도이고, 패키지는 그 제도의
**운영규칙(operating rules)** 이다. 유상할당은 정부공표경로 'A_gov'로 일원화
(무상할당비율 시트에서 cap 가중 도출: base 2026 ~9.9% → 2030+ ~23.9%).

패키지 4종 (정책패키지 시트):
  P0 — 무정책 반사실 (L0, 하한 없음, base cap, λ hold)
  P1 — 시행령 초안대로 (L3 수량규칙 + M_mid 하한)
  A  — 가격약속형: 회랑 하한(2026 관측가→2035 수소환원 문턱) + carve-only 백스톱(L_C),
       미유찰 보류물량 무효화(1차 overlay)
  B  — 수량약속형(B8): 2035 개시 사전공표, 무조건(θ=-1) 경매물량 50% 흡수·전량취소(L_QB)

산출 블록:
  1. packages         — P0/P1/A/B 경로·도입연도·방어·여유율·재정(연도별 a_gov×cap×P)
  2. gate_waterfall   — P0 → +draft(P1) → +회랑(=A) | 분기: P0 → +수량약속(=B)
  3. a_lambda_regimes — 패키지 A의 λ 레짐(relapse/hold/consolidate) 감도, P0 대비 효과
  4. quantity_frontier— B 변형 그리드(ρ×θ×개시연도, EU-literal 무효화 변형 포함)
  5. sensitivity_h2_elec — 수소×전력 2×2에서 A·B 도입연도(보수수소 하 B의 H2-DRI 미도입이 핵심)
  6. modes            — MACC step/exponential × 3 cap × 전 MSR강도 하이퍼큐브(부록)
  7. tech_thresholds  — 헤드라인 전환기술(H₂-DRI·e-cracker)의 연도별 문턱비용(보고서 §1)

모든 입력은 마스터 엑셀에서 로드(코드 하드코딩 없음). 유동성 모수는 유동성모수 시트.
산출: outputs/runs/msr_results_v1.0.json + outputs/csv/*.csv
"""

import sys, json, csv
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from kets.engine import KETSModel, PRICE_CEIL
from kets.excel_source import load_data_from_excel
from kets.policy_grid import policy_grid, cbam_cost
from kets.liquidity import realized_price_path, lambda_ramp

MACC_MODES = ["step", "exponential"]
SCENARIOS = ["base", "middle", "ideal"]
POLICY_CAP = "base"     # 정책그리드: 현행 cap에서 레버만 변화
V07_PATH = PROJECT_ROOT / "outputs" / "runs" / "msr_results_v0.7.json"
OUT_JSON = PROJECT_ROOT / "outputs" / "runs" / "msr_results_v1.0.json"
CSV_DIR = PROJECT_ROOT / "outputs" / "csv"


# ═══════════════════════════════════════════════════════════════
# 1. 데이터 로드 (엑셀 1회 → 두 macc_mode가 같은 데이터 계약 공유)
# ═══════════════════════════════════════════════════════════════
DATA = load_data_from_excel()
LIQ = DATA["liquidity_defaults"]   # 유동성모수 시트 (lambda_0, psi_default 등)


def liquidity_regimes(model: KETSModel, base_path, msr_path):
    """L0 반사실 대비 MSR 효과에 전달승수를 적용한 4개 레짐 (Policy Brief §5·§7①).

    엔진 realized_path와 동일 수식이나, 이미 푼 경로를 재사용해 재solve를 피한다.
    """
    years = model.years
    p_base = np.array([r["kau"] for r in base_path])
    p_fri = np.array([r["kau"] for r in msr_path])
    lam0 = LIQ["lambda_0"]
    ramp = np.array([lambda_ramp(yr, model.base_year, lam0,
                                 LIQ["lambda_terminal_default"],
                                 LIQ["ramp_years_default"]) for yr in years])
    flat = np.full(len(years), lam0)
    regimes = {
        "frictionless": realized_price_path(p_base, p_fri, np.ones(len(years)), 0.0),
        "noresponse":   realized_price_path(p_base, p_fri, flat, LIQ["psi_high"]),
        "perverse":     realized_price_path(p_base, p_fri, flat, LIQ["psi_default"]),
        "perverse_low": realized_price_path(p_base, p_fri, flat, LIQ["psi_low"]),
        "reform":       realized_price_path(p_base, p_fri, ramp, LIQ["psi_default"]),
    }
    return {k: [round(float(v)) for v in arr] for k, arr in regimes.items()}


def solve_mode(macc_mode: str) -> dict:
    """한 MACC 모드의 전체 산출: 15+3경로, 레벨브리지, 유동성레짐, 그리드, 취소비교."""
    m = KETSModel(DATA, macc_mode)
    presets = m.msr_presets()
    out = {"results": {}, "level_bridge": {}, "liquidity_regimes": {},
           "policy_grid_hotelling": None, "policy_grid_static": None,
           "cancel_vs_deferral": {}}

    for sid in SCENARIOS:
        out["results"][sid] = {}
        out["level_bridge"][sid] = {}
        out["liquidity_regimes"][sid] = {}
        base_path = None
        for lid, msr in presets.items():
            bridge = m.level_bridge_path(sid, msr, lam_0=0.0)   # static+hotelling 동시
            if not m.last_fp_converged:
                print(f"  [경고] MSR 고정점 비수렴: {sid}/{lid} (macc={macc_mode})")
            path = []
            for rec in bridge:
                yr = rec["year"]
                p = rec["hotelling"]
                path.append({"year": yr, "kau": round(p), "static": round(rec["static"]),
                             "abate_Mt": round(m.abatement_at_price(p, yr, sid) / 1e6, 1),
                             "intake_Mt": round(rec["intake_Mt"], 2),
                             "release_Mt": round(rec["release_Mt"], 2),
                             "bank_Mt": round(rec["bank_Mt"], 1),
                             "eua": round(m.eua[yr]), "gap": round(m.eua[yr] - p),
                             "auction_rev_trillion": round(m.auction_revenue(sid, yr, p) / 1e12, 3),
                             "cbam_cost_trillion": round(cbam_cost(m, p, yr) / 1e12, 3)})
            cum_rev = sum(x["auction_rev_trillion"] for x in path)
            cum_cbam = sum(x["cbam_cost_trillion"] for x in path)
            out["results"][sid][lid] = {
                "fp_converged": bool(m.last_fp_converged),
                # PRICE_CEIL 도달 = 물리적 비가용 조합 마커 (예: ideal×L_QB) — 균형 아님
                "infeasible_ceiling": any(x["kau"] >= PRICE_CEIL * 0.999 for x in path),
                "p0": path[0]["kau"], "terminal_bank_Mt": path[-1]["bank_Mt"],
                "min_bank_Mt": min(x["bank_Mt"] for x in path),
                "cum_auction_rev_trillion": round(cum_rev, 1),
                "cum_cbam_cost_trillion": round(cum_cbam, 1),
                "path": path,
            }
            out["level_bridge"][sid][lid] = [
                {"year": r["year"], "static": round(r["static"]),
                 "hotelling": round(r["hotelling"])} for r in bridge]
            if lid == "L0":
                base_path = path
            else:
                out["liquidity_regimes"][sid][lid] = liquidity_regimes(m, base_path, path)

        # ── 취소 vs 이연 vs EU식 무효화: 예비분·누적소각량 궤적 재구성 (엔진 규칙 미러) ──
        cmp = {}
        for lid in ("L3", "L3C", "L4", "L_EU"):
            if lid not in out["results"][sid]:
                continue
            pr = presets[lid]
            cancel = pr["cancel"]
            inval = pr.get("invalidate_above")          # tCO2 or None
            inval_Mt = inval / 1e6 if inval is not None else None
            reserve = DATA["msr_reserve_Mt"]
            cum_cancel = 0.0
            rows = []
            for x in out["results"][sid][lid]["path"]:
                cc = cancel * x["intake_Mt"]
                reserve += x["intake_Mt"] - x["release_Mt"] - cc
                if inval_Mt is not None and reserve > inval_Mt:
                    cc += reserve - inval_Mt            # EU식 스톡 무효화
                    reserve = inval_Mt
                cum_cancel += cc
                rows.append({"year": x["year"], "kau": x["kau"],
                             "reserve_Mt": round(reserve, 2),
                             "cum_cancel_Mt": round(cum_cancel, 2)})
            cmp[lid] = rows
        out["cancel_vs_deferral"][sid] = cmp

    # ── 정책그리드: 이중 앵커 (base cap, L0 펀더멘털) ──
    l0 = out["level_bridge"][POLICY_CAP]["L0"]
    pf_hotel = {r["year"]: float(r["hotelling"]) for r in l0}
    pf_static = {r["year"]: float(r["static"]) for r in l0}
    out["policy_grid_hotelling"] = policy_grid(m, POLICY_CAP, pf_hotel, "hotelling")
    out["policy_grid_static"] = policy_grid(m, POLICY_CAP, pf_static, "static")
    return out


# ═══════════════════════════════════════════════════════════════
# 2. 두 MACC 모드 산출
# ═══════════════════════════════════════════════════════════════
m_ref = KETSModel(DATA, "step")
presets_ref = m_ref.msr_presets()
print(f"기간 {m_ref.years[0]}–{m_ref.years[-1]}, r={m_ref.r:.3f}, "
      f"B0={m_ref.B0/1e6:.0f}Mt, 예비분={m_ref.reserve0/1e6:.1f}Mt")
print(f"MSR 강도: {', '.join(presets_ref.keys())}")
print(f"유동성 모수(유동성모수 시트): λ0={LIQ['lambda_0']}, ψ∈[{LIQ['psi_low']},{LIQ['psi_high']}], "
      f"ψ기본={LIQ['psi_default']}, 개혁 λ→{LIQ['lambda_terminal_default']}/{LIQ['ramp_years_default']:.0f}년")

modes = {}
for mode in MACC_MODES:
    print(f"\n>>> solving macc_mode={mode} ...")
    modes[mode] = solve_mode(mode)

# ═══════════════════════════════════════════════════════════════
# 2b. 정책 패키지 P0/P1/A/B + 게이트 워터폴 (v1.0, step MACC 헤드라인)
# ═══════════════════════════════════════════════════════════════
def _headline_acts(acts: dict):
    h2 = next((y for t, y in acts.items() if "수소환원" in t), None)
    en = next((y for t, y in acts.items() if "e-cracker" in t or "NCC" in t), None)
    return h2, en


def max_drawdown(prices) -> float:
    """가격경로 최대 낙폭(peak-to-trough, 비율) — 수량규칙의 급등·붕락 위험 지표."""
    peak, dd = prices[0], 0.0
    for p in prices:
        peak = max(peak, p)
        if peak > 0:
            dd = max(dd, (peak - p) / peak)
    return dd


def pkg_record(m, pkg):
    path = m.solve_package(pkg)
    prices = [r["kau"] for r in path]
    acts = m.tech_activation_years(prices, pkg["cap_scenario"], headline_only=True)
    acts_all = m.tech_activation_years(prices, pkg["cap_scenario"], headline_only=False)
    sid = pkg["cap_scenario"]
    # 재정: 연도별 유상할당 경로 a_t (A_gov = 무상할당비율 시트 도출 정부공표경로)
    #   rev_t = a_t × cap_t × P_t — 패키지 공통 기준이므로 패키지 간 재정 비교 가능.
    a_path = m.auction_ratio_path(sid, pkg["auction_lever"])
    rows = [{"year": r["year"], "kau": round(r["kau"]), "kau_prefloor": round(r["kau_prefloor"]),
             "static": round(r["static"]), "hotelling": round(r["hotelling"]),
             "lambda": round(r["lambda"], 3), "floor": round(r["floor"]),
             "defended": bool(r["defended"]), "headroom": r["headroom"],
             "bank_Mt": r["bank_Mt"],
             "intake_Mt": r["intake_Mt"], "release_Mt": r["release_Mt"],
             "auction_share": round(a_path[r["year"]], 4),
             "eua": round(m.eua[r["year"]]),
             "auction_rev_trillion": round(a_path[r["year"]] * m.cap_total[sid][r["year"]]
                                           * r["kau"] / 1e12, 3),
             "cbam_cost_trillion": round(cbam_cost(m, r["kau"], r["year"]) / 1e12, 3)}
            for r in path]
    return {
        "meta": {k: pkg.get(k) for k in ("package_id", "name_en", "name_kr", "msr_level",
                                          "floor_id", "auction_lever", "cap_scenario", "lambda_regime")},
        "fp_mode": getattr(m, "last_fp_mode", "exact"),
        "path": rows,
        "activation_headline": acts,
        "activation_all": acts_all,
        "defended_all": all(r["defended"] for r in path),
        "min_headroom": min(r["headroom"] for r in rows),
        "max_drawdown": round(max_drawdown(prices), 3),
        "cum_intake_Mt": round(sum(r["intake_Mt"] for r in rows), 1),
        "cum_auction_rev_trillion": round(sum(r["auction_rev_trillion"] for r in rows), 1),
    }

m_step = KETSModel(DATA, "step")
PKG_CFG = {p["package_id"]: p for p in m_step.packages}
packages = {pid: pkg_record(m_step, cfg) for pid, cfg in PKG_CFG.items()}

# 게이트 워터폴 (v4, 현행 cap·A_gov 고정): 운영규칙 스위치온의 한계기여 분해.
#   본선: P0 → +draft 수량규칙(=P1) → +회랑(=A)  |  분기: P0 → +수량약속(=B)
WF_STEPS = [
    ("W0 baseline (P0)", "main", PKG_CFG["P0"]),
    ("W1 +decree draft rule (=P1)", "main", PKG_CFG["P1"]),
    ("W2 +price-commitment corridor (=A)", "main", PKG_CFG["A"]),
    ("WB branch P0 +quantity-commitment (=B)", "branch", PKG_CFG["B"]),
]
waterfall = []
for label, branch, cfg in WF_STEPS:
    rec = packages[cfg["package_id"]]
    waterfall.append({"step": label, "branch": branch, "package_id": cfg["package_id"],
                      "kau_2030": next(r["kau"] for r in rec["path"] if r["year"] == 2030),
                      "kau_2040": rec["path"][-1]["kau"],
                      "activation_headline": rec["activation_headline"],
                      "defended_all": rec["defended_all"],
                      "min_headroom": rec["min_headroom"],
                      "max_drawdown": rec["max_drawdown"],
                      "cum_intake_Mt": rec["cum_intake_Mt"],
                      "cum_auction_rev_trillion": rec["cum_auction_rev_trillion"]})

# λ 레짐 감도: 패키지 A(가격약속형)를 3레짐으로 — 게이트① = 레짐 내 정책효과(A−P0)의 전달
a_regime_sens = {}
for reg in ("relapse", "hold", "consolidate"):
    p0r = pkg_record(m_step, {**PKG_CFG["P0"], "lambda_regime": reg})
    rec = pkg_record(m_step, {**PKG_CFG["A"], "lambda_regime": reg})
    a_regime_sens[reg] = {"kau_2030": next(r["kau"] for r in rec["path"] if r["year"] == 2030),
                          "path": [r["kau"] for r in rec["path"]],
                          "p0_path": [r["kau"] for r in p0r["path"]],
                          "effect_path": [a["kau"] - b["kau"] for a, b in zip(rec["path"], p0r["path"])],
                          "defended_all": rec["defended_all"],
                          "min_headroom": rec["min_headroom"],
                          "lambda_path": [r["lambda"] for r in rec["path"]]}

# ═══════════════════════════════════════════════════════════════
# 2c. 수량약속형 프런티어 (부록): B 변형 그리드 — ρ × θ × 개시연도, EU-literal 변형
#   모든 변형 = L_QB 기반(intake_basis='auction', A_gov 상한), base cap, λ hold, 하한 없음.
# ═══════════════════════════════════════════════════════════════
QF_YEARS = [2026, 2028, 2030, 2033, 2036, 2040]
QF_VARIANTS = [
    ("rho24_theta8",      "ρ=24%, θ=cap 8% (EU흡수율·EU형 임계)", dict(rho=0.24, theta_cap_frac=0.08, start_year=None)),
    ("rho24_theta3",      "ρ=24%, θ=cap 3%", dict(rho=0.24, theta_cap_frac=0.03, start_year=None)),
    ("rho50_theta3",      "ρ=50%, θ=cap 3%", dict(rho=0.50, theta_cap_frac=0.03, start_year=None)),
    ("rho24_uncond_now",  "ρ=24%, 무조건 즉시", dict(rho=0.24, theta_cap_frac=-1.0, start_year=None)),
    ("rho50_uncond_now",  "ρ=50%, 무조건 즉시", dict(rho=0.50, theta_cap_frac=-1.0, start_year=None)),
    ("rho24_start2033",   "ρ=24%, 무조건 2033 개시", dict(rho=0.24, theta_cap_frac=-1.0, start_year=2033)),
    ("rho24_start2035",   "ρ=24%, 무조건 2035 개시", dict(rho=0.24, theta_cap_frac=-1.0, start_year=2035)),
    ("rho50_start2035_B", "ρ=50%, 무조건 2035 개시 (=B)", dict(rho=0.50, theta_cap_frac=-1.0, start_year=2035)),
    ("eu_literal_inval",  "EU-literal 무효화: ρ=24%, θ=cap 8%, 무취소, 스톡>100Mt 무효화, 방출 6Mt@θ⁻=23Mt",
     dict(rho=0.24, theta_cap_frac=0.08, start_year=None, cancel=0.0,
          invalidate_above=100e6, release=6e6, theta_minus=23e6)),
]

def quantity_frontier(m):
    presets = m.msr_presets()
    lam_hold = m.lambda_regime_path("hold")
    out = {}
    for vid, desc, over in QF_VARIANTS:
        msr = {**presets["L_QB"], **over}
        bridge = m.level_bridge_path("base", msr, lam_path=lam_hold)
        prices = [r["kau_realized"] for r in bridge]
        h2, en = _headline_acts(m.tech_activation_years(prices, "base", headline_only=True))
        intakes = {r["year"]: r["intake_Mt"] for r in bridge}
        out[vid] = {"desc": desc,
                    "rule": {k: over.get(k, presets["L_QB"].get(k)) for k in
                             ("rho", "theta_cap_frac", "start_year", "cancel")},
                    "fp_mode": getattr(m, "last_fp_mode", "exact"),
                    "prices": {yr: round(prices[m.years.index(yr)]) for yr in QF_YEARS},
                    "cum_intake_Mt": round(sum(intakes.values()), 1),
                    "intake_years": [yr for yr, v in intakes.items() if v > 0.01],
                    "max_drawdown": round(max_drawdown(prices), 3),
                    "activation": {"h2_dri": h2, "e_ncc": en}}
    return out

qfrontier = quantity_frontier(m_step)

# ═══════════════════════════════════════════════════════════════
# 2d. 민감도 2×2: 수소(gov/conservative) × 전력(gov_invest/conservative) — A vs B
#   A는 회랑이 문턱을 추종(자기보정) vs B는 수량만 약속 → 보수수소에서 A·B 분기 검증.
# ═══════════════════════════════════════════════════════════════
sens_2x2 = {}
for h2_sc in ("gov", "conservative"):
    for el_sc in ("gov_invest", "conservative"):
        d2 = {**DATA, "model_params": {**DATA["model_params"],
                                       "h2_scenario": h2_sc, "elec_scenario": el_sc}}
        m2 = KETSModel(d2, "step")
        cfg2 = {p["package_id"]: p for p in m2.packages}
        cell = {}
        for pid in ("A", "B"):
            rec = pkg_record(m2, cfg2[pid])
            h2y, eny = _headline_acts(rec["activation_headline"])
            entry = {"h2_dri": h2y, "e_ncc": eny}
            if pid == "A":
                entry.update({"defended_all": rec["defended_all"],
                              "min_headroom": rec["min_headroom"]})
            cell[pid] = entry
        sens_2x2[f"h2_{h2_sc}|elec_{el_sc}"] = cell

# ═══ 콘솔 요약: 패키지·워터폴·프런티어·민감도 ═══
print("\n" + "=" * 78)
print("정책 패키지 v4 (step MACC): K-MSR 운영규칙 P0/P1/A/B — 유상=A_gov 공통")
print("=" * 78)
print(f"  {'pkg':<4}{'2026':>9}{'2030':>9}{'2035':>9}{'2040':>9}{'방어':>4}{'여유':>7}"
      f"{'누적흡수':>9}{'재정(조)':>9}   H2-DRI / e-NCC")
for pid, rec in packages.items():
    h2, en = _headline_acts(rec["activation_headline"])
    px = {r["year"]: r["kau"] for r in rec["path"]}
    print(f"  {pid:<4}{px[2026]:>9,}{px[2030]:>9,}{px[2035]:>9,}{px[2040]:>9,}"
          f"{'✓' if rec['defended_all'] else '✗':>4}{rec['min_headroom']:>7.2f}"
          f"{rec['cum_intake_Mt']:>9.1f}{rec['cum_auction_rev_trillion']:>9.1f}"
          f"   {h2 or '—'} / {en or '—'}")

print("\n게이트 워터폴 (2030 KAU / H2-DRI / e-NCC):")
for w in waterfall:
    h2, en = _headline_acts(w["activation_headline"])
    print(f"  {w['step']:<42}{w['kau_2030']:>10,}   {h2 or '—'} / {en or '—'}")

print("\n수량약속형 프런티어 (B 변형, base cap·A_gov·hold):")
print(f"  {'변형':<20}{'2030':>9}{'2036':>9}{'2040':>9}{'누적흡수':>9}{'낙폭':>7}   H2-DRI / e-NCC")
for vid, v in qfrontier.items():
    print(f"  {vid:<20}{v['prices'][2030]:>9,}{v['prices'][2036]:>9,}{v['prices'][2040]:>9,}"
          f"{v['cum_intake_Mt']:>9.1f}{v['max_drawdown']:>7.2f}"
          f"   {v['activation']['h2_dri'] or '—'} / {v['activation']['e_ncc'] or '—'}")

print("\n민감도 2×2 수소×전력 (A vs B, H2-DRI/e-NCC 도입연도):")
print(f"  {'셀':<34}{'A: H2/e-NCC':>16}{'A방어(여유)':>12}{'B: H2/e-NCC':>16}")
for key, cell in sens_2x2.items():
    a, b = cell["A"], cell["B"]
    a_def = ("✓" if a["defended_all"] else "✗") + f" ({a['min_headroom']:.2f})"
    a_act = f"{a['h2_dri'] or '—'}/{a['e_ncc'] or '—'}"
    b_act = f"{b['h2_dri'] or '—'}/{b['e_ncc'] or '—'}"
    print(f"  {key:<34}{a_act:>16}{a_def:>12}{b_act:>16}")

# ═══════════════════════════════════════════════════════════════
# 3. 무차익 불변식 게이트 + v0.7 대조 (참고용)
#
# v0.8은 상분해 솔버를 교정했으므로(엔진 docstring 참조) v0.7 Hotelling
# 경로와의 일치는 기대하지 않는다. 대신 균형의 필요조건인 무차익 불변식
#   P_{t+1} ≤ P_t·(1+r)·(1+tol)   (상향점프 = 차익기회 → 균형 아님)
# 을 전 경로에 대해 검사한다. v0.7과의 차이는 분류만 해서 기록한다.
# ═══════════════════════════════════════════════════════════════
viol_list = []
infeasible_cells = []
growth = np.exp(m_ref.r)          # 엔진 Hotelling은 연속복리 e^r 성장
for mode in MACC_MODES:
    for sid in SCENARIOS:
        for lid, rr in modes[mode]["results"][sid].items():
            path = rr["path"]
            for a, b in zip(path, path[1:]):
                # PRICE_CEIL 도달 = 물리적 비가용 마커(균형 아님) — 무차익 검사 제외.
                # 예: ideal cap × L_QB(무조건 수량보류)는 어떤 가격에도 청산 불가.
                if b["kau"] >= PRICE_CEIL * 0.999 or a["kau"] >= PRICE_CEIL * 0.999:
                    infeasible_cells.append((mode, sid, lid, b["year"]))
                    continue
                if b["kau"] > a["kau"] * growth * 1.001 + 1:
                    viol_list.append((mode, sid, lid, b["year"], a["kau"], b["kau"]))
print("\n" + "=" * 78)
print(f"무차익 불변식 (P_t+1 ≤ P_t·(1+r), 전 {len(MACC_MODES)*len(SCENARIOS)*len(presets_ref)}경로): "
      f"{'PASS' if not viol_list else 'FAIL ' + str(len(viol_list)) + '건'}")
for v in viol_list[:10]:
    print("  위반:", v)
if infeasible_cells:
    combos = sorted({(m_, s_, l_) for m_, s_, l_, _ in infeasible_cells})
    print(f"  (비가용 마커 셀 {len(infeasible_cells)}건 제외 — PRICE_CEIL 도달, 균형 아님: "
          f"{['/'.join(c) for c in combos]})")

parity = {"checked": False, "no_arbitrage_pass": not viol_list,
          "note": "v0.8 솔버 교정(argmax 소진연도 상분해)으로 v0.7 Hotelling 경로와 "
                  "의도적으로 다름 — v0.7은 상 경계 상향점프(차익기회)를 허용했음. "
                  "정태가·그리드 역학은 동일 로직."}
if V07_PATH.exists():
    v07 = json.loads(V07_PATH.read_text(encoding="utf-8"))
    n_diff = 0; n_cells = 0; max_dp = 0
    for sid in SCENARIOS:
        for lid, old in v07["results"][sid].items():
            new = modes["exponential"]["results"][sid].get(lid)
            if new is None:
                continue
            for xo, xn in zip(old["path"], new["path"]):
                n_cells += 1
                d = abs(xo["kau"] - xn["kau"])
                if d > 2:
                    n_diff += 1
                max_dp = max(max_dp, d)
    parity.update({"checked": True, "n_path_cells": n_cells,
                   "n_cells_changed_vs_v07": n_diff, "max_price_diff_krw": max_dp})
    print(f"v0.7 대조(exponential, 참고): {n_cells}셀 중 {n_diff}셀 변경, max |Δ|={max_dp:,}원 "
          f"(솔버 교정에 따른 의도된 변화)")

# ═══════════════════════════════════════════════════════════════
# 4. 콘솔 요약 (step 모드 기준)
# ═══════════════════════════════════════════════════════════════
S = modes["step"]

def pth(sid, lid, yr, key="kau"):
    return next(p[key] for p in S["results"][sid][lid]["path"] if p["year"] == yr)

print("\n" + "=" * 78)
print("v0.8 이중 앵커 (step MACC, base cap, L0): 정태(λ≈0) vs Hotelling(λ=1)")
print("=" * 78)
print(f"  {'연도':>6}{'정태':>10}{'Hotelling':>11}{'웨지':>10}{'관측 KAU':>10}")
kau_hist = {int(r["year"]): r["kau_avg_krw"] for r in m_ref.kau_history
            if r.get("kau_avg_krw") is not None}
for yr in [2026, 2030, 2035, 2040]:
    st = pth("base", "L0", yr, "static"); ho = pth("base", "L0", yr)
    obs = f"{kau_hist.get(yr, ''):>10,}" if yr in kau_hist else f"{'—':>10}"
    print(f"  {yr:>6}{st:>10,}{ho:>11,}{ho-st:>10,}{obs}")
print(f"  (참고: 관측 2025 평균 {kau_hist.get(2025, 0):,}원 — 정태 앵커와 정합, λ≈0 캘리브레이션 근거)")

print("\n" + "=" * 78)
print("KAU 가격경로 (step MACC, Hotelling 앵커), 3 cap × MSR강도")
print("=" * 78)
for sid in SCENARIOS:
    print(f"\n[{sid}]")
    print(f"  {'MSR':<16}{'2026':>9}{'2030':>9}{'2035':>9}{'2040':>9}{'min Bank':>9}")
    for lid in presets_ref:
        rr = S["results"][sid][lid]
        print(f"  {lid:<16}{pth(sid,lid,2026):>9,}{pth(sid,lid,2030):>9,}"
              f"{pth(sid,lid,2035):>9,}{pth(sid,lid,2040):>9,}{rr['min_bank_Mt']:>9.1f}")

print("\n" + "=" * 78)
print("유동성 레짐 (step, base cap, L3 vs L0): 2030년 MSR 가격효과의 전달")
print("=" * 78)
i2030 = m_ref.years.index(2030)
base30 = pth("base", "L0", 2030)
for reg, arr in S["liquidity_regimes"]["base"]["L3"].items():
    print(f"  {reg:<14}{arr[i2030]:>10,}원  (L0 대비 {arr[i2030]-base30:>+8,}원)")

print("\n" + "=" * 78)
print(f"정책그리드 (step, {POLICY_CAP} cap) — 2040 KAU, 앵커별. ✓=하한 전기간 방어")
print("=" * 78)
for anchor in ["static", "hotelling"]:
    g = S[f"policy_grid_{anchor}"]
    fls = sorted({v["floor_id"] for k, v in g.items() if k != "_meta"})
    aids = [k.split("|")[0] for k in g if k != "_meta"]
    aids = sorted(set(aids), key=aids.index)
    print(f"\n  [{anchor} 앵커]")
    print("  " + f"{'유상할당':<12}" + "".join(f"{f:>13}" for f in fls))
    for aid in aids:
        row = f"  {aid:<12}"
        for f in fls:
            cell = g[f"{aid}|{f}"]
            p40 = cell["path"][-1]["kau"]
            ok = "✓" if all(c["defended"] for c in cell["path"]) else "✗"
            row += f"{str(p40)+(ok if f != 'M0' else ''):>13}"
        print(row)

print("\n" + "=" * 78)
print("취소 vs 이연 (step): 2040 예비분·누적취소 (base / ideal)")
print("=" * 78)
for sid in ["base", "ideal"]:
    for lid, rows in S["cancel_vs_deferral"][sid].items():
        last = rows[-1]
        print(f"  [{sid}] {lid:<4} 2040 KAU={last['kau']:>8,}  예비분={last['reserve_Mt']:>7.1f}Mt  "
              f"누적취소={last['cum_cancel_Mt']:>6.1f}Mt")

# ═══════════════════════════════════════════════════════════════
# 5. 저장: JSON + CSV
# ═══════════════════════════════════════════════════════════════
# 전환기술 문턱 비용경로 — docs/report.md §1이 인쇄하는 값(H₂-DRI 2035·2037,
# e-cracker 2035). 엔진은 계산했지만 어디에도 남지 않아 골든 테스트가 잠글 수
# 없었다. 회랑 하한(패키지 A)의 기술앵커도 같은 경로다.
tech_thresholds = {
    t["tech"]: {"sector": t["sector"],
                "cost_krw_by_year": {yr: round(m_step._tech_cost(t, yr, POLICY_CAP))
                                     for yr in m_step.years}}
    for t in m_step.techs if t.get("headline")}

out = {"model_version": "1.0",
       "description": "정책패키지 v4: K-MSR=법제화 제도, 패키지=운영규칙(P0/P1/A 가격약속형/B 수량약속형); "
                      "유상=A_gov(정부공표경로) 일원화; 수량프런티어(ρ×θ×개시연도); 수소×전력 2×2 민감도; "
                      "이중 MACC·이중 앵커·λ레짐·정책그리드·취소vs이연은 부록(modes) 유지",
       "params": {"r": m_ref.r, "B0_Mt": m_ref.B0 / 1e6, "reserve_Mt": m_ref.reserve0 / 1e6,
                  "a_gov_base": {yr: round(m_ref.auction_share_t("base", yr), 4) for yr in m_ref.years},
                  "liquidity_defaults": LIQ},
       "msr_levels": [{**{k: (v / 1e6 if k in ("theta_plus", "theta_minus", "release") else v)
                          for k, v in p.items()}} for p in presets_ref.values()],
       "parity_v07": parity,
       "tech_thresholds": tech_thresholds,
       "packages": packages,
       "gate_waterfall": waterfall,
       "a_lambda_regimes": a_regime_sens,
       "quantity_frontier": qfrontier,
       "sensitivity_h2_elec": sens_2x2,
       "modes": modes}
OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n저장: {OUT_JSON} ({OUT_JSON.stat().st_size/1024:.0f} KB)")

CSV_DIR.mkdir(parents=True, exist_ok=True)

def write_csv(name, header, rows):
    p = CSV_DIR / name
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)
    print(f"저장: {p} ({len(rows)} rows)")

rows = []
for mode in MACC_MODES:
    for sid in SCENARIOS:
        for lid, rr in modes[mode]["results"][sid].items():
            for x in rr["path"]:
                rows.append([mode, sid, lid, x["year"], x["kau"], x["static"], x["eua"], x["gap"],
                             x["bank_Mt"], x["intake_Mt"], x["release_Mt"], x["abate_Mt"],
                             x["auction_rev_trillion"], x["cbam_cost_trillion"]])
write_csv("scenario_paths.csv",
          ["macc_mode", "cap_scenario", "msr_level", "year", "kau_krw", "static_krw", "eua_krw",
           "gap_krw", "bank_Mt", "intake_Mt", "release_Mt", "abate_Mt",
           "auction_rev_trillion", "cbam_cost_trillion"], rows)

rows = []
for mode in MACC_MODES:
    for sid in SCENARIOS:
        for lid, regs in modes[mode]["liquidity_regimes"][sid].items():
            for reg, arr in regs.items():
                for i, yr in enumerate(m_ref.years):
                    rows.append([mode, sid, lid, reg, yr, arr[i]])
write_csv("liquidity_regimes.csv",
          ["macc_mode", "cap_scenario", "msr_level", "regime", "year", "kau_realized_krw"], rows)

rows = []
for mode in MACC_MODES:
    for anchor in ["hotelling", "static"]:
        g = modes[mode][f"policy_grid_{anchor}"]
        for key, cell in g.items():
            if key == "_meta":
                continue
            for c in cell["path"]:
                rows.append([mode, anchor, key.split("|")[0], cell["floor_id"], cell["auction"],
                             c["year"], c["kau"], c["floor"], c["defended"], c["abate_Mt"],
                             c["withhold_capacity_Mt"], c["cbam_cost_trillion"]])
write_csv("policy_grid_yearly.csv",
          ["macc_mode", "anchor", "auction_lever", "floor_id", "auction_ratio", "year",
           "kau_krw", "floor_krw", "defended", "abate_Mt", "withhold_capacity_Mt",
           "cbam_cost_trillion"], rows)

rows = []
for mode in MACC_MODES:
    for anchor in ["hotelling", "static"]:
        g = modes[mode][f"policy_grid_{anchor}"]
        for key, cell in g.items():
            if key == "_meta":
                continue
            rows.append([mode, anchor, key.split("|")[0], cell["floor_id"], cell["auction"],
                         cell["path"][-1]["kau"],
                         all(c["defended"] for c in cell["path"]),
                         cell["cum_abate_Mt"], cell["cum_auction_rev_trillion"],
                         cell["cum_cbam_cost_trillion"]])
write_csv("policy_grid_summary.csv",
          ["macc_mode", "anchor", "auction_lever", "floor_id", "auction_ratio", "kau_2040_krw",
           "defended_all_years", "cum_abate_Mt", "cum_auction_rev_trillion",
           "cum_cbam_cost_trillion"], rows)

rows = []
for mode in MACC_MODES:
    for sid in SCENARIOS:
        for lid, recs in modes[mode]["cancel_vs_deferral"][sid].items():
            for x in recs:
                rows.append([mode, sid, lid, x["year"], x["kau"], x["reserve_Mt"], x["cum_cancel_Mt"]])
write_csv("cancel_vs_deferral.csv",
          ["macc_mode", "cap_scenario", "msr_level", "year", "kau_krw",
           "reserve_Mt", "cum_cancel_Mt"], rows)

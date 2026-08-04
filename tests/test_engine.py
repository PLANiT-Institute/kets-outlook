"""엔진 통합 테스트 (v0.8) — 균형 성질·데이터 계약·정책 메커니즘 회귀검증.

검증 항목:
  1. 관측가격 앵커: base/L0 2026 정태청산가 ≈ 관측 KAU (KAU과거가격 시트, ±15%)
  2. Excel ↔ JSON 데이터 계약 동등성 (kets_data.json 드리프트 방어)
  3. banking 비음(非陰)성: 전 경로 bank_Mt ≥ 0
  4. 무차익 불변식: P_{t+1} ≤ P_t·e^r (bank>0 구간 r 성장, 하향점프만 허용)
  5. MSR 방향성: 무마찰(Hotelling)에서 MSR 도입 시 초기가 ≥ L0
  6. 유동성 항등식: T(1,ψ)=1, T(0,0)=0, T(0,ψ<0)<0; λ=1이면 realized=frictionless
  7. 취소 vs 이연: L3C 누적취소 > 0, 예비분 잔액 L3C ≤ L3 (ideal cap)
  8. 정책그리드: 방어여부가 유상할당에 단조, 누적감축이 하한에 단조
  9. MSR 고정점 수렴 플래그
  10. 예비분 carve-out 회계: 2026–2030 합 = 예비분 총량, L0은 carve 없음
"""

import sys
import json
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from kets.engine import KETSModel, PRICE_CEIL
from kets.liquidity import transmission_multiplier
from kets.policy_grid import policy_grid

WEB_JSON = PROJECT_ROOT / "public" / "model" / "kets_data.json"


@pytest.fixture(scope="module")
def model():
    return KETSModel.from_excel("step")


@pytest.fixture(scope="module")
def presets(model):
    return model.msr_presets()


@pytest.fixture(scope="module")
def base_bridge_L0(model, presets):
    return model.level_bridge_path("base", presets["L0"], lam_0=0.0)


@pytest.fixture(scope="module")
def solved_paths(model, presets):
    """base·ideal × 전 프리셋 Hotelling 경로 (모듈 1회 계산)."""
    out = {}
    for sid in ("base", "ideal"):
        out[sid] = {}
        for lid, msr in presets.items():
            out[sid][lid] = model.solve_path(sid, msr)
            assert model.last_fp_converged, f"MSR 고정점 비수렴: {sid}/{lid}"
    return out


# ── 1. 관측가격 앵커 ──
def test_static_anchor_matches_observed_kau(model, base_bridge_L0):
    obs = [r["kau_avg_krw"] for r in model.kau_history
           if r.get("kau_avg_krw") and int(r["year"]) >= 2024]
    assert obs, "KAU과거가격 시트에 2024+ 관측가 없음"
    p_static_2026 = base_bridge_L0[0]["static"]
    ref = float(np.mean(obs))
    assert abs(p_static_2026 - ref) / ref < 0.15, \
        f"정태 2026={p_static_2026:.0f} vs 관측 평균={ref:.0f} — ±15% 이탈"


# ── 2. Excel ↔ JSON 데이터 계약 ──
def test_excel_json_contract_parity(model, presets, base_bridge_L0):
    assert WEB_JSON.exists(), "kets_data.json 없음 — scripts/export_web_data.py 실행 필요"
    mj = KETSModel.from_json(WEB_JSON, "step")
    bj = mj.level_bridge_path("base", mj.msr_presets()["L0"], lam_0=0.0)
    for a, b in zip(base_bridge_L0, bj):
        assert abs(a["static"] - b["static"]) < 1.0
        assert abs(a["hotelling"] - b["hotelling"]) < 1.0


# ── 3·4. banking 비음성 + 무차익 ──
def test_bank_nonnegative_and_no_arbitrage(model, solved_paths):
    growth = float(np.exp(model.r))
    ceil_combos = set()
    for sid, levels in solved_paths.items():
        for lid, path in levels.items():
            for rec in path:
                assert rec["bank_Mt"] >= -1e-6, f"{sid}/{lid}/{rec['year']} bank<0"
            for a, b in zip(path, path[1:]):
                # PRICE_CEIL 도달 = 물리적 비가용 마커(균형 아님) — 무차익 검사 제외.
                # 예: ideal cap × L_QB(무조건 수량보류)는 어떤 가격에도 청산 불가.
                if b["kau"] >= PRICE_CEIL * 0.999 or a["kau"] >= PRICE_CEIL * 0.999:
                    ceil_combos.add((sid, lid))
                    continue
                assert b["kau"] <= a["kau"] * growth * 1.001 + 1, \
                    f"{sid}/{lid} {b['year']} 상향점프 {a['kau']:.0f}→{b['kau']:.0f} (차익기회)"
    # 비가용 마커는 tight cap × 무조건 수량규칙 조합에서만 허용 (확산 시 솔버 점검)
    assert ceil_combos <= {("ideal", "L_QB")}, f"비가용 마커 확산: {ceil_combos}"


# ── 5. MSR 방향성 (무마찰) ──
def test_msr_raises_initial_price_frictionless(solved_paths):
    for sid in ("base", "ideal"):
        p0_L0 = solved_paths[sid]["L0"][0]["kau"]
        for lid in ("L1", "L2", "L3", "L3C", "L4"):
            assert solved_paths[sid][lid][0]["kau"] >= p0_L0 - 1, \
                f"{sid}/{lid} 초기가 {solved_paths[sid][lid][0]['kau']:.0f} < L0 {p0_L0:.0f}"


# ── 6. 유동성 항등식 ──
def test_transmission_identities():
    assert transmission_multiplier(1.0, -0.5) == pytest.approx(1.0)
    assert transmission_multiplier(0.0, 0.0) == pytest.approx(0.0)
    assert transmission_multiplier(0.0, -0.5) < 0.0


def test_realized_collapses_to_frictionless_at_lambda_one(model, presets, solved_paths):
    rp = model.realized_path("base", presets["L3"], psi=-0.25, lam_0=1.0)
    for rec, fri in zip(rp, solved_paths["base"]["L3"]):
        assert rec["kau_realized"] == pytest.approx(fri["kau"], rel=1e-9)
        assert rec["kau_frictionless"] == pytest.approx(fri["kau"], rel=1e-9)


# ── 7. 취소 vs 이연 ──
def test_cancellation_burns_reserve(model, presets, solved_paths):
    def reserve_end(sid, lid):
        cancel = presets[lid]["cancel"]
        reserve = model.reserve0 / 1e6
        for x in solved_paths[sid][lid]:
            reserve += x["intake_Mt"] - x["release_Mt"] - cancel * x["intake_Mt"]
        return reserve
    cum_cancel = sum(presets["L3C"]["cancel"] * x["intake_Mt"]
                     for x in solved_paths["ideal"]["L3C"])
    assert cum_cancel > 0, "ideal cap에서 L3C 취소량 0 — carve/흡수 경로 확인"
    assert reserve_end("ideal", "L3C") <= reserve_end("ideal", "L3") + 1e-6


# ── 8. 정책그리드 단조성 ──
def test_policy_grid_monotonicity(model, base_bridge_L0):
    pf = {r["year"]: float(r["static"]) for r in base_bridge_L0}
    grid = policy_grid(model, "base", pf, "static")
    floors = {f["id"]: f for f in model.floor_levers}
    aucs = model.auction_levers                      # [(aid, ratio)] 시트 순
    # (a) 하한 방어여부: 유상할당 비율 증가에 단조 (같은 floor에서 ✗→✓ 역전 없음)
    for fid in floors:
        prev_ok = None
        for aid, ratio in sorted(aucs, key=lambda x: x[1]):
            ok = all(c["defended"] for c in grid[f"{aid}|{fid}"]["path"])
            if prev_ok is not None:
                assert ok >= prev_ok, f"{fid}: 유상할당↑인데 방어 성공→실패 역전 ({aid})"
            prev_ok = ok
    # (b) 누적감축: 같은 유상할당에서 하한 수준(f40)에 비감소
    for aid, _ in aucs:
        by_floor = sorted(floors.values(), key=lambda f: f["f40"])
        prev = -1.0
        for f in by_floor:
            cum = grid[f"{aid}|{f['id']}"]["cum_abate_Mt"]
            assert cum >= prev - 1e-9, f"{aid}: 하한↑인데 누적감축 감소 ({f['id']})"
            prev = cum


# ── 10. carve-out 회계 ──
def test_reserve_carveout_accounting(model):
    total = sum(model.reserve_carveout("base", yr) for yr in model.years)
    assert total == pytest.approx(model.reserve0, rel=1e-9)
    assert model.reserve_carveout("base", 2031) == 0.0
    assert model.reserve_carveout("base", 2025) == 0.0


# ── v2: 정책 패키지·λ 레짐 (three gates) ──
def test_lambda_regimes(model):
    hold = model.lambda_regime_path("hold")
    rel = model.lambda_regime_path("relapse")
    con = model.lambda_regime_path("consolidate")
    lam0 = model.liquidity["lambda_2026_implied"]
    assert all(abs(x - lam0) < 1e-12 for x in hold)
    assert rel[0] == pytest.approx(lam0) and rel[-1] == 0.0
    assert all(a >= b - 1e-12 for a, b in zip(rel, rel[1:])), "Relapse 단조감소 위반"
    assert con[-1] == pytest.approx(model.liquidity["regime_consolidate_terminal"])


def _pkg_recs(m):
    recs = {}
    for pkg in m.packages:
        path = m.solve_package(pkg)
        prices = [r["kau"] for r in path]
        acts = m.tech_activation_years(prices, pkg["cap_scenario"], headline_only=True)
        h2 = next((y for t, y in acts.items() if "수소환원" in t), None)
        en = next((y for t, y in acts.items() if "NCC" in t or "cracker" in t), None)
        peak, dd = prices[0], 0.0
        for p in prices:
            peak = max(peak, p)
            dd = max(dd, (peak - p) / peak if peak > 0 else 0.0)
        recs[pkg["package_id"]] = {"p2030": prices[4], "h2": h2, "en": en,
                                   "defended": all(r["defended"] for r in path),
                                   "min_headroom": min(r.get("headroom", 1.0) for r in path),
                                   "max_drawdown": dd,
                                   "cum_intake_Mt": sum(r["intake_Mt"] for r in path)}
    return recs


def test_packages_headline_regression(model):
    """v4 회귀 앵커 (P0/P1/A/B): 도입연도·방어·낙폭·누적흡수·서열.

    v4 프레임: K-MSR=법제화 제도, 패키지=운영규칙. 유상=A_gov(정부공표경로,
    base 2026 ~9.9%→2030+ ~23.9%) 일원화. 2026-07-03 라이브 검증 앵커:
      P0/P1 미도입; A(가격약속형)=H2-DRI 2035·e-NCC 2039·방어✓·여유 0.475;
      B(수량약속형)=H2-DRI 2035·e-NCC 2039·낙폭 0.186·누적흡수 268Mt.
    """
    recs = _pkg_recs(model)
    assert set(recs) == {"P0", "P1", "A", "B"}, "정책패키지 시트 v4 구성(P0/P1/A/B) 확인"
    # 서열(2030): P0 ≤ P1 ≤ A, P0 ≤ B — 운영규칙은 기준선 대비 가격신호 강화
    assert recs["P0"]["p2030"] <= recs["P1"]["p2030"] + 1 <= recs["A"]["p2030"] + 2
    assert recs["P0"]["p2030"] <= recs["B"]["p2030"] + 1
    # P0(무정책)·P1(시행령 초안): 두 헤드라인 기술 모두 2040까지 미도입
    for pid in ("P0", "P1"):
        assert recs[pid]["h2"] is None, f"{pid}에서 H2-DRI 조기도입 — 서술 갱신 필요"
        assert recs[pid]["en"] is None, f"{pid}에서 e-NCC 조기도입 — 전력경로 확인 필요"
    # A 가격약속형: 회랑으로 H2-DRI 2035·e-NCC 2039, 전기간 방어, 여유율 0.4–0.55 창
    assert recs["A"]["h2"] == 2035 and recs["A"]["en"] == 2039
    assert recs["A"]["defended"], "A 회랑 방어 실패 — A_gov 용량 확인"
    assert 0.40 <= recs["A"]["min_headroom"] <= 0.55, \
        f"A 여유율 {recs['A']['min_headroom']:.3f} — 0.4–0.55 창 이탈(서술 갱신 확인)"
    # B 수량약속형(B8): 같은 2035 도입을 수량으로 달성, e-NCC 2039±1,
    #   가격 낙폭 ≤25%(질서 있는 경로), 누적흡수 200–350Mt 창
    assert recs["B"]["h2"] == 2035
    assert recs["B"]["en"] is not None and 2038 <= recs["B"]["en"] <= 2040
    assert recs["B"]["max_drawdown"] <= 0.25, \
        f"B 최대낙폭 {recs['B']['max_drawdown']:.3f} — 붕락 위험 서술 갱신 필요"
    assert 200 <= recs["B"]["cum_intake_Mt"] <= 350, \
        f"B 누적흡수 {recs['B']['cum_intake_Mt']:.1f}Mt — 200–350Mt 창 이탈"


def test_price_vs_quantity_rule_diverge_under_conservative_hydrogen():
    """v4 핵심 민감도: 보수 수소가격에서 A(가격약속형)는 회랑이 문턱을 추종(자기보정)해
    H2-DRI 2035를 유지하지만, B(수량약속형)는 수량만 약속하므로 문턱 미달 — A·B 분기."""
    from kets.excel_source import load_data_from_excel
    data = load_data_from_excel()
    data = {**data, "model_params": {**data["model_params"], "h2_scenario": "conservative"}}
    m2 = KETSModel(data, "step")
    cfg = {p["package_id"]: p for p in m2.packages}

    def h2_year(pid):
        path = m2.solve_package(cfg[pid])
        acts = m2.tech_activation_years([r["kau"] for r in path], "base", headline_only=True)
        return next((y for t, y in acts.items() if "수소환원" in t), None), \
            all(r["defended"] for r in path)

    yA, defA = h2_year("A")
    yB, _ = h2_year("B")
    assert yA == 2035 and defA, "A: 보수수소에서도 회랑 자기보정으로 2035 도입·방어 유지"
    assert yB is None, "B: 보수수소에서 H2-DRI 미도입(분기)이 v4 핵심 결과 — 갱신 시 서술 확인"

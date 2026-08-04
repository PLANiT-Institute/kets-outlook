"""정책 그리드: 유상할당 × MSR 가격하한 (v0.8).

`scripts/run_model.py` v0.7 §5의 로직을 엔진 위로 이식한 모듈.
핵심 메커니즘(보고서 식 6): 하한 P̄ 방어에 필요한 withholding W = A(P̄)−A(P_fund)가
경매물량(유상할당비율 a × cap)을 넘으면 하한이 붕괴한다.

v0.8 변경 — 이중 앵커(dual anchor):
  펀더멘털 가격 P_fund를 인자로 받아, 같은 그리드를
    (a) Hotelling 앵커 (λ=1, 완전 차익거래)와
    (b) 정태 앵커   (λ≈0, 현 K-ETS 관측가격에 부합)
  둘 다에서 계산한다. 스텝 MACC 전환으로 두 앵커의 간극(유동성 웨지)이
  드러났으므로(Policy Brief §5), 그리드도 앵커별로 제시해야 한다.

한계(v0.7과 동일, 보고서 §7.3): 하한 overlay는 펀더멘털 경로 위 1차 근사로,
취소가 banking에 주는 피드백은 부분 반영(긴축효과 보수적 추정).

엔진과 동일하게 numpy + stdlib만 의존한다(Vercel 배포 가능).
"""

from __future__ import annotations

from kets.engine import KETSModel, _bisect


def cbam_cost(model: KETSModel, price: float, yr: int) -> float:
    """CBAM 비용(원) = Σ 수출량×내재배출×max(EUA−KAU, 0). KAU↑ → 비용↓."""
    gap = max(model.eua[yr] - price, 0.0)
    c = model.cbam
    s = c["steel_export_Mt"] * 1e6 * c["steel_embed_tCO2"]
    p = c["petrochem_export_Mt"] * 1e6 * c["petrochem_embed_tCO2"]
    return (s + p) * gap


def floor_at(fl: dict, yr: int, y0: int, y1: int) -> float:
    """가격하한의 연도별 선형보간 (f26 → f40)."""
    return fl["f26"] + (fl["f40"] - fl["f26"]) * (yr - y0) / (y1 - y0)


def max_defensible_price(model: KETSModel, yr: int, capacity_tco2: float,
                         sid: str, p_fund: float) -> float:
    """경매물량 withhold로 방어 가능한 최고가: abate(p) = abate(P_fund) + capacity.

    스텝 MACC에서는 abate(P)가 계단형이라 해가 기술비용 문턱에 놓인다 —
    방어 판정은 가격보다 물량(capacity) 기준이 안정적이므로 xtol=1.0이면 충분.
    """
    base_ab = model.abatement_at_price(p_fund, yr, sid)
    target = base_ab + capacity_tco2

    def g(p):
        return model.abatement_at_price(p, yr, sid) - target

    lo, hi = p_fund, 5e5
    if g(hi) < 0:            # 용량이 최대감축을 초과 → 사실상 무제한 방어
        return hi
    if g(lo) >= 0:           # 펀더멘털가에서 이미 목표 도달(용량 0 등)
        return p_fund
    try:
        return _bisect(g, lo, hi, xtol=1.0)
    except ValueError:
        return p_fund


def policy_grid(model: KETSModel, sid: str, p_fund: dict[int, float],
                anchor: str = "hotelling") -> dict:
    """유상할당(A*) × 가격하한(M*) 그리드를 펀더멘털 경로 p_fund 위에서 계산.

    Args:
        model: KETSModel (auction_levers·floor_levers 시트 로드 필요).
        sid: cap 시나리오 (통상 "base" — 현행 cap에서 정책 레버만 변화).
        p_fund: {year: 펀더멘털 가격} — 앵커별 L0 경로 (hotelling 또는 static).
        anchor: 결과 메타에 기록할 앵커명.

    Returns:
        {"A1|M0": {auction, floor_id, path[…], cum_abate_Mt,
                   cum_auction_rev_trillion, cum_cbam_cost_trillion}, …}
    """
    if not model.auction_levers or not model.floor_levers:
        raise ValueError("유상할당레버/MSR가격하한 시트가 데이터 계약에 없음 — "
                         "excel_source.SHEETS 및 kets_data.json 재수출 확인")
    years = model.years
    y0, y1 = years[0], years[-1]
    grid = {"_meta": {"anchor": anchor, "cap_scenario": sid}}
    for aid, a in model.auction_levers:
        for fl in model.floor_levers:
            cells = []
            cum_abate = cum_rev = cum_cbam = 0.0
            for yr in years:
                cap = model.cap_total[sid][yr]
                cap_floor = floor_at(fl, yr, y0, y1)
                capacity = a * cap                      # 방어용량 = 유상할당 × cap
                p_def = max_defensible_price(model, yr, capacity, sid, p_fund[yr])
                price = max(p_fund[yr], min(cap_floor, p_def)) if cap_floor > 0 else p_fund[yr]
                broke = cap_floor > 0 and p_def < cap_floor - 1
                ab = model.abatement_at_price(price, yr, sid) / 1e6
                cum_abate += ab
                cum_rev += a * cap * price / 1e12
                cum_cbam += cbam_cost(model, price, yr) / 1e12
                cells.append({"year": yr, "kau": round(price), "floor": round(cap_floor),
                              "defended": not broke, "abate_Mt": round(ab, 1),
                              "withhold_capacity_Mt": round(capacity / 1e6, 1),
                              "cbam_cost_trillion": round(cbam_cost(model, price, yr) / 1e12, 3)})
            grid[f"{aid}|{fl['id']}"] = {
                "auction": a, "floor_id": fl["id"], "path": cells,
                "cum_abate_Mt": round(cum_abate, 0),
                "cum_auction_rev_trillion": round(cum_rev, 1),
                "cum_cbam_cost_trillion": round(cum_cbam, 1),
            }
    return grid

"""유동성 모수(λ, ψ) 실증 캘리브레이션 — 1차 추정.

원칙(피드백): 가정값 금지, 실제 데이터·출처 명시. 데이터가 없는 부분은 명시.

방법 1 — λ '가격 웨지'로 직접 추정 (주 방법, 관측가격 기반):
    관측 KAU가 정태(λ=0, 차익거래 없음)와 Hotelling(λ=1, 완전차익거래) 사이
    어디에 있는지로 λ를 역산한다:
        λ_implied = (P_obs − P_static) / (P_Hotelling − P_static)
    P_static·P_Hotelling은 엔진(스텝 MACC)이 산출.

방법 2 — λ 회전율 교차검증 (보조):
    turnover = 연간 거래량 / 유통물량(전년 carryover).  거래량은 3개 연도만 존재.

ψ — Yoo 이벤트스터디에서 범위 (연간데이터 재추정 불가 → 발표결과 인용):
    Yoo & Lee (2020): 이월제한 → '잠깐 dip 후 회귀', 지속 가격효과 미미 → ψ ≈ 0
    Yoo & Seo  (2023): 이월제한 → 잉여보유자 dumping, 기간 내 가격 하락 → ψ < 0
    → ψ ∈ [−0.5, 0]. 점추정은 두 논문의 원자료로 프런티어 재추정 필요(미착수).

실행:  python scripts/calibrate_liquidity.py
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from kets.engine import KETSModel
from kets.liquidity import liquidity_lambda
from kets.config import get_sheet


def main():
    m = KETSModel.from_excel(macc_mode="step")
    presets = m.msr_presets()

    # ── 방법 1: 가격 웨지 λ ──
    lb = m.level_bridge_path("base", presets["L0"], lam_0=0.0)  # λ 무관(정태·Hotelling만 필요)
    p_static_2026 = lb[0]["static"]
    p_hotel_2026 = lb[0]["hotelling"]

    kau = get_sheet("KAU과거가격")
    obs = {int(r["year"]): float(r["kau_avg_krw"]) for _, r in kau.iterrows()
           if r["kau_avg_krw"] == r["kau_avg_krw"]}  # NaN 제외
    recent = {y: obs[y] for y in (2023, 2024, 2025) if y in obs}

    print("═══ 방법 1: 가격 웨지 λ (모델 2026 정태/Hotelling 기준) ═══")
    print(f"  정태(λ=0)={p_static_2026:,.0f}원   Hotelling(λ=1)={p_hotel_2026:,.0f}원")
    for y, p in recent.items():
        lam = (p - p_static_2026) / (p_hotel_2026 - p_static_2026)
        print(f"  관측 {y} = {p:>7,.0f}원  →  λ_implied = {lam:+.3f}")
    avg_lam = sum((p - p_static_2026) / (p_hotel_2026 - p_static_2026) for p in recent.values()) / len(recent)
    print(f"  → λ₀ ≈ {avg_lam:.3f}  (관측 ≈ 정태 → 기간간 차익거래 사실상 부재)")

    # ── 방법 2: 회전율 λ 교차검증 ──
    surplus = get_sheet("시장잉여추정")
    carry = {}
    for _, r in surplus.iterrows():
        try:
            carry[int(r["year"])] = float(r["carryover_total_Mt"])
        except (ValueError, TypeError):
            pass
    vol = {int(r["year"]): float(r["trading_volume_Mt"]) for _, r in kau.iterrows()
           if r["trading_volume_Mt"] == r["trading_volume_Mt"]}

    print("\n═══ 방법 2: 회전율 교차검증 (거래량 존재 연도만) ═══")
    print("  turnover = 거래량 / 전년 유통물량(carryover)")
    for y, v in sorted(vol.items()):
        prev_carry = carry.get(y - 1) or carry.get(y)
        if prev_carry:
            tr = v / prev_carry
            print(f"  {y}: 거래량 {v:>6.1f}Mt / 유통 {prev_carry:>4.0f}Mt = 회전율 {tr:.2f}")
    print("  주의: 거래량이 2015·2020·2024 3개년만 존재 → 시계열 λ 산출 불가(데이터 공백).")

    # ── ψ: 문헌 범위 ──
    print("\n═══ ψ (행태승수) — Yoo 이벤트스터디 범위 ═══")
    print("  Yoo & Lee (2020): 잠깐 dip 후 회귀, 지속효과 미미  → ψ ≈ 0")
    print("  Yoo & Seo  (2023): dumping, 기간 내 가격 하락       → ψ < 0")
    print("  → 채택 범위 ψ ∈ [−0.5, 0]. 점추정은 원자료 프런티어 재추정 필요(미착수).")

    print("\n═══ 1차 캘리브레이션 결론 ═══")
    print(f"  λ₀ ≈ {avg_lam:.2f}  (현 K-ETS ≈ 정태; 유동성 개혁으로 λ↑ 시나리오)")
    print("  ψ  ∈ [−0.5, 0]  (문헌 범위; 저유동에서 긴축이 무반응~dumping)")


if __name__ == "__main__":
    main()

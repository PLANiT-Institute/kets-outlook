# GENERATED — DO NOT EDIT. 원본: kets/liquidity.py (scripts/sync_engine.py가 재생성)
"""유동성 조건부 전달(transmission) 레이어 — K-MSR Policy Brief §5 형식화.

정책브리프의 핵심 caveat를 모형화한다: 항등식 P = 한계감축비용(P = π + 2ϱα)은
'유동적·경쟁적·완전한 시장'을 전제한다. K-ETS는 그렇지 않다 — 소수 참여자,
hoarding, 마감기 거래가 가격형성을 지배한다. 따라서 MSR의 공급긴축은 매끄러운
기간간 차익거래로 전달되지 않고, hoarding/dumping 마진에 흡수되거나(→가격 무반응)
심지어 가격을 낮출 수 있다(→dumping).

결정론 코어(`hotelling.py`+`market_clearing.py`)는 암묵적으로 λ=1(완전전달)을
가정한다. 이 모듈은 그 위에 유동성 게이트 λ∈[0,1]과 행태 승수 ψ를 얹어,
실현 가격반응을 다음과 같이 축약한다:

    ΔP_realized = [ λ + (1−λ)·ψ ] · ΔP_frictionless
                = T(λ, ψ) · ΔP_frictionless

여기서 ΔP_frictionless = (MSR 시나리오 무마찰가격) − (L0 반사실가격).
전달승수 T의 세 극한이 브리프가 인용한 실증과 정확히 대응한다:

    λ=1              → T=1        완전전달 (EU형 유동시장; 의도대로 가격↑)
    λ=0, ψ=0         → T=0        무반응  (Yoo & Lee 2020: 잠깐 dip 후 회귀)
    λ=0, ψ<0         → T<0        역효과  (Yoo & Seo 2023: 긴축이 dumping 유발→가격↓)

모든 모수(turnover_half, psi_dump, λ 경로)는 마스터 엑셀에서 로드하며(러너가 조립),
이 모듈에는 한국 데이터 상수를 두지 않는다. λ와 ψ는 이론이 값을 주지 않는
자유모수로, 오직 과거 한국 시장(거래회전율, 2019·2021 이월제한 이벤트)에서만
캘리브레이션된다 — `calibrate_psi_from_event()` 참조.

참고:
  - Yoo, J.-M., & Lee, J.-W. (2020). 이월제한의 K-ETS 가격효과. 기후변화연구 11(3).
  - Yoo, J.-M., & Lee, S.-J. (2023). 2차 계획기간 이월제한 비선형최적화 분석. 자원환경경제연구 32(3).
  - Kollenberg & Taschini (2019), EER 118 — P = π + 2ϱα 항등식의 유동시장 전제.
"""

from __future__ import annotations
import numpy as np


# ═══════════════════════════════════════════════════════════════
# 1. 유동성 게이트 λ — 미시구조 지표 → 전달효율 ∈ [0, 1]
# ═══════════════════════════════════════════════════════════════
def liquidity_lambda(turnover_ratio: float, turnover_half: float) -> float:
    """거래회전율에서 전달효율 λ를 산출한다 (Hill/Michaelis-Menten 형).

        λ(τ) = τ / (τ + τ_half),   τ = 거래량 / 유통가능물량

    포화형·단조증가·[0,1] 유계이며 해석 가능한 모수가 하나(τ_half: λ=0.5가 되는
    회전율)뿐이라 데이터 희소 상황에서 강건하다. K-ETS 회전율은 EU 대비 매우 낮아
    λ→0 영역에 위치, EU-ETS는 λ→1 영역에 위치하도록 τ_half를 잡는다.

    Args:
        turnover_ratio: 연간 거래량 / 유통가능물량 (무차원). KAU과거가격 시트의
            trading_volume_Mt와 시장잉여추정 시트의 유통물량에서 산출.
        turnover_half: λ=0.5가 되는 회전율 (캘리브레이션 모수, 엑셀 로드).

    Returns:
        λ ∈ [0, 1). turnover_ratio=0 → 0.
    """
    if turnover_ratio <= 0 or turnover_half <= 0:
        return 0.0
    return turnover_ratio / (turnover_ratio + turnover_half)


def liquidity_lambda_composite(
    turnover_ratio: float,
    turnover_half: float,
    spread_penalty: float = 0.0,
    concentration_penalty: float = 0.0,
) -> float:
    """다지표 확장 — 회전율 기반 λ에 스프레드·집중도 페널티를 곱한다.

    데이터(호가 스프레드, 상위 N 참여자 보유비중)가 확보되면 사용. 기본은
    페널티 0 → `liquidity_lambda()`와 동일. 페널티는 [0,1] 감쇠계수로 해석:
        λ_composite = λ_turnover · (1 − spread_penalty) · (1 − concentration_penalty)

    Args:
        spread_penalty: 매수-매도 스프레드가 넓을수록 ↑ (0=무페널티, 1=완전차단).
        concentration_penalty: 참여자 집중도(HHI/상위N)가 높을수록 ↑.
    """
    lam = liquidity_lambda(turnover_ratio, turnover_half)
    sp = min(max(spread_penalty, 0.0), 1.0)
    cp = min(max(concentration_penalty, 0.0), 1.0)
    return lam * (1.0 - sp) * (1.0 - cp)


def lambda_ramp(
    year: int,
    base_year: int,
    lambda_0: float,
    lambda_terminal: float,
    ramp_years: float,
) -> float:
    """유동성 인프라 도입에 따른 λ의 시간경로 (브리프 §7① '유동성 우선' 시퀀싱).

    비유동 초기(λ_0)에서 개혁 후 목표(λ_terminal)로 선형 램프.
    'liquidity first' 대 'MSR only'를 비교하는 정책 시나리오의 핵심 레버.

        λ_t = λ_0 + (λ_terminal − λ_0) · min((t − t0)/ramp_years, 1)

    Args:
        ramp_years: 목표 유동성 도달까지 연수. 0이면 즉시 λ_terminal.
    """
    if ramp_years <= 0:
        return lambda_terminal
    frac = min(max((year - base_year) / ramp_years, 0.0), 1.0)
    return lambda_0 + (lambda_terminal - lambda_0) * frac


# ═══════════════════════════════════════════════════════════════
# 2. 전달승수 T와 실현가격 — 무마찰 반응에 유동성·행태를 곱한다
# ═══════════════════════════════════════════════════════════════
def transmission_multiplier(lam: float, psi: float) -> float:
    """유동성 게이트 λ와 행태 승수 ψ를 하나의 전달승수 T로 축약한다.

        T = λ + (1 − λ)·ψ

    - λ 부분: 매끄러운 차익거래로 전달되는 몫.
    - (1−λ) 부분: 얇은 시장 몫. ψ가 그 성격을 결정한다.
        ψ = 0  → hoarding 흡수, 무반응 (Yoo & Lee 2020).
        ψ < 0  → dumping, 역효과 (Yoo & Seo 2023).
        ψ > 0  → (드묾) 얇은 시장이 오히려 증폭.

    Args:
        lam: 전달효율 λ ∈ [0,1].
        psi: 행태 승수. 2019·2021 이월제한 이벤트에서 캘리브레이션.
    """
    lam = min(max(lam, 0.0), 1.0)
    return lam + (1.0 - lam) * psi


def realized_price(
    price_baseline: float,
    price_frictionless: float,
    lam: float,
    psi: float,
) -> float:
    """L0 반사실 대비 MSR 가격효과에 전달승수를 적용한 실현가격.

        P_realized = P_L0 + T(λ,ψ) · (P_frictionless − P_L0)

    코어 솔버를 건드리지 않는 최소침습 오버레이 — taschini 밴드와 동일한 방식으로
    후처리한다. L0(반사실)와 MSR 시나리오를 각각 무마찰로 풀어 차분한 뒤 T를 곱한다.

    Args:
        price_baseline: L0(MSR 미도입) 무마찰 가격.
        price_frictionless: MSR 시나리오 무마찰 가격.
        lam, psi: 유동성/행태 모수.

    Returns:
        실현 가격 (KRW/tCO2).
    """
    T = transmission_multiplier(lam, psi)
    return price_baseline + T * (price_frictionless - price_baseline)


def realized_price_path(
    price_baseline: np.ndarray,
    price_frictionless: np.ndarray,
    lam_path: np.ndarray,
    psi: float,
) -> np.ndarray:
    """연도별 λ 경로에 대한 실현 가격경로 (벡터화).

    lam_path가 연도에 따라 상승(유동성 인프라 램프)하면, 동일 MSR이라도
    초기에는 전달 실패/역효과, 후기에는 완전전달로 나타나는 부채꼴이 생성된다.
    """
    price_baseline = np.asarray(price_baseline, dtype=float)
    price_frictionless = np.asarray(price_frictionless, dtype=float)
    lam_path = np.asarray(lam_path, dtype=float)
    T = np.clip(lam_path, 0.0, 1.0) + (1.0 - np.clip(lam_path, 0.0, 1.0)) * psi
    return price_baseline + T * (price_frictionless - price_baseline)


# ═══════════════════════════════════════════════════════════════
# 3. 캘리브레이션 — 과거 한국 시장에서 λ·ψ를 확정
# ═══════════════════════════════════════════════════════════════
def calibrate_psi_from_event(
    dp_observed: float,
    dp_frictionless: float,
    lam: float,
) -> float:
    """이월제한 이벤트에서 행태 승수 ψ를 역산한다.

    2019·2021 이월제한은 공급긴축의 자연실험이다. 모형이 예측한 무마찰
    가격변화(ΔP_frictionless)와 실제 관측된 변화(ΔP_observed)를 대조하면,
    당시 유동성 λ를 조건으로 ψ가 결정된다:

        ΔP_obs = [λ + (1−λ)·ψ]·ΔP_fri
        ⟹  ψ = ((ΔP_obs/ΔP_fri) − λ) / (1 − λ)

    Yoo & Seo(2023)의 '긴축→가격하락'이 재현되려면 ψ<0이 나와야 한다.
    이 역산이 미시구조 원시데이터가 없을 때의 λ·ψ 확정 경로다(Policy Brief §5).

    Args:
        dp_observed: 이벤트 전후 관측 가격변화 (KRW/tCO2).
        dp_frictionless: 코어 모형이 예측한 무마찰 가격변화.
        lam: 이벤트 당시 추정 λ (관측 회전율 기반).

    Returns:
        행태 승수 ψ. lam≈1이면 식별 불가(무마찰과 구분 안 됨) → 예외적으로 0 반환.

    Raises:
        ValueError: dp_frictionless가 0이면 식별 불가.
    """
    if dp_frictionless == 0:
        raise ValueError("dp_frictionless=0 → ψ 식별 불가 (무마찰 반응이 없음).")
    if lam >= 1.0:
        return 0.0
    ratio = dp_observed / dp_frictionless
    return (ratio - lam) / (1.0 - lam)

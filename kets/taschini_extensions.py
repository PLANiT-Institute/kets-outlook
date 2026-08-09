"""Taschini 이론에 근거한 K-MSR 모형 확장.

v0.7 결정론 모형(`run_model.py`)이 §7.3에서 명시적으로 미반영한 세 채널을
Luca Taschini의 핵심 논문에 따라 형식화한다. 모든 모수는 마스터 엑셀에서 로드한다.

  1. 불확실성 채널 — Kollenberg & Taschini (2019), EER 118:213-226
       위험회피 기업은 MSR이 키운 banking 스톡 분산에 위험프리미엄을 요구한다.
       위험중립(γ=0)이면 캡보존형 MSR은 기대가격에 무관(KT2019 명제).
       위험회피(γ>0)이면 잉여기 가격에 하방 프리미엄이 작용해 워터베드를 일부 상쇄.
         premium_t = ½·γ·κ·σ²·(B_t / Cap_t)
       → 결정론 중심경로 P_t 둘레에 위험조정 가격밴드를 만든다.

  2. 옵션분해 — Grüll & Taschini (2011), JEEM 61(1):107-118
       가격하한 P̄는 정부가 시장에 발행한 풋옵션, 가격상한은 콜옵션과 동형.
       Black-76으로 하한 방어의 옵션가치를 평가한다. 방어물량(풋 행사량)이
       경매물량(유상할당×cap)으로 제약된다는 보고서 식(6)을 옵션틀로 해석.

  3. Carbon Cap Rule — Benmir, Roman & Taschini (2025), LSE GRI WP421
       가격편차에 반응하는 규칙기반 동적 cap(테일러준칙 analog):
         ΔCap_t = −φ·((P_t − P*_t)/P*_t)·Cap_t,   P*_t = ratio·EUA_t
       물량편차(TNAC)에 반응하는 K-MSR과 대비. 저유동성 한국 시장 적합성 비교.

참고: Parsons & Taschini (2013)은 정성적 근거(영구적 비용충격→수량규칙 우월)로
      K-MSR의 수량기반 설계를 정당화하며, 본 모듈은 그 위에 가격하한(가격규칙)을 얹는다.
"""

from __future__ import annotations
import math


# ═══════════════════════════════════════════════════════════════
# 1. Kollenberg & Taschini (2019) — 불확실성 / 위험프리미엄 채널
# ═══════════════════════════════════════════════════════════════
def banking_risk_premium(bank_tco2: float, cap_tco2: float, gamma: float,
                         sigma: float, kappa: float = 1.0) -> float:
    """위험회피 기업의 banking 위험프리미엄 (가격 대비 비율).

    KT2019: MSR이 banking 경로의 분산에 작용한다. CRRA 위험회피 하에서
    잉여(banked) 포지션을 보유한 기업은 certainty-equivalent 가격에
    프리미엄을 요구하며, 그 크기는 위험회피도와 희소성 분산에 비례한다.

        premium = ½ · γ · κ · σ² · (B_t / Cap_t)

    부호: 잉여 보유기(B>0)에는 가격 하방 압력(워터베드 상쇄)으로 해석하여
    중심가격에 (1 − premium)을 곱한 하단, (1 + premium)을 곱한 상단으로 밴드화.

    Returns: premium ∈ [0, ~), 가격에 대한 비율(예: 0.08 = ±8%).
    """
    if cap_tco2 <= 0 or gamma <= 0:
        return 0.0
    scarcity_ratio = max(bank_tco2, 0.0) / cap_tco2
    return 0.5 * gamma * kappa * (sigma ** 2) * scarcity_ratio


def risk_adjusted_band(price: float, bank_tco2: float, cap_tco2: float,
                       gamma: float, sigma: float, kappa: float = 1.0) -> dict:
    """결정론 중심가격 둘레의 위험조정 밴드.

    KT2019의 핵심 함의를 결정론 모형 위에 1차 근사로 얹는다:
      - 위험중립(γ=0): 밴드폭 0 → 중심가격과 동일(KT2019 명제 재현).
      - 위험회피(γ>0)·잉여 큼: 하단이 크게 낮아짐 → MSR 잉여기 가격하락 채널.
    """
    prem = banking_risk_premium(bank_tco2, cap_tco2, gamma, sigma, kappa)
    return {
        "central": price,
        "premium_ratio": prem,
        "lower": price * (1.0 - prem),
        "upper": price * (1.0 + prem),
    }


# ═══════════════════════════════════════════════════════════════
# 2. Grüll & Taschini (2011) — 가격하한/상한의 옵션분해 (Black-76)
# ═══════════════════════════════════════════════════════════════
def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _black76_put(forward: float, strike: float, vol: float, T: float, rf: float) -> float:
    """Black-76 선도가격 풋옵션가치. (단위: 가격과 동일)"""
    if T <= 0 or vol <= 0 or forward <= 0 or strike <= 0:
        return max(strike - forward, 0.0) * math.exp(-rf * max(T, 0.0))
    d1 = (math.log(forward / strike) + 0.5 * vol ** 2 * T) / (vol * math.sqrt(T))
    d2 = d1 - vol * math.sqrt(T)
    disc = math.exp(-rf * T)
    return disc * (strike * _norm_cdf(-d2) - forward * _norm_cdf(-d1))


def price_floor_put_value(fundamental_price: float, floor_price: float,
                          vol: float, T: float, rf: float) -> float:
    """가격하한을 정부 발행 풋옵션으로 평가 (GT2011).

    하한 P̄ 보장 = 시장참여자가 행사가 P̄ 풋을 보유. 선도가격 F=펀더멘털가.
    옵션가치가 클수록 하한 방어에 내재된 정부 부담(=거둬들일 물량의 가치)이 크다.

    ponytail: 유럽형 풋 하나로 근사. 경매마다 하한을 거는 규칙은 엄밀히는 경매 횟수만큼의
    유럽형 풋 다발이며 다발 가치 ≠ 단일 옵션 가치(만기별 분산이 다르고 행사가가 에스컬레이션
    경로를 따른다). 따라서 방어비용의 수준이 아니라 하한 간 상대 비교에만 쓴다. 수준이
    필요해지면 경매 일정에 맞춘 만기 사다리로 재구현하라 — docs/methodology.md §7.1.
    """
    return _black76_put(fundamental_price, floor_price, vol, T, rf)


def price_ceiling_call_value(fundamental_price: float, ceiling_price: float,
                             vol: float, T: float, rf: float) -> float:
    """가격상한을 콜옵션으로 평가 (GT2011). 칼라=풋 매수+콜 매도."""
    if T <= 0 or vol <= 0:
        return max(fundamental_price - ceiling_price, 0.0) * math.exp(-rf * max(T, 0.0))
    d1 = (math.log(fundamental_price / ceiling_price) + 0.5 * vol ** 2 * T) / (vol * math.sqrt(T))
    d2 = d1 - vol * math.sqrt(T)
    disc = math.exp(-rf * T)
    return disc * (fundamental_price * _norm_cdf(d1) - ceiling_price * _norm_cdf(d2))


# ═══════════════════════════════════════════════════════════════
# 3. Benmir, Roman & Taschini (2025) — Carbon Cap Rule (CCR)
# ═══════════════════════════════════════════════════════════════
def carbon_cap_rule_adjustment(price: float, target_price: float, cap_tco2: float,
                               phi: float, max_adjust: float = 0.15) -> float:
    """가격편차에 비례한 cap 조정량 ΔCap (tCO2). 음수=긴축(가격 낮을 때 cap 축소).

    BRT2025: ΔCap_t = −φ·((P_t − P*_t)/P*_t)·Cap_t, 단 |ΔCap/Cap| ≤ max_adjust.
    가격이 목표 미달(P<P*)이면 양(+) → cap 축소(공급 흡수)로 가격 부양.
    """
    if target_price <= 0 or cap_tco2 <= 0:
        return 0.0
    dev = (price - target_price) / target_price          # 가격 갭(상대)
    raw = -phi * dev * cap_tco2                            # 음(−)이면 cap 확대
    limit = max_adjust * cap_tco2
    return max(min(raw, limit), -limit)


def ccr_vs_tnac_summary(price: float, target_price: float, tnac_tco2: float,
                        cap_tco2: float, phi: float, theta_plus_tco2: float,
                        rho: float, max_adjust: float = 0.15) -> dict:
    """동일 시점에서 CCR(가격규칙)과 K-MSR(물량규칙)의 공급조정을 병렬 산출.

    저유동성 한국 시장 함의 비교용:
      - CCR: 가격신호에 직접 반응(빠르나 신뢰가능 가격 필요).
      - TNAC: 물량잉여에 반응(느리나 thin trading에 견고).
    """
    ccr_dcap = carbon_cap_rule_adjustment(price, target_price, cap_tco2, phi, max_adjust)
    tnac_intake = rho * max(tnac_tco2 - theta_plus_tco2, 0.0)   # K-MSR 흡수(양=공급감소)
    return {
        "ccr_dcap_Mt": ccr_dcap / 1e6,            # 음수=cap축소(긴축)
        "ccr_supply_change_Mt": ccr_dcap / 1e6,    # cap조정이 곧 공급변화
        "tnac_intake_Mt": tnac_intake / 1e6,       # 양수=흡수(공급감소)
        "tnac_supply_change_Mt": -tnac_intake / 1e6,
        "price_gap_pct": round(100 * (price - target_price) / target_price, 1) if target_price > 0 else None,
    }

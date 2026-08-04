"""Taschini 확장 모듈 단위테스트 — 이론적 성질 검증."""

import math
import pytest

from kets.taschini_extensions import (
    banking_risk_premium, risk_adjusted_band,
    price_floor_put_value, price_ceiling_call_value,
    carbon_cap_rule_adjustment, ccr_vs_tnac_summary,
)


# ── KT2019: 위험중립이면 프리미엄 0 (핵심 명제) ──
def test_risk_neutral_zero_premium():
    assert banking_risk_premium(70e6, 500e6, gamma=0.0, sigma=0.3) == 0.0
    b = risk_adjusted_band(10000, 70e6, 500e6, gamma=0.0, sigma=0.3)
    assert b["lower"] == b["upper"] == b["central"] == 10000


def test_premium_increases_with_scarcity():
    """잉여(banking) 클수록 위험프리미엄 증가."""
    low = banking_risk_premium(20e6, 500e6, gamma=2.0, sigma=0.3)
    high = banking_risk_premium(80e6, 500e6, gamma=2.0, sigma=0.3)
    assert high > low > 0


def test_premium_formula_matches_closed_form():
    """premium = ½·γ·κ·σ²·(B/Cap)."""
    got = banking_risk_premium(100e6, 500e6, gamma=2.0, sigma=0.3, kappa=1.0)
    expected = 0.5 * 2.0 * 1.0 * 0.3**2 * (100e6 / 500e6)
    assert got == pytest.approx(expected)


# ── GT2011: 깊은 ITM 풋 ≈ 할인된 내재가치 ──
def test_deep_itm_put_approx_discounted_intrinsic():
    fund, floor, vol, T, rf = 15552, 150000, 0.35, 14, 0.035
    val = price_floor_put_value(fund, floor, vol, T, rf)
    intrinsic = math.exp(-rf * T) * (floor - fund)
    assert val >= intrinsic                      # 시간가치로 내재가치 이상
    assert val == pytest.approx(intrinsic, rel=0.05)


def test_higher_floor_higher_put_value():
    """하한이 높을수록(더 ITM) 풋가치 증가 = 정부 방어부담 증가."""
    v_mid = price_floor_put_value(15552, 50000, 0.35, 14, 0.035)
    v_max = price_floor_put_value(15552, 150000, 0.35, 14, 0.035)
    assert v_max > v_mid > 0


def test_floor_at_zero_horizon_is_intrinsic():
    assert price_floor_put_value(10000, 25000, 0.35, 0, 0.035) == pytest.approx(15000)


# ── BRT2025: 가격이 목표 미달이면 cap 긴축(공급 흡수) ──
def test_ccr_tightens_when_price_below_target():
    dcap = carbon_cap_rule_adjustment(price=10000, target_price=50000,
                                      cap_tco2=500e6, phi=0.5)
    assert dcap > 0                              # 양수 = cap 축소(공급 감소→가격 부양)


def test_ccr_respects_max_adjust_cap():
    dcap = carbon_cap_rule_adjustment(price=1, target_price=100000,
                                      cap_tco2=500e6, phi=0.5, max_adjust=0.15)
    assert dcap == pytest.approx(0.15 * 500e6)   # 상한에서 클립


def test_ccr_vs_tnac_both_tighten_in_surplus_lowprice():
    s = ccr_vs_tnac_summary(price=10000, target_price=50000, tnac_tco2=70e6,
                            cap_tco2=500e6, phi=0.5, theta_plus_tco2=30e6,
                            rho=0.24, max_adjust=0.15)
    assert s["ccr_supply_change_Mt"] > 0         # CCR 긴축
    assert s["tnac_supply_change_Mt"] < 0        # TNAC 흡수(공급감소)

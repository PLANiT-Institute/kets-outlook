"""시장청산 테스트."""

from kets.market_clearing import excess_demand


def test_excess_demand_sign():
    """높은 가격에서 초과수요는 음수 (공급 과잉)."""
    # beta는 tCO2당 한계비용 기울기: a(P) = ln(P/alpha)/beta (tCO2).
    # P=100,000 → a = ln(20)/5e-7 ≈ 6.0Mt > shortfall 1Mt (음수 초과수요),
    # P=5,001  → a ≈ 0.0004Mt < 1Mt (양수 초과수요)가 되도록 스케일 정합.
    params = [{
        "sector_code": "steel",
        "alpha": 5000.0,
        "beta": 5e-7,
        "functional_form": "exponential",
        "max_abatement_tco2": 50_000_000,
    }]
    shortfalls = {"steel": 1_000_000}

    # 매우 높은 가격 → 감축량 > shortfall → 초과수요 음수
    ed = excess_demand(100_000, params, shortfalls)
    assert ed < 0, f"Expected negative excess demand at high price, got {ed}"

    # 매우 낮은 가격 → 감축량 < shortfall → 초과수요 양수
    ed_low = excess_demand(5_001, params, shortfalls)
    assert ed_low > 0, f"Expected positive excess demand at low price, got {ed_low}"

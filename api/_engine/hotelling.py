# GENERATED — DO NOT EDIT. 원본: kets/hotelling.py (scripts/sync_engine.py가 재생성)
"""Hotelling 가격 동학 (v0.6).

Banking이 허용된 배출권 시장에서 균형가격은 지수적 경로를 따른다:
    P_t = P_0 * exp(r * t)

여기서 r = 무위험금리 + 리스크프리미엄.

v0.6: banking_stock_path() 추가 — 연도별 banking 잔고 추적.
Banking stock ≥ 0 제약은 solver에서 처리.
"""

import numpy as np


def hotelling_price_path(
    p0: float,
    r: float,
    years: list[int] | np.ndarray,
    base_year: int | None = None,
) -> np.ndarray:
    """Hotelling 규칙에 따른 가격 경로를 생성한다.

    Args:
        p0: 기준년도 균형가격 (KRW/tCO2)
        r: 실효 할인율 (discount_rate + risk_premium)
        years: 연도 배열
        base_year: 기준년도 (None이면 years의 첫 해)

    Returns:
        연도별 가격 배열 (KRW/tCO2)
    """
    years = np.asarray(years)
    if base_year is None:
        base_year = years[0]
    t = years - base_year
    return p0 * np.exp(r * t)


def banking_stock_path(
    prices: np.ndarray,
    shortfalls: dict[int, float],
    years: list[int],
    abatement_fn,
    initial_bank: float = 0.0,
) -> np.ndarray:
    """Hotelling 가격 경로에서 연도별 banking stock을 추적한다.

    Banking stock_t = stock_{t-1} + abatement(P_t) - shortfall_t
    양수 = 잉여 배출권 축적, 음수 = 부족 (규정 위반)

    Args:
        prices: 연도별 가격 배열
        shortfalls: {연도: fundamental_shortfall (tCO2)}
        years: 연도 리스트
        abatement_fn: abatement_at_price(price, year) → tCO2
        initial_bank: 초기 banking stock (기본 0)

    Returns:
        연도별 banking stock 배열 (tCO2)
    """
    stocks = np.zeros(len(years))
    bank = initial_bank
    for i, yr in enumerate(years):
        net = abatement_fn(prices[i], yr) - shortfalls[yr]
        bank += net
        stocks[i] = bank
    return stocks


def effective_rate() -> float:
    """model_params에서 실효 할인율을 계산한다.

    주의: pandas/yaml 의존은 이 함수 안에서만 발생해야 한다 —
    모듈 수준 import 시 Vercel(stdlib+numpy) 런타임이 깨진다.
    """
    from api._engine.config import load_model_params

    params = load_model_params()
    h = params["hotelling"]
    return h["discount_rate"] + h["risk_premium"]

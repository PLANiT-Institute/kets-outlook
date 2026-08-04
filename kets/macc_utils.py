"""MACC (Marginal Abatement Cost Curve) 유틸리티.

함수형태:
  MAC(a) = alpha * exp(beta * a)       (지수형)
  MAC(a) = alpha * a^beta              (거듭제곱형)

역함수 (가격 → 감축량):
  a(P) = (1/beta) * ln(P/alpha)        (지수형)
  a(P) = (P/alpha)^(1/beta)            (거듭제곱형)
"""

import numpy as np


def mac_exponential(a: float | np.ndarray, alpha: float, beta: float) -> float | np.ndarray:
    """지수형 한계감축비용: MAC(a) = alpha * exp(beta * a)"""
    return alpha * np.exp(beta * a)


def inverse_mac_exponential(
    price: float | np.ndarray, alpha: float, beta: float
) -> float | np.ndarray:
    """지수형 MACC 역함수: a(P) = (1/beta) * ln(P/alpha)

    P < alpha이면 감축량 0 (가격이 최소 감축비용 미만).
    """
    price = np.asarray(price, dtype=float)
    result = np.where(price > alpha, (1.0 / beta) * np.log(price / alpha), 0.0)
    return float(result) if result.ndim == 0 else result


def mac_power(a: float | np.ndarray, alpha: float, beta: float) -> float | np.ndarray:
    """거듭제곱형 한계감축비용: MAC(a) = alpha * a^beta"""
    return alpha * np.power(np.maximum(a, 0), beta)


def inverse_mac_power(
    price: float | np.ndarray, alpha: float, beta: float
) -> float | np.ndarray:
    """거듭제곱형 MACC 역함수: a(P) = (P/alpha)^(1/beta)"""
    price = np.asarray(price, dtype=float)
    result = np.where(price > 0, np.power(price / alpha, 1.0 / beta), 0.0)
    return float(result) if result.ndim == 0 else result


def total_abatement_cost(
    abatement: float, alpha: float, beta: float, form: str = "exponential"
) -> float:
    """총 감축비용 = ∫₀ᵃ MAC(x) dx (MACC 아래 면적).

    지수형: (alpha/beta) * [exp(beta*a) - 1]
    """
    if form == "exponential":
        return (alpha / beta) * (np.exp(beta * abatement) - 1.0)
    elif form == "power":
        return (alpha / (beta + 1.0)) * np.power(abatement, beta + 1.0)
    else:
        raise ValueError(f"Unknown functional form: {form}")


def get_inverse_mac(form: str = "exponential"):
    """함수형태에 따른 역 MACC 함수를 반환한다."""
    if form == "exponential":
        return inverse_mac_exponential
    elif form == "power":
        return inverse_mac_power
    else:
        raise ValueError(f"Unknown functional form: {form}")

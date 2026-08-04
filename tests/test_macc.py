"""MACC 유틸리티 테스트."""

import numpy as np
import pytest
from kets.macc_utils import (
    mac_exponential,
    inverse_mac_exponential,
    total_abatement_cost,
)


def test_mac_inverse_consistency():
    """MAC과 역함수가 일관적인지 확인."""
    alpha, beta = 5000.0, 0.00005
    abatement = 10000.0  # tCO2

    price = mac_exponential(abatement, alpha, beta)
    recovered = inverse_mac_exponential(price, alpha, beta)
    assert abs(recovered - abatement) < 1.0, f"Expected ~{abatement}, got {recovered}"


def test_inverse_mac_below_alpha():
    """가격이 alpha 미만이면 감축량 0."""
    alpha, beta = 5000.0, 0.00005
    assert inverse_mac_exponential(4000.0, alpha, beta) == 0.0


def test_total_abatement_cost_positive():
    """총 감축비용이 양수."""
    alpha, beta = 5000.0, 0.00005
    cost = total_abatement_cost(10000.0, alpha, beta, "exponential")
    assert cost > 0


def test_mac_monotonic():
    """MAC은 감축량에 대해 단조 증가."""
    alpha, beta = 5000.0, 0.00005
    a1, a2 = 5000.0, 10000.0
    assert mac_exponential(a2, alpha, beta) > mac_exponential(a1, alpha, beta)

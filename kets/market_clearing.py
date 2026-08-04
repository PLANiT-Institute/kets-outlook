"""시장청산 조건 (v0.6).

균형 조건 (Coase 정리):
    Σ_s a_s(P_t) = Σ_s (BAU_{s,t} - Cap_{s,t})

좌변: 가격 P에서 각 산업의 감축량 합 (MACC 역함수)
우변: 각 산업의 fundamental shortfall = BAU - Cap

핵심: shortfall은 BAU - Cap으로 정의. 무상할당 비율은 균형가격에 무관 (Coase 정리).
무상할당은 재정 분석(경매수입, 기업비용 분배)에서만 사용.
"""

import numpy as np
from kets.macc_utils import get_inverse_mac


def excess_demand(
    price: float,
    sector_params: list[dict],
    shortfalls: dict[str, float],
) -> float:
    """주어진 가격에서의 초과수요를 계산한다.

    초과수요 = 총 fundamental shortfall - 총 감축량
    균형에서 excess_demand = 0.

    Args:
        price: 후보 균형가격 (KRW/tCO2)
        sector_params: 각 산업의 MACC 파라미터 리스트
            [{"sector_code": str, "alpha": float, "beta": float,
              "functional_form": str, "max_abatement_tco2": float}, ...]
        shortfalls: 산업별 fundamental shortfall = BAU - Cap (tCO2)
            무상할당 비율은 여기에 포함하지 않음.

    Returns:
        초과수요 (양수 = 가격 상승 필요, 음수 = 가격 하락 필요)
    """
    total_shortfall = sum(shortfalls.values())

    total_abatement = 0.0
    for sp in sector_params:
        inv_mac = get_inverse_mac(sp["functional_form"])
        abatement = inv_mac(price, sp["alpha"], sp["beta"])
        # 최대 감축량 제약
        max_abate = sp.get("max_abatement_tco2", np.inf)
        abatement = min(abatement, max_abate)
        total_abatement += abatement

    return total_shortfall - total_abatement

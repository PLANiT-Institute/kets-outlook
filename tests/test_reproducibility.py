"""골든 회귀 — 보고서에 인쇄된 헤드라인 수치가 저장된 산출물과 일치하는지 잠근다.

이 리포의 실패 모드는 "엔진을 고쳤는데 보고서 숫자가 조용히 달라지는 것"이다.
아래 상수는 docs/report.md에 실제로 인쇄된 값이며, 여기서 깨지면 보고서도
같이 고쳐야 한다는 신호다. 값을 맞추려고 상수를 바꾸지 말고, 왜 달라졌는지
먼저 확인하라.

산출물 재생성:
    python3 scripts/run_model.py            → msr_results_v1.0.json
    python3 scripts/run_escalator_floor.py  → escalator_floor_cce_v2.0.json
    python3 scripts/build_carry_analysis.py → carry_analysis_cce_v2.0.json
"""

import json
from pathlib import Path

import pytest

RUNS = Path(__file__).resolve().parents[1] / "outputs" / "runs"


def _load(name):
    path = RUNS / name
    if not path.exists():
        pytest.skip(f"{name} 없음 — scripts/ 러너를 먼저 실행")
    return json.loads(path.read_text(encoding="utf-8"))


# ─── P0 무정책 반사실 균형가격 (docs/report.md §2) ───

def test_p0_equilibrium_prices():
    path = _load("msr_results_v1.0.json")["packages"]["P0"]["path"]
    kau = {r["year"]: round(r["kau"]) for r in path}
    assert (kau[2026], kau[2030], kau[2040]) == (22_749, 46_159, 67_461)


def test_lambda_regime_is_calibrated_not_zero():
    """λ=0.575는 2026 관측가(22,750원)에서 역산한 값 — 0으로 돌아가면 전달채널이 죽은 것."""
    row = _load("msr_results_v1.0.json")["packages"]["P0"]["path"][0]
    assert row["lambda"] == pytest.approx(0.575, abs=1e-9)
    assert row["static"] < row["kau"] < row["hotelling"], "실현가는 정태와 Hotelling 사이"
    # λ를 관측가에서 역산했으므로 레벨-브리지가 되돌아가야 한다
    # (JSON은 원 단위 반올림 저장 → 허용오차 1e-3)
    implied = (row["kau"] - row["static"]) / (row["hotelling"] - row["static"])
    assert implied == pytest.approx(row["lambda"], abs=1e-3)


# ─── 경매 최저가격 에스컬레이션 (docs/report.md §4, Table 1) ───

EXPECTED_2040_FLOOR = {
    "40k_7pct": 103_141, "45k_7pct": 116_034, "50k_7pct": 128_927,
    "45k_5.5pct": 95_224, "50k_5.5pct": 105_805,
}


@pytest.mark.parametrize("case,floor_2040", EXPECTED_2040_FLOOR.items())
def test_escalator_floor_2040(case, floor_2040):
    data = _load("escalator_floor_cce_v2.0.json")[case]
    assert round(data["floor"]["2040"]) == floor_2040


def test_every_escalator_case_defends_its_floor():
    """하한이 방어되지 않으면 정책 권고 자체가 성립하지 않는다."""
    data = _load("escalator_floor_cce_v2.0.json")
    for case in EXPECTED_2040_FLOOR:
        assert data[case]["defended_all"] is True, case


# ─── 캐리(인접 빈티지) 실증 (docs/report.md §3) ───

def test_carry_sample_sizes():
    c = _load("carry_analysis_cce_v2.0.json")
    assert c["kau_vintage_day_quotes"] == 8_513
    assert c["all_quote_pairs"]["n_pairs"] == 5_693
    assert c["both_traded_pairs"]["n_pairs"] == 253


def test_initial_bank_matches_registry():
    """모형 B0(마스터 엑셀)와 등록부 실측 이월잔고가 같아야 한다.

    과거에 이 둘이 갈렸다(시트 70Mt vs 등록부 92.14Mt) — 러너마다 다른 기준선을
    쓰면 같은 보고서 안에서 숫자가 어긋난다. 이 테스트가 그 재발을 막는다.
    """
    b0 = _load("msr_results_v1.0.json")["params"]["B0_Mt"]
    registry = _load("carry_analysis_cce_v2.0.json")["bank_2024_Mt"]
    floor_run = _load("escalator_floor_cce_v2.0.json")["meta"]["initial_bank_Mt"]
    assert b0 == pytest.approx(registry, abs=1e-6)
    assert floor_run == pytest.approx(registry, abs=1e-6)


def test_observed_bank_2024():
    """2024년 관측 이월잔고 — 모형 초기 은행잔고의 실측 앵커."""
    assert _load("carry_analysis_cce_v2.0.json")["bank_2024_Mt"] == pytest.approx(92.140327)

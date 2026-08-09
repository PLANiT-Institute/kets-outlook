"""시나리오 레버 — "다른 세계였다면?"을 API·MCP에서 실제로 물을 수 있는가.

패키지 레버(P0/P1/A/B, 하한, 유상할당)가 **정부가 무엇을 약속하는가**라면,
여기서 잠그는 네 레버는 **어떤 세계에서 그 약속을 하는가**다.

  h2_scenario      수소가격 경로  → H₂-DRI 비용 (수소가격시나리오 시트)
  elec_scenario    전력가격 경로  → e-NCC·전기가열로 비용 (전력가격시나리오 시트)
  tech_scenario    학습곡선       → 에너지집약도가 없는 기술의 비용하락 (학습곡선 시트)
  cost_multiplier  자본비용 배율  → MACC 수준 자체 (논문 ±20% 민감도)

세 레버는 서로 다른 비용 채널을 탄다. 헤드라인 2기술(H₂-DRI·e-NCC)은 에너지가격
채널로 움직이므로 tech_scenario에 반응하지 않는다 — 이는 설계이며
`test_tech_scenario_moves_non_energy_techs_only`가 그 경계를 명시한다.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from api import solve  # noqa: E402
from kets.engine import KETSModel  # noqa: E402

HEADLINE_STEEL = "수소환원제철 (H₂-DRI-EAF)"
HEADLINE_NCC = "NCC 전기분해로(e-cracker)"


def _activation(**overrides):
    r = solve.run_package({"package_id": overrides.pop("package_id", "A"),
                           "overrides": overrides})
    a = r["activation_headline"]
    return a.get(HEADLINE_STEEL), a.get(HEADLINE_NCC)


# ── 발견 가능성: 도구를 쓰는 쪽이 값 목록을 알 수 있어야 한다 ──

def test_levers_are_discoverable_with_values_from_sheets():
    levers = solve.meta()["model_levers"]
    assert set(levers) == {"h2_scenario", "elec_scenario", "tech_scenario", "cost_multiplier"}
    assert levers["h2_scenario"]["values"] == ["gov", "conservative"]
    assert levers["elec_scenario"]["values"] == ["gov_invest", "conservative"]
    assert levers["tech_scenario"]["values"] == ["base", "middle", "ideal"]
    assert levers["cost_multiplier"]["range"] == [0.1, 5.0]


def test_response_reports_effective_levers():
    """무엇이 실제로 적용됐는지 응답이 되돌려준다 — 조용한 무시를 막는다."""
    meta = solve.run_package({"package_id": "A",
                              "overrides": {"h2_scenario": "conservative",
                                            "unknown_key": 123}})["meta"]
    assert meta["model_levers"]["h2_scenario"] == "conservative"
    assert meta["model_levers"]["explicit"] == {"h2_scenario": "conservative"}
    assert "unknown_key" not in meta["model_levers"]["explicit"]


@pytest.mark.parametrize("key,bad", [("h2_scenario", "nope"), ("elec_scenario", "nope"),
                                     ("tech_scenario", "nope"), ("cost_multiplier", 99)])
def test_unknown_lever_value_raises(key, bad):
    """오타를 조용히 기본값으로 흘리면 사용자가 안 돌아간 시나리오를 인용하게 된다."""
    with pytest.raises(ValueError):
        solve.run_package({"package_id": "A", "overrides": {key: bad}})


# ── 에너지가격 채널: 논문 §7의 A·B 분기를 API 경로에서 재현 ──

def test_h2_lever_reproduces_paper_2x2():
    """API 레버로 돌린 결과가 run_model.py의 2×2 민감도 셀과 일치한다.

    깨지면 웹·MCP 사용자가 보는 숫자와 논문 표가 갈라진 것이다.
    """
    assert _activation(package_id="A", h2_scenario="conservative",
                       elec_scenario="gov_invest") == (2035, 2037)
    assert _activation(package_id="B", h2_scenario="conservative",
                       elec_scenario="gov_invest") == (None, 2039)


def test_conservative_electricity_kills_the_e_cracker():
    """전력가격이 안 떨어지면 e-NCC는 어떤 패키지에서도 활성화되지 않는다."""
    for pid in ("A", "B"):
        assert _activation(package_id=pid, elec_scenario="conservative")[1] is None


# ── 자본비용 채널 ──

@pytest.mark.parametrize("mult,expected_ncc", [(0.8, 2035), (1.0, 2039), (1.2, None)])
def test_cost_multiplier_moves_activation_monotonically(mult, expected_ncc):
    """비용이 비쌀수록 문턱 도달이 늦거나 사라진다 (논문 ±20% 민감도와 같은 방향)."""
    assert _activation(cost_multiplier=mult)[1] == expected_ncc


def test_cost_multiplier_equals_legacy_post_hoc_scaling():
    """엔진 레버가 '만든 뒤 techs를 곱하던' 옛 방식과 같은 비용을 낸다.

    `scripts/run_escalator_floor.py`가 이 등가성 위에서 리팩터링됐다 —
    깨지면 논문 §6 ±20% 표의 재현이 깨진다.
    """
    legacy = KETSModel(solve._RAW, "step")
    for tech in legacy.techs:
        tech["cost_krw"] *= 0.8
    lever = KETSModel({**solve._RAW,
                       "model_params": {**solve._RAW["model_params"], "cost_multiplier": 0.8}},
                      "step")
    legacy.techs.sort(key=lambda t: t["cost_krw"])
    assert [t["cost_krw"] for t in lever.techs] == [t["cost_krw"] for t in legacy.techs]


# ── 학습곡선 채널: cap과 분리됐는가 ──

def _tech_cost_2040(tech_scenario, tech_name, cap_sid="base"):
    data = solve._RAW if tech_scenario is None else {
        **solve._RAW,
        "model_params": {**solve._RAW["model_params"], "tech_scenario": tech_scenario}}
    m = KETSModel(data, "step")
    tech = next(t for t in m.techs if t["tech"] == tech_name)
    return m._tech_cost(tech, 2040, cap_sid)


def test_tech_scenario_overrides_cap_scenario_for_learning():
    """cap을 base로 두고 학습만 ideal로 흔들 수 있다 — 두 사건은 서로 독립이다."""
    base = _tech_cost_2040("base", "태양광 확대", cap_sid="base")
    ideal = _tech_cost_2040("ideal", "태양광 확대", cap_sid="base")
    assert ideal < base, f"학습 가속이 비용을 낮추지 않는다: {ideal} vs {base}"


def test_tech_scenario_defaults_to_cap_scenario():
    """미지정이면 기존 동작(cap 시나리오 추종)을 유지한다 — 하위호환."""
    assert _tech_cost_2040(None, "태양광 확대", cap_sid="ideal") == \
        _tech_cost_2040("ideal", "태양광 확대", cap_sid="ideal")


def test_tech_scenario_moves_non_energy_techs_only():
    """헤드라인 2기술은 에너지가격 채널을 타므로 학습곡선에 반응하지 않는다.

    설계상의 경계다. 이게 바뀌면 §6·§7의 비용 채널 서술을 다시 써야 한다.
    """
    assert _activation(tech_scenario="ideal") == _activation(tech_scenario="base")

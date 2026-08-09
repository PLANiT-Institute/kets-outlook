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


# ─── 전환기술 문턱 비용경로 (docs/report.md §1) ───

STEEL = "수소환원제철 (H₂-DRI-EAF)"
E_NCC = "NCC 전기분해로(e-cracker)"


def test_tech_threshold_costs():
    """§1이 인쇄하는 문턱 — 이 값들이 §4·§5의 '문턱 도달 연도'를 정의한다.

    2026-08-08 감사 전까지 이 수치는 산출물 어디에도 남지 않아(특히 e-cracker
    135,000원은 report.md가 유일한 출처였다) 골든 테스트가 잠글 수 없었다.
    """
    th = _load("msr_results_v1.0.json")["tech_thresholds"]
    steel = th[STEEL]["cost_krw_by_year"]
    ncc = th[E_NCC]["cost_krw_by_year"]
    assert (steel["2035"], steel["2037"], steel["2040"]) == (97_500, 94_500, 90_000)
    assert ncc["2035"] == 135_000


def test_corridor_floor_tracks_steel_threshold():
    """패키지 A의 회랑 하한은 철강 문턱을 추종한다 — 회랑의 '기술앵커' 성질.

    §7의 '보수 수소에서도 A는 철강 투자신호를 유지한다'가 이 성질에 걸려 있다.
    """
    res = _load("msr_results_v1.0.json")
    steel = res["tech_thresholds"][STEEL]["cost_krw_by_year"]
    a_path = {r["year"]: r["floor"] for r in res["packages"]["A"]["path"]}
    for yr in (2035, 2037, 2040):
        assert a_path[yr] == pytest.approx(steel[str(yr)], abs=1.0), yr


# ─── §4 운영규칙 4종 표 (docs/report.md §4) ───
#     2026     2030     2040   낙폭  흡수Mt  수입조   H₂-DRI  e-NCC
EXPECTED_PACKAGES = {
    "P0": (22_749, 46_159, 67_461,  0.0,   0.0, 67.1, None, None),
    "P1": (36_337, 47_680, 67_461, 16.8,  40.6, 67.4, None, None),
    "A":  (30_849, 55_972, 90_000,  7.7,   0.0, 98.3, 2035, 2039),
    "B":  (35_835, 54_817, 89_767, 16.7, 268.2, 96.9, 2035, 2039),
}


@pytest.mark.parametrize("pid,expected", EXPECTED_PACKAGES.items())
def test_package_table(pid, expected):
    """§4 표 전체 — 골든 테스트는 그동안 P0 가격 3개만 잠그고 있었다."""
    p26, p30, p40, drawdown, intake, revenue, steel, ncc = expected
    P = _load("msr_results_v1.0.json")["packages"][pid]
    px = {r["year"]: round(r["kau"]) for r in P["path"]}
    assert (px[2026], px[2030], px[2040]) == (p26, p30, p40)
    assert round(P["max_drawdown"] * 100, 1) == drawdown
    assert round(P["cum_intake_Mt"], 1) == intake
    assert round(P["cum_auction_rev_trillion"], 1) == revenue
    assert P["activation_headline"].get(STEEL) == steel
    assert P["activation_headline"].get(E_NCC) == ncc


def test_p1_does_not_move_2040_price():
    """§4의 논증 축: 수량규칙만으로는 장기 수준이 안 움직인다(워터베드).

    P1 2040 == P0 2040이 깨지면 §4 '읽는 법' 첫 항목과 게이트 워터폴 논증이 무너진다.
    """
    pk = _load("msr_results_v1.0.json")["packages"]
    p0_40 = next(r["kau"] for r in pk["P0"]["path"] if r["year"] == 2040)
    p1_40 = next(r["kau"] for r in pk["P1"]["path"] if r["year"] == 2040)
    assert p0_40 == p1_40


# ─── §5 에스컬레이터 표 나머지 열 (2040 하한은 위에서 이미 잠금) ───
#         철강  e-NCC  누적보류  연간최대  최소여유
EXPECTED_ESCALATOR = {
    "40k_7pct":   (2039, 2039, 360.1, 50.7, 0.415),
    "45k_7pct":   (2037, 2038, 500.1, 50.7, 0.415),
    "50k_7pct":   (2036, 2038, 584.0, 54.7, 0.369),
    "45k_5.5pct": (2040, 2039, 372.5, 44.6, 0.475),
    "50k_5.5pct": (2038, 2039, 511.7, 50.7, 0.415),
}


@pytest.mark.parametrize("case,expected", EXPECTED_ESCALATOR.items())
def test_escalator_table(case, expected):
    steel, ncc, cum, max_annual, headroom = expected
    c = _load("escalator_floor_cce_v2.0.json")[case]
    assert c["steel_threshold_year"] == steel
    assert c["ncc_threshold_year"] == ncc
    assert round(c["cum_required_withholding_Mt"], 1) == cum
    assert round(c["max_annual_required_withholding_Mt"], 1) == max_annual
    assert round(c["min_headroom"], 3) == headroom


# ─── §6 기술비용 ±20% 민감도 (docs/report.md §6) ───
#   (출발가격, 비용배수) → (누적필요보류 Mt, 방어성립)
EXPECTED_PM20 = {
    (40_000, 0.8): (549.6, True),  (40_000, 1.0): (360.1, True),  (40_000, 1.2): (130.7, True),
    (45_000, 0.8): (671.2, False), (45_000, 1.0): (500.1, True),  (45_000, 1.2): (276.3, True),
    (50_000, 0.8): (724.1, False), (50_000, 1.0): (584.0, True),  (50_000, 1.2): (365.0, True),
}


def test_cost_sensitivity_pm20():
    """§6 — 보고서의 정책권고를 '4만 원 출발' 하나로 좁히는 표.

    4.5만·5만이 비용 −20%에서 방어에 실패한다는 것이 권고의 근거 전부다.
    이 표가 조용히 바뀌면 보고서 결론이 바뀐다.
    """
    grid = _load("escalator_floor_cce_v2.0.json")["cost_sensitivity_pm20"]["grid"]
    got = {(int(g["f0"]), round(g["cost_scale"], 1)):
           (round(g["cum_required_withholding_Mt"], 1), g["defended_all"]) for g in grid}
    assert got == EXPECTED_PM20


def test_only_40k_survives_full_cost_range():
    """§6의 결론문 — 전 비용범위에서 방어되는 출발가격은 4만 원뿐."""
    grid = _load("escalator_floor_cce_v2.0.json")["cost_sensitivity_pm20"]["grid"]
    survivors = {int(f0) for f0 in {g["f0"] for g in grid}
                 if all(g["defended_all"] for g in grid if g["f0"] == f0)}
    assert survivors == {40_000}


# ─── §7 수소×전력 2×2 (docs/report.md §7) ───
#   셀 → {패키지: (H₂-DRI 도입연도, e-NCC 도입연도)}   None = 미도입
EXPECTED_2X2 = {
    "h2_gov|elec_gov_invest":          {"A": (2035, 2039), "B": (2035, 2039)},
    "h2_gov|elec_conservative":        {"A": (2035, None), "B": (2035, None)},
    "h2_conservative|elec_gov_invest": {"A": (2035, 2037), "B": (None, 2039)},
    "h2_conservative|elec_conservative": {"A": (2035, None), "B": (None, None)},
}


@pytest.mark.parametrize("cell,expected", EXPECTED_2X2.items())
def test_h2_elec_2x2(cell, expected):
    got = _load("msr_results_v1.0.json")["sensitivity_h2_elec"][cell]
    for pid, (steel, ncc) in expected.items():
        assert (got[pid]["h2_dri"], got[pid]["e_ncc"]) == (steel, ncc), pid


def test_conservative_h2_splits_a_from_b():
    """§7의 핵심 분기이자 보고서가 A를 고르는 이유.

    보수 수소에서 B는 H₂-DRI를 못 살리고 A는 살린다. 이게 깨지면 §7 결론
    ('A가 더 강건하다')의 근거가 사라진다.
    """
    sens = _load("msr_results_v1.0.json")["sensitivity_h2_elec"]
    for elec in ("gov_invest", "conservative"):
        cell = sens[f"h2_conservative|elec_{elec}"]
        assert cell["A"]["h2_dri"] == 2035, elec
        assert cell["B"]["h2_dri"] is None, elec


# ─── 선도차수별 거래 실태 (2026-08-09 사이클12 발견) ───

def test_forward_vintages_are_untraded():
    """기간간 차익거래 채널의 존재 여부를 거래량으로 직접 잠근다.

    가격 프리미엄 통계는 정지호가·편의수익률·거래비용 해석에 열려 있지만
    거래량은 그렇지 않다. 선도 빈티지(h>=1)가 실제로 거래되기 시작하면 이 테스트가
    깨지고, 그때는 전달실패 해석 자체를 재검토해야 한다 — 그것이 이 잠금의 목적이다.
    """
    fh = _load("carry_analysis_cce_v2.0.json")["forward_horizon"]
    totals = fh["forward_totals"]
    assert totals["quote_days"] == 4_016
    assert totals["traded_days"] == 3
    assert totals["volume_tco2"] == 33_139
    assert totals["share_of_all_kau_volume"] < 0.0002, "선도 거래가 유의해지면 §3 논증 재검토"
    # h>=2는 단 한 건도 없다
    by_h = fh["by_horizon"]
    for h in ("2", "3", "4"):
        assert by_h[h]["traded_days"] == 0, h


def test_forward_trades_are_three_isolated_2019_blocks():
    """h=1의 유일한 거래 3건 — 2019년 4분기 KAU20에 몰려 있다."""
    days = _load("carry_analysis_cce_v2.0.json")["forward_horizon"]["forward_traded_days"]
    assert len(days) == 3
    assert {d["date"] for d in days} == {"2019-09-24", "2019-11-11", "2019-11-22"}
    assert {d["vintage"] for d in days} == {2020}
    assert sum(d["volume_tco2"] for d in days) == 33_139


def test_forward_closes_are_reference_prints():
    """선도 빈티지 종가는 시장가가 아니라 복제된 참조가다."""
    fh = _load("carry_analysis_cce_v2.0.json")["forward_horizon"]
    n_days = fh["forward_quote_days_with_multiple_vintages"]
    identical = fh["forward_days_with_identical_close_across_vintages"]
    assert (n_days, identical) == (1_143, 1_130)
    assert identical / n_days > 0.98


def test_half_of_full_pair_sample_is_degenerate():
    """전체 5,693쌍 중 절반이 프리미엄 정확히 0 — both_traded 필터가 필요한 이유."""
    dp = _load("carry_analysis_cce_v2.0.json")["degenerate_pairs"]
    assert dp["n_pairs_total"] == 5_693
    assert dp["n_exactly_zero_premium"] == 2_841
    assert dp["share_exactly_zero_premium"] == pytest.approx(0.499, abs=5e-4)
    assert dp["n_both_traded"] == 253


# ─── 기간간 채널: 등록부 대 시장 (2026-08-09 사이클15 발견) ───

def test_registry_channel_dwarfs_market_channel():
    """기업은 빈티지 간에 배출권을 옮긴다 — 시장이 아니라 등록부에서.

    "선도 빈티지 미거래는 제도적 금지 탓"이라는 반론에 대한 실증적 답.
    411개 기업이 미래 빈티지 배출권에 접근했다(차입). 접근이 금지였다면 0이어야 한다.
    """
    ch = _load("carry_analysis_cce_v2.0.json")["intertemporal_channel"]
    assert (ch["borrowing_firm_year_obs"], ch["borrowing_distinct_firms"]) == (800, 411)
    assert (ch["banking_firm_year_obs"], ch["banking_distinct_firms"]) == (4_572, 823)
    assert ch["borrowing_total_tco2"] == 40_965_299
    assert ch["borrowing_to_forward_market_volume_ratio"] > 1_000


def test_bank_to_borrow_asymmetry_explodes():
    """이월/차입 비율의 단조 폭발 — 양방향 균등화에서 단방향 비축으로.

    작동하는 기간간 시장에서 이월과 차입은 같은 차익거래의 양면이다.
    차입이 되살아나면(비율 하락) 채널이 재가동된다는 신호이므로 이 테스트가 깨진다.
    """
    by_year = _load("carry_analysis_cce_v2.0.json")["intertemporal_channel"]["by_year"]
    ratios = {y: v["bank_to_borrow_ratio"] for y, v in by_year.items()
              if v["bank_to_borrow_ratio"] is not None}
    assert ratios["2015"] == pytest.approx(1.8, abs=0.05)
    assert ratios["2024"] == pytest.approx(462.2, abs=0.5)
    # 3차 계획기간 이후 단조 증가
    recent = [ratios[y] for y in ("2021", "2022", "2023", "2024")]
    assert recent == sorted(recent), recent
    assert by_year["2024"]["banked_tco2"] == 92_140_327, "§3 이월잔고 앵커"


# ─── 쌍 표본 3분할 (2026-08-09 사이클18 발견) ───

def test_all_quote_row_is_a_reference_price_artifact():
    """Table 1 all-quote 행이 시장 관측이 아님을 잠근다.

    양쪽 무거래 쌍은 참조가 둘을 비교한다 — 값이 같으면 정확히 0, 다르게 표류하면
    중앙값 −14.5%(p10 −56.2%) 같은 시장가로 성립 불가능한 값이 나온다.
    두 갈래 모두 정보가 없다. 이 구조가 바뀌면 all-quote 통계의 해석도 바뀐다.
    """
    comp = _load("carry_analysis_cce_v2.0.json")["pair_composition_by_trading_status"]
    both, one, none = comp["both_traded"], comp["one_traded"], comp["neither_traded"]
    assert (both["n_pairs"], one["n_pairs"], none["n_pairs"]) == (253, 1_828, 3_612)
    assert both["n_pairs"] + one["n_pairs"] + none["n_pairs"] == 5_693
    # 양쪽 무거래: 4분의 3이 정확히 0, 나머지는 시장가로 불가능한 폭으로 표류
    assert none["share_exactly_zero"] == pytest.approx(0.752, abs=5e-4)
    assert none["nonzero_median_pct"] == pytest.approx(-14.489, abs=1e-3)
    assert none["nonzero_p10_pct"] < -50, "참조가 표류 폭"
    # 양쪽 거래 표본은 질적으로 다르다 — 비영 중앙값이 0 근처 양수
    assert 0 < both["nonzero_median_pct"] < 1


def test_borrowing_cap_never_binds():
    """차입 한도(시행령 제36조제2항, 제출의무의 10%)는 한 해도 구속하지 않았다.

    "이월/차입 비대칭은 제도 탓"이라는 반론을 정량적으로 기각한다. 2024년 기업들은
    법이 허용한 차입 여력의 0.36%만 썼다. 한도가 구속력을 갖기 시작하면
    (소진율 상승) 이 테스트가 깨지고 반론을 재검토해야 한다.
    """
    cap = _load("carry_analysis_cce_v2.0.json")["intertemporal_channel"]["borrowing_cap"]
    assert cap["share_of_surrender_obligation"] == 0.10
    util = {y: v["utilisation"] for y, v in cap["by_year"].items()}
    assert max(util.values()) < 0.27, "최대 소진율(2016)"
    assert util["2024"] == pytest.approx(0.0036, abs=5e-5)
    # 3차 계획기간 내내 1.5% 미만
    for year in ("2021", "2022", "2023", "2024"):
        assert util[year] < 0.015, year


def test_compliance_proximity_effect_is_not_identified():
    """음성 결과를 잠근다 — 재현 가능해야 §7 한계로 인용할 수 있다.

    풀링 통계는 마감 근접 시 프리미엄이 높아 보이지만, 연도 고정효과를 넣으면
    사라진다. 표본이 커져 이 계수가 유의해지면 테스트가 깨지고, 그때는 마감효과를
    한계가 아니라 결과로 다뤄야 한다.
    """
    test = _load("carry_analysis_cce_v2.0.json")["compliance_distance_test"]
    reg = test["year_fe_proximity_regression"]
    assert reg["n_pairs"] == 253 and reg["n_date_clusters"] == 252
    assert reg["coefficient_pp"] == pytest.approx(2.543, abs=1e-3)
    assert reg["cluster_robust_se_pp"] == pytest.approx(2.155, abs=1e-3)
    assert abs(reg["t_stat"]) < 1.96, "유의해지면 §7이 아니라 §5로 옮겨야 한다"
    assert reg["ci95_pp"][0] < 0 < reg["ci95_pp"][1]
    assert reg["identifying_years"] == [2019, 2020, 2021, 2022, 2023, 2024]
    # 풀링 단계에서는 효과가 있어 보인다 — 그래서 검정이 필요했다
    horizons = test["by_months_to_deadline"]
    assert horizons["0"]["mean_pct"] > 5.5 and horizons["4"]["mean_pct"] < 5.5


# ─── 경매 실적 (2026-08-09 사이클26 발견, 사이클27 영속화) ───

def test_auction_undersubscription_is_demand_not_reserve():
    """유찰 29.05%의 98.3%가 응찰 부족이다 — 유보가격 구속이 아니다.

    논문이 "required withholding ≠ 유찰 예측"이라고 선을 긋는 근거가 여기 있다.
    모형이 계산하는 유보가격형 유찰과 한국의 관측 유찰은 다른 현상이다.
    이 비중이 뒤집히면(유보가격형 증가) §5.5·§7 서술을 재검토해야 한다.
    """
    a = _load("carry_analysis_cce_v2.0.json")["auction_outcomes"]
    assert (a["n_auctions"], a["first_date"], a["last_date"]) == (83, "2019-01-23", "2026-07-08")
    assert (a["n_fully_sold"], a["n_undersold"], a["n_zero_sold"]) == (36, 47, 2)
    assert a["offered_tco2"] == 130_562_800 and a["sold_tco2"] == 92_634_600
    assert a["unsold_share"] == pytest.approx(0.2905, abs=5e-5)
    d = a["undersold_decomposition"]
    short = d["insufficient_bids"]["unsold_tco2"]
    reserve_like = d["bids_sufficient_but_unsold"]["unsold_tco2"]
    assert (d["insufficient_bids"]["n_auctions"],
            d["bids_sufficient_but_unsold"]["n_auctions"]) == (42, 5)
    assert short / (short + reserve_like) > 0.98, "수요부족이 압도적이어야 한다"


def test_auction_demand_is_thin_at_market_prices():
    """응찰배율 중앙값 0.98 — 현행 시장가에서도 경매 수요가 빠듯하다.

    §6의 "4만 원 출발만 전 범위에서 살아남는다"와 같은 방향의 독립 증거.
    """
    btc = _load("carry_analysis_cce_v2.0.json")["auction_outcomes"]["bid_to_cover"]
    assert btc["n"] == 83
    assert btc["median"] == pytest.approx(0.9816, abs=5e-4)
    assert btc["median"] < 1.0, "전형적 경매가 미달"


def test_oversubscribed_auction_can_still_sell_nothing():
    """2024-05-08: 1.2배 초과청약인데 낙찰자 0명·낙찰량 0.

    응찰이 있어도 낙찰이 0일 수 있다는 관측 사례. 취소 규칙 설계의 근거.
    """
    cases = (_load("carry_analysis_cce_v2.0.json")["auction_outcomes"]
             ["undersold_decomposition"]["bids_sufficient_but_unsold"]["cases"])
    zero = [c for c in cases if c["sold_tco2"] == 0]
    assert len(zero) == 1
    c = zero[0]
    assert (c["date"], c["instrument"]) == ("2024-05-08", "KAU23")
    assert c["bid_tco2"] > c["offered_tco2"] and c["winners"] == 0

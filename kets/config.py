"""설정 로딩 유틸리티.

Single Source of Truth: data/K-ETS_마스터데이터.xlsx
모든 파라미터, 시나리오, 업종 정보는 이 엑셀에서 로드한다.
엑셀 하나가 유일한 파라미터 소스다 — 코드에 숫자를 넣지 않는다.
"""

from pathlib import Path
from functools import lru_cache
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MASTER_EXCEL = PROJECT_ROOT / "data" / "K-ETS_마스터데이터.xlsx"


# ─── 엑셀 시트 로딩 (캐싱) ───

@lru_cache(maxsize=1)
def _load_master_excel() -> dict[str, pd.DataFrame]:
    """마스터 엑셀의 모든 시트를 한 번에 로드한다."""
    return pd.read_excel(MASTER_EXCEL, sheet_name=None, engine="openpyxl")


def reload_master():
    """캐시를 무효화하고 엑셀을 다시 로드한다."""
    _load_master_excel.cache_clear()


def get_sheet(name: str) -> pd.DataFrame:
    """마스터 엑셀에서 특정 시트를 반환한다."""
    sheets = _load_master_excel()
    if name not in sheets:
        raise KeyError(f"Sheet '{name}' not found. Available: {list(sheets.keys())}")
    return sheets[name].copy()


# ─── 시나리오 ───

def load_scenarios_df() -> pd.DataFrame:
    return get_sheet("시나리오정의")


def get_scenario_ids() -> list[str]:
    return load_scenarios_df()["scenario_id"].tolist()


# ─── 업종 ───

def load_sectors_df() -> pd.DataFrame:
    return get_sheet("업종분류")


def get_modeled_sectors() -> pd.DataFrame:
    """MACC 모형 대상 업종만 반환."""
    df = load_sectors_df()
    return df[df["is_modeled"] == True]


# ─── 모형 파라미터 ───

def load_model_params_df() -> pd.DataFrame:
    return get_sheet("모형파라미터")


def get_param(category: str, parameter: str):
    """특정 파라미터 값을 가져온다."""
    df = load_model_params_df()
    row = df[(df["category"] == category) & (df["parameter"] == parameter)]
    if row.empty:
        raise KeyError(f"Parameter not found: {category}/{parameter}")
    return row["value"].iloc[0]


def load_model_params() -> dict:
    """기존 YAML 호환 dict 형태로 파라미터를 반환한다."""
    df = load_model_params_df()

    def _get(cat, param):
        row = df[(df["category"] == cat) & (df["parameter"] == param)]
        return row["value"].iloc[0] if not row.empty else None

    return {
        "analysis": {
            "start_year": int(_get("분석기간", "start_year")),
            "end_year": int(_get("분석기간", "end_year")),
            "calibration_period": {
                "start": int(_get("분석기간", "calibration_start")),
                "end": int(_get("분석기간", "calibration_end")),
            },
        },
        "hotelling": {
            "discount_rate": float(_get("Hotelling", "discount_rate")),
            "risk_premium": float(_get("Hotelling", "risk_premium")),
        },
        "msr": {
            "enabled": bool(_get("MSR", "msr_enabled")),
        },
        "exchange_rate": {
            "eur_krw": float(_get("환율", "eur_krw")),
            "usd_krw": float(_get("환율", "usd_krw")),
        },
        "macc": {
            "default_functional_form": str(_get("MACC_철강", "functional_form")),
            "steel": {
                "alpha": float(_get("MACC_철강", "alpha")),
                "beta": float(_get("MACC_철강", "beta")),
                "max_abatement_share": float(_get("MACC_철강", "max_abatement_share")),
                "baseline_emissions_MtCO2": float(_get("MACC_철강", "baseline_emissions_MtCO2")),
            },
            "petrochem": {
                "alpha": float(_get("MACC_석유화학", "alpha")),
                "beta": float(_get("MACC_석유화학", "beta")),
                "max_abatement_share": float(_get("MACC_석유화학", "max_abatement_share")),
                "baseline_emissions_MtCO2": float(_get("MACC_석유화학", "baseline_emissions_MtCO2")),
            },
        },
        "solver": {
            "method": str(_get("Solver", "method")),
            "price_lower_bound_krw": float(_get("Solver", "price_lower_bound")),
            "price_upper_bound_krw": float(_get("Solver", "price_upper_bound")),
            "tolerance": float(_get("Solver", "tolerance")),
            "intl_steepness": float(_get("Solver", "intl_steepness") or 0.0005),
            "step_smoothing_width": float(_get("Solver", "step_smoothing_width") or 0.0),
        },
        "market": {
            "total_kets_emissions_MtCO2": float(_get("K-ETS_시장", "total_kets_emissions_MtCO2")),
            "intl_credit_limit_ratio": float(_get("K-ETS_시장", "intl_credit_limit_ratio")),
        },
        "cbam": {
            "steel_export_Mt": float(_get("CBAM", "cbam_steel_export_Mt")),
            "steel_embed_tCO2": float(_get("CBAM", "cbam_steel_embed_tCO2")),
            "petrochem_export_Mt": float(_get("CBAM", "cbam_petrochem_export_Mt")),
            "petrochem_embed_tCO2": float(_get("CBAM", "cbam_petrochem_embed_tCO2")),
        },
    }


# ─── 무상할당 비율 ───

def load_free_allocation_df() -> pd.DataFrame:
    return get_sheet("무상할당비율")


# ─── EUA 가격 전망 ───

def load_eua_forecast_df() -> pd.DataFrame:
    return get_sheet("EUA가격전망")


# ─── BAU 배출 전망 ───

def load_bau_emissions_df() -> pd.DataFrame:
    return get_sheet("BAU배출전망")


# ─── Cap Path ───

def load_cap_path_df() -> pd.DataFrame:
    return get_sheet("배출허용총량")


# ─── 데이터 수집 현황 ───

def load_data_status_df() -> pd.DataFrame:
    return get_sheet("데이터수집현황")


# ─── 신규 시트 (v2) ───

def load_kau_historical_df() -> pd.DataFrame:
    return get_sheet("KAU과거가격")


def load_kets_market_df() -> pd.DataFrame:
    return get_sheet("K-ETS시장총괄")


def load_cbam_phaseout_df() -> pd.DataFrame:
    return get_sheet("CBAM무상폐지일정")


def load_cbam_emissions_df() -> pd.DataFrame:
    return get_sheet("CBAM내재배출")


def load_trade_df() -> pd.DataFrame:
    return get_sheet("한국-EU무역")


def load_ndc_df() -> pd.DataFrame:
    return get_sheet("NDC부문별목표")


def load_macc_tech_df() -> pd.DataFrame:
    return get_sheet("MACC기술상세")

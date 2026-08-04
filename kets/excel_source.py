"""마스터 엑셀 → 엔진 데이터 dict (로컬 전용, pandas/openpyxl 의존).

`KETSModel.from_excel()`과 `scripts/export_web_data.py`가 공유하는 단일 로더.
반환 dict는 `public/model/kets_data.json`과 동일 구조 → 로컬 엑셀 경로와
프로덕션 JSON 경로가 같은 데이터 계약을 쓴다(SSOT 일관).

이 모듈은 엔진 계산부와 분리되어 있어, Vercel 서버리스에는 배포되지 않는다
(엔진은 numpy+stdlib만 의존; 엑셀 로딩은 빌드타임에만).
"""

from __future__ import annotations
import json

from kets.config import get_sheet, get_param, load_model_params

SHEETS = ["모형파라미터", "학습곡선", "MACC기술상세", "BAU배출전망",
          "배출허용총량", "EUA가격전망", "무상할당비율", "MSR설계", "유동성모수",
          "유상할당레버", "MSR가격하한", "KAU과거가격", "CBAM무상폐지일정",
          "CBAM내재배출", "한국-EU무역", "K-ETS시장총괄", "KAU2026시세", "정책패키지", "수소가격시나리오", "전력가격시나리오"]


def _records(name: str) -> list[dict]:
    df = get_sheet(name)
    return json.loads(df.to_json(orient="records", force_ascii=False))


def _liquidity_defaults(sheets: dict) -> dict:
    """유동성모수 시트 → {parameter: value} 편의 dict."""
    return {r["parameter"]: r["value"] for r in sheets.get("유동성모수", [])}


def load_data_from_excel() -> dict:
    """엔진이 소비하는 데이터 계약(dict)을 마스터 엑셀에서 조립한다."""
    sheets = {name: _records(name) for name in SHEETS}
    return {
        "_meta": {"source": "data/K-ETS_마스터데이터.xlsx"},
        "model_params": load_model_params(),
        "banking_initial_bank_Mt": float(get_param("Banking", "initial_bank_Mt")),
        "msr_reserve_Mt": float(get_param("MSR", "msr_reserve_Mt")),
        "liquidity_defaults": _liquidity_defaults(sheets),
        "sheets": sheets,
    }

"""데이터 무결성 — 마스터 엑셀이 소리 없이 바뀌는 것을 막는다.

`data/MANIFEST.json`이 데이터 계약의 지문이다. 엑셀을 고치면
`python3 scripts/build_manifest.py`로 지문을 갱신해야 한다. 그 마찰이 목적 —
"언제 누가 무슨 숫자를 바꿨나"를 커밋 디프로 남긴다.

검증 항목:
  1. 시트 목록·행수·열 구성이 매니페스트와 일치
  2. 셀 내용 다이제스트 일치 (파일 재저장에는 흔들리지 않고 값 변경만 잡는다)
  3. 출처(provenance) 커버리지 — 모든 행이 그룹 내 출처로 덮인다
  4. 결론을 지탱하는 스칼라 2종이 실측 기반 값이며 출처가 붙어 있다
  5. export된 kets_data.json이 현재 엑셀과 같은 세대 (행수 대조)
"""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_manifest import build, sheet_digest  # noqa: E402

MANIFEST_PATH = PROJECT_ROOT / "data" / "MANIFEST.json"
MASTER = PROJECT_ROOT / "data" / "K-ETS_마스터데이터.xlsx"
WEB_JSON = PROJECT_ROOT / "public" / "model" / "kets_data.json"

REBUILD = "엑셀을 고쳤다면 `python3 scripts/build_manifest.py`로 매니페스트를 갱신하라."


@pytest.fixture(scope="module")
def manifest() -> dict:
    assert MANIFEST_PATH.is_file(), f"MANIFEST.json 없음 — {REBUILD}"
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sheets() -> dict[str, pd.DataFrame]:
    assert MASTER.is_file(), f"마스터 엑셀 없음: {MASTER}"
    return pd.read_excel(MASTER, sheet_name=None, engine="openpyxl")


# ── 1·2. 계약 지문 ──

def test_sheet_inventory_matches_manifest(manifest, sheets):
    assert set(sheets) == set(manifest["sheets"]), (
        f"시트 목록 변동 — 추가 {sorted(set(sheets) - set(manifest['sheets']))} / "
        f"삭제 {sorted(set(manifest['sheets']) - set(sheets))}. {REBUILD}")


def test_rows_and_columns_match_manifest(manifest, sheets):
    drift = []
    for name, df in sheets.items():
        rec = manifest["sheets"].get(name)
        if rec is None:
            continue
        if len(df) != rec["rows"]:
            drift.append(f"{name}: 행 {rec['rows']} → {len(df)}")
        if [str(c) for c in df.columns] != rec["columns"]:
            drift.append(f"{name}: 열 구성 변동")
    assert not drift, "\n".join(drift) + f"\n{REBUILD}"


def test_cell_digests_match_manifest(manifest, sheets):
    """값이 바뀐 시트를 지목한다. 파일 재저장(타임스탬프)에는 반응하지 않는다."""
    changed = [name for name, df in sheets.items()
               if name in manifest["sheets"]
               and sheet_digest(df) != manifest["sheets"][name]["digest"]]
    assert not changed, f"셀 값이 바뀐 시트: {changed}. {REBUILD}"


def test_manifest_is_reproducible(manifest):
    """매니페스트가 현재 엑셀에서 실제로 재생성되는지 (손으로 고쳤을 가능성 차단)."""
    assert build() == {k: v for k, v in manifest.items() if k != "raw_observations"}, \
        f"매니페스트가 엑셀과 어긋난다. {REBUILD}"


def test_raw_observation_file_is_fingerprinted(manifest):
    """원자료 파일이 바뀌면(재다운로드·재가공) 지문이 어긋나 드러난다."""
    raw = manifest.get("raw_observations") or {}
    assert raw.get("sha256"), f"원자료 지문 없음 — {REBUILD}"
    path = PROJECT_ROOT / raw["file"]
    assert path.is_file(), f"원자료 파일 없음: {raw['file']}"
    import hashlib
    assert hashlib.sha256(path.read_bytes()).hexdigest() == raw["sha256"], \
        f"{raw['file']}이 바뀌었다 — {REBUILD}"


# ── 3. 출처 커버리지 ──

def test_every_row_has_provenance(manifest, sheets):
    """모든 행이 출처로 덮인다.

    출처는 그룹(시나리오·카테고리)의 첫 행에 한 번만 적는 관행을 쓴다.
    따라서 그룹 내 forward-fill 후에도 비어 있는 행이 진짜 고아다.
    """
    exempt = set(manifest["provenance_exempt"])
    orphans = []
    for name, df in sheets.items():
        if name in exempt or df.empty:
            continue
        rec = manifest["sheets"][name]
        col = rec["provenance_col"]
        if col is None:
            orphans.append(f"{name}: 출처열 없음 (source/paper_ref/note 중 하나 필요)")
            continue
        src = df[col].replace(r"^\s*$", None, regex=True)
        gcol = rec["group_col"]
        filled = src.groupby(df[gcol].astype(str)).ffill() if gcol else src.ffill()
        missing = df.index[filled.isna()].tolist()
        if missing:
            orphans.append(f"{name}: 출처 없는 행 {missing[:10]}"
                           f"{' …' if len(missing) > 10 else ''} (총 {len(missing)})")
    assert not orphans, "출처 미기재:\n" + "\n".join(orphans)


# ── 4. 결론을 지탱하는 스칼라 ──

@pytest.mark.parametrize("category,parameter,expected,anchor", [
    ("Banking", "initial_bank_Mt", 92.140327, "등록부"),
    ("Liquidity", "lambda_2026_implied", 0.575, "역산"),
])
def test_load_bearing_scalars(sheets, category, parameter, expected, anchor):
    """B0와 λ는 결과 전체를 움직인다 — 값과 출처를 함께 잠근다.

    B0=70Mt(가정) / λ=0.55(선언)로 되돌아가면 여기서 걸린다.
    """
    sheet = "모형파라미터" if category == "Banking" else "유동성모수"
    df = sheets[sheet]
    row = df[(df["category"] == category) & (df["parameter"] == parameter)]
    assert len(row) == 1, f"{sheet}/{category}/{parameter} 행이 {len(row)}개"
    assert float(row["value"].iloc[0]) == pytest.approx(expected, rel=1e-9)
    src = str(row["source"].iloc[0])
    assert anchor in src, f"{parameter} 출처가 실측 기반이 아니다: {src!r}"


# ── 5. export 신선도 ──

def test_exported_json_matches_current_excel(manifest):
    """kets_data.json이 현재 엑셀 세대인지 — 엑셀만 고치고 export를 잊는 사고 방지."""
    assert WEB_JSON.is_file(), "kets_data.json 없음 — scripts/export_web_data.py 실행 필요"
    exported = json.loads(WEB_JSON.read_text(encoding="utf-8"))["sheets"]
    stale = [name for name, rows in exported.items()
             if name in manifest["sheets"] and len(rows) != manifest["sheets"][name]["rows"]]
    assert not stale, (f"export가 뒤처진 시트: {stale} — "
                       "`python3 scripts/export_web_data.py` 재실행 필요")

"""마스터 엑셀 → data/MANIFEST.json (데이터 계약 지문).

기록하는 것: 시트 목록·행수·출처열·내용 다이제스트.
파일 바이트가 아니라 **셀 값**의 다이제스트를 쓴다 — Excel이 내용 변경 없이
다시 저장해도(zip 타임스탬프 변동) 지문이 흔들리지 않게 하기 위해서다.

엑셀을 고쳤으면 이 스크립트를 다시 돌려야 tests/test_data_integrity.py가 통과한다.
그 마찰이 목적이다 — 데이터가 소리 없이 바뀌는 걸 막는다.

    python3 scripts/build_manifest.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data" / "K-ETS_마스터데이터.xlsx"
RAW = ROOT / "data" / "ets_data.xlsx"       # 시장·등록부 관측 원자료 (가공 없음)
MANIFEST = ROOT / "data" / "MANIFEST.json"

# 출처를 담는 열 후보 (앞에서부터 먼저 발견되는 것을 채택)
PROVENANCE_COLS = ("source", "paper_ref", "note")

# 수치 주장이 없는 시트 (라벨·서술만) — 출처열 면제
PROVENANCE_EXEMPT = ("시나리오정의",)

# 출처가 한 번만 적히고 이후 행은 비워두는 그룹 키 (앞에서부터 먼저 발견되는 것)
GROUP_COLS = ("scenario_id", "category", "channel", "sector")


def provenance_col(df: pd.DataFrame) -> str | None:
    return next((c for c in PROVENANCE_COLS if c in df.columns), None)


def group_col(df: pd.DataFrame) -> str | None:
    return next((c for c in GROUP_COLS if c in df.columns), None)


def sheet_digest(df: pd.DataFrame) -> str:
    """셀 값만의 SHA-256. 열 순서·행 순서 포함, 파일 메타데이터는 제외."""
    payload = json.dumps(
        {"columns": [str(c) for c in df.columns],
         "rows": df.astype(object).where(pd.notna(df), None).values.tolist()},
        ensure_ascii=False, sort_keys=False, default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build(path: Path = MASTER) -> dict:
    sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    return {
        "generated_from": str(path.relative_to(ROOT)),
        "note": "엑셀 수정 후 `python3 scripts/build_manifest.py` 재실행 필수.",
        "provenance_exempt": list(PROVENANCE_EXEMPT),
        "sheets": {
            name: {
                "rows": int(len(df)),
                "columns": [str(c) for c in df.columns],
                "provenance_col": provenance_col(df),
                "group_col": group_col(df),
                "digest": sheet_digest(df),
            }
            for name, df in sheets.items()
        },
    }


def build_raw(path: Path = RAW) -> dict:
    """원자료(`ets_data.xlsx`)는 관측치 — 출처열을 요구하지 않고 지문만 남긴다.

    복제 패키지가 "우리가 읽은 파일이 이것"임을 증명할 수 있어야 한다
    (`data/README.md`가 지적한 provenance 공백의 최소 보완).
    """
    if not path.is_file():
        return {}
    sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    return {
        "file": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "sheets": {name: {"rows": int(len(df)), "columns": [str(c) for c in df.columns]}
                   for name, df in sheets.items()},
    }


def main() -> int:
    if not MASTER.is_file():
        print(f"마스터 엑셀 없음: {MASTER}", file=sys.stderr)
        return 1
    manifest = build()
    manifest["raw_observations"] = build_raw()
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"{MANIFEST.relative_to(ROOT)} — 마스터 {len(manifest['sheets'])} 시트 · "
          f"원자료 {len(manifest.get('raw_observations', {}).get('sheets', {}))} 시트")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

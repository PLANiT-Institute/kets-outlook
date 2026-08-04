"""마스터 엑셀 → public/model/kets_data.json 이식 데이터 export (빌드타임).

Vercel 프로덕션 엔진(stdlib만)이 읽을 JSON을 생성한다. SSOT는 여전히 엑셀 하나이며,
엑셀을 수정하면 이 스크립트를 재실행해 JSON을 갱신한다 — 숫자를 코드에 넣지 않는다.

데이터 계약은 `kets/excel_source.load_data_from_excel()` 하나로 통일
(= KETSModel.from_excel()과 동일 소스).

추가로 outputs/runs/msr_results_v1.0.json(러너 v1.0 결과, 논문 v4 SSOT)에서
Overview용 정적 슬림 추출본 public/model/results_v1.json을 함께 생성한다
(packages P0/P1/A/B 경로·헤드라인 지표 + sensitivity_h2_elec + gate_waterfall).

실행:  python scripts/export_web_data.py
"""

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from kets.excel_source import load_data_from_excel, SHEETS

OUT = _ROOT / "public" / "model" / "kets_data.json"
RESULTS_SRC = _ROOT / "outputs" / "runs" / "msr_results_v1.0.json"
RESULTS_OUT = _ROOT / "public" / "model" / "results_v1.json"
FLOOR_SRC = _ROOT / "outputs" / "runs" / "escalator_floor_cce_v2.0.json"

# Overview에 필요한 경로 필드만 추출 (풀 결과는 outputs/runs에 유지)
PATH_FIELDS = ("year", "kau", "floor", "defended", "headroom", "bank_Mt", "auction_share",
               "static", "hotelling", "lambda")   # static·hotelling·λ: 메커니즘 탭의 전달 분해용
PKG_HEADLINE_FIELDS = ("activation_headline", "defended_all", "min_headroom",
                       "max_drawdown", "cum_intake_Mt", "cum_auction_rev_trillion")


def _slim_floor() -> dict:
    """escalator_floor_cce_v2.0.json → 보고서 탭이 쓰는 격자·민감도만 추출.

    없으면 None을 돌려 프런트가 해당 섹션을 숨긴다(빌드 실패시키지 않는다).
    """
    if not FLOOR_SRC.exists():
        print(f"경고: {FLOOR_SRC.name} 없음 — 보고서 탭의 최저가격 격자를 생략한다.")
        return None
    with open(FLOOR_SRC, encoding="utf-8") as f:
        esc = json.load(f)
    cases = {k: v for k, v in esc.items() if k not in ("meta", "cost_sensitivity_pm20")}
    return {
        "meta": esc["meta"],
        "cases": {k: {"floor_2040": v["floor"]["2040"],
                      "steel_threshold_year": v["steel_threshold_year"],
                      "ncc_threshold_year": v["ncc_threshold_year"],
                      "cum_required_withholding_Mt": v["cum_required_withholding_Mt"],
                      "max_annual_required_withholding_Mt": v["max_annual_required_withholding_Mt"],
                      "min_headroom": v["min_headroom"],
                      "defended_all": v["defended_all"]} for k, v in cases.items()},
        "cost_sensitivity_pm20": esc["cost_sensitivity_pm20"]["grid"],
    }


def export_results_v1():
    """msr_results_v1.0.json → results_v1.json 슬림 추출 (논문 v4 Overview 데이터)."""
    if not RESULTS_SRC.exists():
        sys.exit(
            f"오류: 러너 결과 파일이 없습니다 — {RESULTS_SRC}\n"
            "  먼저 `python3 scripts/run_model.py`로 msr_results_v1.0.json을 생성하세요.\n"
            "  (kets_data.json은 이미 저장됨; results_v1.json만 생성 실패)"
        )
    with open(RESULTS_SRC, encoding="utf-8") as f:
        full = json.load(f)

    slim = {
        "_meta": {
            "source": "outputs/runs/msr_results_v1.0.json",
            "model_version": full.get("model_version"),
            "note": "빌드타임 슬림 추출. 편집 금지 — scripts/export_web_data.py로 재생성.",
        },
        "packages": {},
        "sensitivity_h2_elec": full["sensitivity_h2_elec"],
        "gate_waterfall": full["gate_waterfall"],
        "escalator_floor": _slim_floor(),
    }
    for pid, rec in full["packages"].items():
        slim["packages"][pid] = {
            "meta": rec["meta"],
            "path": [{k: r[k] for k in PATH_FIELDS} for r in rec["path"]],
            **{k: rec[k] for k in PKG_HEADLINE_FIELDS},
        }
    with open(RESULTS_OUT, "w", encoding="utf-8") as f:
        json.dump(slim, f, ensure_ascii=False, indent=1)
    print(f"저장: {RESULTS_OUT}  ({RESULTS_OUT.stat().st_size / 1024:.0f} KB)")
    fl = slim.get("escalator_floor")
    print(f"  packages: {list(slim['packages'])} · sensitivity {len(slim['sensitivity_h2_elec'])} cells"
          f" · waterfall {len(slim['gate_waterfall'])} steps"
          f" · floor {len(fl['cases']) if fl else 0} cases / {len(fl['cost_sensitivity_pm20']) if fl else 0} ±20% 셀")


def main():
    data = load_data_from_excel()
    data["_meta"]["note"] = "빌드타임 export. 편집은 엑셀(SSOT)에서만. scripts/export_web_data.py로 재생성."
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"저장: {OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")
    for name in SHEETS:
        print(f"  {name}: {len(data['sheets'][name])} rows")

    export_results_v1()


if __name__ == "__main__":
    main()

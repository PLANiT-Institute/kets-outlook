#!/usr/bin/env bash
# 전체 재현: 마스터 엑셀 → 데이터 계약 → 모형 → 실증 → 그림 → 검증
# 사용: bash scripts/reproduce_all.sh   (리포 루트에서)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "[1/7] 데이터 계약 export (엑셀 → public/model/*.json)"
python3 scripts/export_web_data.py

echo "[2/7] 엔진 vendoring (api/_engine — Vercel 함수용)"
python3 scripts/sync_engine.py

echo "[3/7] 모형 v1.0 — 운영규칙 P0/P1/A/B + 정책그리드 (수 분 소요)"
python3 -u scripts/run_model.py

echo "[4/7] 경매 최저가격 격자 + 기술비용 ±20% 민감도"
python3 scripts/run_escalator_floor.py

echo "[5/7] 인접 빈티지 캐리 실증 (KRX 원자료)"
python3 scripts/build_carry_analysis.py

echo "[6/7] 보고서 그림 5종 (docs/figures/)"
python3 scripts/build_figures.py

echo "[7/7] 검증 — 단위 + 골든 회귀 + MCP 계약"
python3 -m pytest tests/ -q

echo
echo "완료. 산출:"
echo "  outputs/runs/msr_results_v1.0.json          운영규칙 4종"
echo "  outputs/runs/escalator_floor_cce_v2.0.json  최저가격 격자"
echo "  outputs/runs/carry_analysis_cce_v2.0.json   캐리 실증"
echo "  docs/figures/fig1..5.png                    보고서 그림"
echo "  public/model/kets_data.json                 웹·MCP 데이터 계약"

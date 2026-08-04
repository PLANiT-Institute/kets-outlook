# outputs/ — 모형 산출물

전부 `scripts/`의 러너가 생성한다. 손으로 편집하지 않는다.

| 파일 | 생성 스크립트 | 내용 |
|---|---|---|
| `runs/msr_results_v1.0.json` | `run_model.py` | 운영규칙 P0/P1/A/B 경로 · 게이트 워터폴 · λ 레짐 · 수량규칙 프런티어 · 수소×전력 민감도 · MACC/cap/MSR 하이퍼큐브 |
| `runs/escalator_floor_cce_v2.0.json` | `run_escalator_floor.py` | 경매 최저가격 격자(출발가 × 실질 상승률) · 필요보류량 · 기술비용 ±20% 민감도 |
| `runs/carry_analysis_cce_v2.0.json` | `build_carry_analysis.py` | 인접 빈티지 캐리 실증 요약 (KRX 원자료) |
| `runs/taschini_ext_v0.2.json` | `run_taschini_extensions.py` | 불확실성 밴드 · 하한 옵션가치 · CCR vs TNAC |
| `runs/msr_results_v0.7.json` | — (보존) | v0.7 동결본. `run_model.py`가 회귀비교(`parity_v07` 블록)에 읽는 **입력**이다. 없어도 실행은 되지만 비교 블록이 빠진다. |
| `csv/*.csv` | `run_model.py`, `run_taschini_extensions.py` | 위 JSON의 표 형태 추출 |
| `supplementary/carry_pairs_cce.csv` | `build_carry_analysis.py` | 인접 빈티지 쌍 전수 (5,693행) — `build_figures.py`의 입력 |
| `supplementary/carry_summary_by_year_cce.csv` | `build_carry_analysis.py` | 연도별 캐리 요약 |

전체 재생성: `bash scripts/reproduce_all.sh`

`docs/report.md`에 인쇄된 헤드라인 수치는 `tests/test_reproducibility.py`가 이
파일들과 대조해 잠근다.

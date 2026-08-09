<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# kets-outlook 작업 규칙

## 절대 규칙

1. **숫자를 코드에 넣지 않는다.** 모형 파라미터·시나리오는 전부
   `data/K-ETS_마스터데이터.xlsx`에서 온다. 파라미터를 바꾸려면 엑셀 시트를 고치고
   파이프라인을 다시 돌린다. placeholder·가정값 금지 — 출처 없는 수치를 쓰지 않는다.
   원자료(시장 시세·등록부)는 `data/ets_data.xlsx`이며 `build_carry_analysis.py`만
   읽는다. 두 파일의 역할 구분은 `data/README.md` 참조.

   엑셀을 고쳤으면 **반드시** 지문을 갱신한다:

   ```bash
   python3 scripts/build_manifest.py     # data/MANIFEST.json 재생성
   ```

   갱신하지 않으면 `tests/test_data_integrity.py`가 어느 시트의 어떤 값이 바뀌었는지
   지목하며 실패한다. 그 마찰이 목적이다 — 데이터 변경이 커밋 디프에 남아야 한다.
   마스터 엑셀 사본이 Drive에도 있다면 그쪽이 아니라 **리포가 정본**이다
   (2026-08-09 B14 해소: Drive 사본은 B0=70Mt·λ=0.55 가정치였고 리포가 실측 기반).
2. **`api/_engine/`을 직접 고치지 않는다.** 생성물이다. 원본은 `kets/`이고
   `python3 scripts/sync_engine.py`가 재생성한다.
3. **`docs/report.md`의 수치를 손으로 고치지 않는다.** 숫자는 엔진 → `outputs/runs/`
   → 보고서 방향으로만 흐른다. 반대 방향은 금지.
4. **골든 테스트를 통과시키려고 기대값 상수를 바꾸지 않는다.**
   `tests/test_reproducibility.py`가 깨지면 왜 달라졌는지 먼저 확인한다.

5. **시나리오 레버는 엔진에 하나만 둔다.** 비용·에너지가격을 흔들려고 모형을 만든 뒤
   `model.techs`를 손으로 곱하지 않는다. `model_params`의 `cost_multiplier` ·
   `h2_scenario` · `elec_scenario` · `tech_scenario`를 쓴다 — CLI·웹·MCP가 모두 같은
   경로를 타야 세 표면의 답이 갈라지지 않는다. 새 레버를 더하면 `api/solve.py`의
   `_MODEL_LEVER_KEYS`, MCP 도구 스키마, `tests/test_scenario_levers.py`를 함께 고친다.

## 논문 수치를 고칠 때

원고는 이 저장소 밖(비공개)에 있으므로 테스트가 잠그지 못한다. 대신 대조한다:

```bash
python3 scripts/audit_paper_numbers.py --paper /경로/원고.md --strict
```

원고에 인쇄된 모든 숫자가 `outputs/`의 산출값으로 되돌아가야 한다. 되돌아가지
않으면 원고가 옛 실행에서 나왔다는 뜻이다 — 원고가 아니라 파이프라인을 먼저 본다.

## 엔진을 고쳤을 때

```bash
python3 scripts/sync_engine.py     # vendoring 재생성
bash scripts/reproduce_all.sh      # 전체 재현 + 검증
```

## 구조

- `kets/` 모형 엔진 (정본, numpy + stdlib만)
- `api/` Vercel 서버리스 함수 + vendored 엔진
- `mcp/` MCP 서버 (`api/solve.py` 재사용)
- `src/`, `public/` Next.js 대시보드
- 상세: `docs/architecture.md`

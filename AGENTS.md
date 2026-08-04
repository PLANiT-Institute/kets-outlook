<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# kets-outlook 작업 규칙

## 절대 규칙

1. **숫자를 코드에 넣지 않는다.** 모든 모형 입력은 `data/K-ETS_마스터데이터.xlsx`에서
   온다. 파라미터를 바꾸려면 엑셀 시트를 고치고 파이프라인을 다시 돌린다.
   placeholder·가정값 금지 — 출처 없는 수치를 쓰지 않는다.
2. **`api/_engine/`을 직접 고치지 않는다.** 생성물이다. 원본은 `kets/`이고
   `python3 scripts/sync_engine.py`가 재생성한다.
3. **`docs/report.md`의 수치를 손으로 고치지 않는다.** 숫자는 엔진 → `outputs/runs/`
   → 보고서 방향으로만 흐른다. 반대 방향은 금지.
4. **골든 테스트를 통과시키려고 기대값 상수를 바꾸지 않는다.**
   `tests/test_reproducibility.py`가 깨지면 왜 달라졌는지 먼저 확인한다.

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

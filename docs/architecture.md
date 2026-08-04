# 저장소 구조와 세 가지 사용 경로

같은 엔진 하나(`kets/`)를 세 방식으로 쓴다. **계산은 한 곳에만 있다** — 경로가
달라도 숫자가 갈라지지 않는 것이 이 구조의 목적이다.

```
                      data/K-ETS_마스터데이터.xlsx  (SSOT)
                                   │
                          kets/excel_source.py
                                   │
                      ┌────────────┴────────────┐
                      │                         │
          KETSModel.from_excel()      scripts/export_web_data.py
                      │                         │
                      │              public/model/kets_data.json
                      │                         │
                      │              KETSModel.from_json()
                      │                         │
        ┌─────────────┼─────────────┐           │
        │             │             │           │
   scripts/ CLI   mcp/server.py  tests/     api/solve.py
   (재현 파이프라인)  (Claude)              (Vercel 서버리스)
                                                │
                                          src/ (Next.js 대시보드)
```

---

## 1. CLI — 재현 파이프라인

연구 산출물을 처음부터 다시 만드는 경로.

```bash
pip install -r requirements-dev.txt
bash scripts/reproduce_all.sh
```

| 스크립트 | 하는 일 |
|---|---|
| `export_web_data.py` | 엑셀 → `public/model/*.json` 데이터 계약 |
| `sync_engine.py` | `kets/` → `api/_engine/` vendoring (Vercel용) |
| `run_model.py` | 운영규칙 4종 + 정책그리드 전수 solve (수 분) |
| `run_escalator_floor.py` | 경매 최저가격 격자 + ±20% 민감도 (3초) |
| `build_carry_analysis.py` | KRX 원자료 → 인접 빈티지 캐리 실증 |
| `run_taschini_extensions.py` | 불확실성 밴드·옵션가치·CCR 비교 |
| `calibrate_liquidity.py` | 관측가에서 λ 역산 |
| `build_figures.py` | 보고서 그림 5종 (300dpi) |

산출은 전부 `outputs/`에 떨어지고, 헤드라인 수치는 `tests/test_reproducibility.py`가
잠근다.

---

## 2. MCP — Claude가 모형을 직접 돌린다

`mcp/server.py` — stdio JSON-RPC MCP 서버. 표준 라이브러리 + numpy만 쓴다
(`pip install mcp` 불필요).

등록:

```json
{
  "mcpServers": {
    "kets": { "command": "python3", "args": ["/절대경로/kets-outlook/mcp/server.py"] }
  }
}
```

도구 7종:

| 도구 | 용도 |
|---|---|
| `list_packages` | 운영규칙 4종·시나리오·MSR 프리셋 조회 (먼저 호출) |
| `solve_package` | 운영규칙 하나를 실제 엔진으로 solve → 가격경로 |
| `solve_custom` | MSR 레버·λ를 직접 지정한 임의 시나리오 |
| `list_data_sheets` / `get_data_sheet` | 데이터 계약 원본 열람 |
| `list_runs` / `get_run` | 저장된 실행 결과 조회 (재계산 없이) |

**설계 요점**: MCP 서버는 `api/solve.py`의 함수를 그대로 재사용한다. 웹 API와 MCP가
같은 코드 경로를 타므로 두 결과가 갈라질 수 없다.
`tests/test_mcp_server.py`가 실제 서브프로세스로 핸드셰이크를 돌려
(a) 프로토콜 계약과 (b) 엔진 직접 호출과의 수치 일치를 함께 검증한다.

자세한 내용은 [`mcp/README.md`](../mcp/README.md).

---

## 3. Vercel — 웹 대시보드 + 라이브 API

리포 루트가 Next.js 앱이자 Vercel 프로젝트 루트다.

```
src/app, src/components, src/lib   Next.js 15 (App Router, TypeScript)
public/model/*.json                빌드타임 데이터 계약 (정적)
api/solve.py                       Python 서버리스 함수
api/_engine/                       GENERATED — kets/ vendoring
vercel.json                        함수 런타임 선언
requirements.txt                   numpy만 (함수 번들 의존성)
requirements-dev.txt               pandas·openpyxl·matplotlib (로컬 전용)
```

**두 개의 데이터 경로**

1. **Overview 탭 — 정적.** `public/model/results_v1.json`을 그대로 읽는다.
   `run_model.py`가 만든 확정 결과의 슬림 추출본이라 서버 호출이 없다.
2. **Simulator 탭 — 라이브.** `POST /api/solve`가 실제 엔진을 콜드스타트에서
   1회 로드하고 슬라이더 값으로 재solve한다.

API 계약:

```bash
# 메타 (시나리오·패키지·프리셋)
curl -s https://<배포주소>/api/solve

# 운영규칙 solve
curl -s https://<배포주소>/api/solve -X POST \
  -d '{"package_id":"A","overrides":{"corridor_target_year":2033}}'

# 커스텀 레버
curl -s https://<배포주소>/api/solve -X POST \
  -d '{"scenario":"base","msr":{"rho":0.24,"cancel":1.0},"liquidity":{"lam_0":0.55}}'
```

로컬에서 함수만 띄우기:

```bash
python3 api/solve.py     # http://localhost:8531
```

### 왜 vendoring인가

`@vercel/python`은 함수 파일과 그 하위 디렉터리만 번들에 넣는다. 리포 루트의
`kets/` 패키지는 번들에 포함되지 않으므로 `scripts/sync_engine.py`가 엔진 4개 파일을
`api/_engine/`으로 복사하고 import 경로를 재작성한다. 산출 파일에는 `GENERATED —
DO NOT EDIT` 헤더가 붙는다. **`api/_engine/`을 직접 고치지 말 것** — 원본은 `kets/`다.

의존성을 `requirements.txt`(numpy만)와 `requirements-dev.txt`로 쪼갠 이유도 같다.
pandas·matplotlib이 함수 번들에 들어가면 250MB 한도에 부딪힌다.

배포:

```bash
npm run build      # Next.js 빌드 확인
vercel deploy      # 프리뷰
vercel deploy --prod
```

---

## 4. 디렉터리 요약

| 경로 | 내용 |
|---|---|
| `kets/` | **모형 엔진 (정본)** — numpy + stdlib |
| `data/` | 마스터 엑셀(SSOT) + KRX 시장 원자료 |
| `scripts/` | 재현 파이프라인 |
| `outputs/runs/` | 실행 결과 JSON (확정 산출물) |
| `outputs/csv/`, `outputs/supplementary/` | 표·부속 자료 |
| `tests/` | 단위 + 골든 회귀 + MCP 계약 |
| `docs/` | 보고서·방법론·이 문서 + 그림 |
| `mcp/` | MCP 서버 |
| `api/` | Vercel 서버리스 함수 (+ vendored 엔진) |
| `src/`, `public/` | Next.js 대시보드 |

---

## 5. 무엇을 고치면 무엇이 깨지나

| 고친 것 | 다시 돌려야 하는 것 |
|---|---|
| `data/K-ETS_마스터데이터.xlsx` | `export_web_data.py` → 러너 전부 → `build_figures.py` |
| `kets/engine.py` 등 엔진 | `sync_engine.py` + 러너 전부 + `pytest` |
| `docs/report.md`의 수치 | 반대 방향은 금지 — 숫자는 엔진에서만 나온다 |
| Next.js `src/` | `npm run build` |

`bash scripts/reproduce_all.sh` 하나가 위 순서를 전부 담고 있다.

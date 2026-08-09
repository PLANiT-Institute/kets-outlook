# kets-outlook

**K-ETS 배출권 가격전망 모형 · K-MSR 운영규칙 분석**
Coase 정태균형 + 계단형 MACC + 제약 Hotelling + 유동성 전달(λ)

<details>
<summary><b>In English</b> — what this is and how to run it</summary>

A calibrated equilibrium model of the Korean ETS. It projects KAU allowance
prices for 2026–2040 and asks **which operating rule** for the Korean Market
Stability Reserve (legislated April 2026) gets the price high enough, soon
enough, for hydrogen steelmaking and electrified crackers to clear their cost
thresholds.

Four layers: a static Coase equilibrium, a step MAC curve built bottom-up from
technology data (no fitted functional form), constrained Hotelling arbitrage,
and a liquidity transmission parameter λ inverted from the observed price wedge
(λ ≈ 0.575 in 2026 — Korea's forward vintages are effectively untraded, so the
intertemporal channel is damped rather than complete).

**Headline.** The cap alone leaves KAU at ~₩67k in 2040, short of the ~₩95k
hydrogen-steel threshold. A pre-announced auction reserve price starting at
₩40,000 in 2026 and escalating 7% in real terms, combined with permanent
cancellation of unsold volume, reaches the threshold in 2039 — and is the only
starting price that survives the full ±20% technology cost range.

```bash
pip install -r requirements-dev.txt
bash scripts/reproduce_all.sh      # regenerates every output from the master workbook
python3 -m pytest tests -q         # locks the numbers printed in the report
```

Register the MCP server and ask the model directly:

```json
{"mcpServers": {"kets": {"command": "python3",
                         "args": ["/abs/path/kets-outlook/mcp/server.py"]}}}
```

Scenario levers — cap path, MSR design, auction reserve price, hydrogen and
electricity price trajectories, technology learning rates, abatement capital
cost — are all reachable from the MCP tools. See [mcp/README.md](mcp/README.md)
for the lever table and [docs/methodology.md](docs/methodology.md) for the
equations. Code is MIT; the redistributed market and registry data are not —
see [LICENSE](LICENSE).

</details>

한국 배출권거래제(K-ETS)의 2026–2040 KAU 가격경로를 계산하고, 2026년 4월 법제화된
K-MSR(시장안정화 예비분)을 **어떤 규칙으로 운영해야** 철강·석유화학의 전환기술이
경제성을 갖는 시점에 도달하는지 평가한다.

> **핵심 결과** — 현행 총량만으로는 2040년 KAU가 약 6.7만 원에 그쳐 철강
> 수소환원제철 문턱(약 9.5만 원)에 닿지 않는다. 2026년 **4만 원 출발 · 실질 7%
> 상승**의 사전공표 경매 최저가격에 **유찰물량 영구취소**를 결합하면 2039년에
> 문턱에 도달하며, 기술비용 ±20% 전 범위에서 방어 가능한 유일한 출발가격이다.
>
> → 전체 설명: **[docs/report.md](docs/report.md)**

---

## 문서

| 문서 | 내용 |
|---|---|
| **[docs/report.md](docs/report.md)** | 보고서 — 문제·모형·결과·반론·한계 (비전문가도 읽을 수 있게) |
| [docs/methodology.md](docs/methodology.md) | 방법론 — 수식과 구현 대조, 데이터 계약 |
| [docs/architecture.md](docs/architecture.md) | 구조 — CLI · MCP · Vercel 세 경로 |
| [mcp/README.md](mcp/README.md) | MCP 서버 등록·도구 목록 |

---

## 빠른 시작

### 1. 모형 돌리기 (CLI)

```bash
pip install -r requirements-dev.txt
bash scripts/reproduce_all.sh
```

전체 재현에는 수 분이 걸린다. 빠른 확인만 하려면:

```bash
python3 scripts/run_escalator_floor.py     # 3초, 경매 최저가격 격자
python3 -m pytest tests -q                 # ~30초, 헤드라인 수치 검증
```

### 2. Claude에서 쓰기 (MCP)

```json
{
  "mcpServers": {
    "kets": { "command": "python3", "args": ["/절대경로/kets-outlook/mcp/server.py"] }
  }
}
```

등록하면 Claude가 `solve_package`·`solve_custom`으로 실제 엔진을 돌린다.
`pip install mcp` 불필요 — 표준 라이브러리 + numpy만 쓴다.

### 3. 웹 대시보드 (Vercel)

```bash
npm install
npm run dev              # http://localhost:3000
python3 api/solve.py     # http://localhost:8531 (라이브 solve API, 별도 터미널)
```

탭 4종 — **홈**(운영규칙 비교) · **메커니즘**(가격 결정 도형 + λ 브리지) ·
**시뮬레이터**(`POST /api/solve` 라이브 재solve) · **보고서**(논증 사슬 요약).
보고서 탭은 `docs/report.md`와 같은 산출물을 읽으므로 문서와 화면이 갈라지지 않는다.

---

## 저장소 구조

```
kets/           모형 엔진 (정본) — numpy + stdlib만
data/           마스터 엑셀(SSOT) + KRX 시장 원자료
scripts/        재현 파이프라인
outputs/        실행 결과 JSON·CSV
tests/          단위 + 골든 회귀 + MCP 계약 (40 tests)
docs/           보고서·방법론·구조 + 그림
mcp/            MCP 서버
api/            Vercel 서버리스 함수 (+ vendored 엔진)
src/, public/   Next.js 대시보드
```

---

## 설계 원칙

1. **SSOT는 엑셀 하나.** 모든 모형 입력은 `data/K-ETS_마스터데이터.xlsx`에서 온다.
   엔진에 데이터 상수가 없다(유일한 예외: 이분법 탐색 상한).
2. **계산은 한 곳에만.** CLI · MCP · 웹 API가 같은 `kets/` 엔진을 탄다.
   `api/_engine/`은 Vercel 번들용 생성물이며 직접 고치지 않는다.
3. **보고서 수치는 테스트가 잠근다.** `tests/test_reproducibility.py`가
   `docs/report.md`에 인쇄된 값을 그대로 검증한다. 숫자는 엔진 → 결과 → 보고서
   방향으로만 흐른다.

작업 규칙은 [AGENTS.md](AGENTS.md).

---

## 검증 상태

| 항목 | 상태 |
|---|---|
| 테스트 | 41 passed |
| 엔진 커버리지 | 89% (`kets/engine.py`) · 전체 83% |
| 재현성 | `bash scripts/reproduce_all.sh` 로 마스터 엑셀에서 전 산출물 재생성 |
| 기준선 정합 | 모형 B0 = 등록부 실측 이월잔고 92.140 Mt — 러너 간 일치를 테스트가 강제 |

---

**PLANiT Institute** · 모형 v1.0 · 데이터 기준 2026-07

# 방법론

[report.md](report.md)가 결론을 설명한다면, 이 문서는 그 결론이 어떤 계산에서
나왔는지를 설명한다. 코드 위치를 함께 적었으니 수식과 구현을 대조할 수 있다.

---

## 1. 데이터 계약 — 숫자는 코드에 없다

```
data/K-ETS_마스터데이터.xlsx   (SSOT, 26개 시트)
        │
        ├─ kets/config.py         시트 → DataFrame (pandas, lru_cache)
        ├─ kets/excel_source.py   시트 → 엔진 dict (데이터 계약)
        │
        ├─ (로컬)  KETSModel.from_excel()
        └─ (배포)  scripts/export_web_data.py → public/model/kets_data.json
                   → KETSModel.from_json()
```

로컬 엑셀 경로와 프로덕션 JSON 경로가 **같은 dict 구조**를 만든다. 따라서 웹에서
본 숫자와 CLI에서 돌린 숫자가 갈라질 수 없다.

**엔진의 하드코딩 상수는 둘뿐이며 둘 다 경제 가정이 아니라 수치 안전경계다:**
이분법 탐색 구간의 하한 `100.0`원과 상한 `PRICE_CEIL = 5e7`원(`kets/engine.py`).
보고된 어떤 실행에서도 두 경계가 구속되지 않는다 — 실제 해는 9,862 ~ 128,927원
범위에 있다. 마스터 엑셀의 `모형파라미터 · Solver` 행(`price_lower_bound` 5,000 /
`price_upper_bound` 300,000 / `tolerance` / `method`)은 **엔진이 읽지 않는 레거시**이며,
같은 이유로 `Banking · initial_bank_low_Mt` / `initial_bank_high_Mt`,
`MSR · msr_enabled`도 현재 참조되지 않는다. 남겨둔 것은 이력 보존 목적이다.

주요 시트:

| 시트 | 내용 |
|---|---|
| `모형파라미터` | 할인율·리스크프리미엄·환율·분석기간·초기 이월잔고 |
| `배출허용총량` | cap 경로 3종 (base / middle / ideal) |
| `BAU배출전망` | 업종별 BAU 배출 |
| `MACC기술상세` | 감축기술별 비용·잠재량·가용연도 |
| `학습곡선` | 기술비용 학습률 (문턱이 시간에 따라 낮아지는 원천) |
| `무상할당비율` | 무상할당 비율 경로 → 경매 비중 A_gov |
| `MSR설계` | MSR 강도 프리셋 (L0…L_QB) |
| `유동성모수` | λ₀·ψ 기본값 |
| `정책패키지` | 운영규칙 P0/P1/A/B 정의 |
| `수소가격시나리오`·`전력가격시나리오` | 민감도 2×2 |
| `KAU과거가격`·`KAU2026시세` | λ 역산용 관측가 |

---

## 2. MACC — 계단형이 기본

한계감축비용 곡선을 두 형태로 지원한다(`macc_mode`).

- **`step`(기본)** — 기술 하나가 하나의 계단. 가격이 기술 비용을 넘으면 그 기술의
  잠재량이 통째로 들어온다. 실제 산업 감축이 연속 조정이 아니라 설비 단위 이산
  선택이라는 사실을 반영한다. `KETSModel._abatement_step()`
- **`exponential`** — MAC(a) = α·exp(β·a) 매끄러운 형태. 민감도 비교용.
  `KETSModel._abatement_exp()`

기술 비용은 학습곡선을 타고 연도별로 낮아진다(`_tech_cost`). 그래서 철강 문턱이
2035년 97,500원에서 2037년 94,500원으로 **내려간다** — 같은 기술이 나중에 싸진다.

### 2.1 비용의 세 채널

`_tech_cost(tech, year, sid)`는 기술마다 **하나의** 채널만 탄다. 순서가 곧 우선순위다.

| 조건 | 비용 경로 | 레버 |
|---|---|---|
| `h2_intensity > 0` | 비수소 잔여 + h2_kg × 수소가격(t) | `h2_scenario` |
| `elec_intensity > 0` | 비전력 잔여 + MWh × 전력가격(t) | `elec_scenario` |
| 둘 다 없음 | 시트 비용 × (1 − 학습률)^(t−2026) | `tech_scenario` |

에너지집약 기술에 학습률을 **겹쳐 적용하지 않는다.** 수소환원제철의 비용 하락은
전해조 학습이 아니라 수소 도입가격 경로에 이미 들어 있고, 둘을 곱하면 같은 학습을
두 번 세게 된다. 대신 그 기술들의 자본비용 불확실성은 `cost_multiplier`로 흔든다 —
시트 비용에 곱해지므로 세 채널 전부에 작용한다.

따라서 **헤드라인 2기술(H₂-DRI · e-NCC)은 `tech_scenario`에 반응하지 않는다.**
설계이며 `tests/test_scenario_levers.py`가 그 경계를 잠근다. 이 기술들의 문턱
연도를 흔들려면 에너지가격 경로나 자본비용 배율을 써야 한다.

`tech_scenario`를 지정하지 않으면 cap 시나리오(`base`/`middle`/`ideal`)를 따른다 —
기존 동작이다. 지정하면 분리된다: cap을 조이는 것과 기술이 빨리 싸지는 것은 서로
다른 사건이므로 독립으로 흔들 수 있어야 한다.

---

## 3. 세 층의 가격

### 3.1 정태 균형 (Coase)

그 해의 유효 부족량 `sf`(= BAU − cap − 무상할당 조정)를 그 해의 MACC로 청산한다.

```
P_static(t) = { P : A(P, t) = sf(t) }        # A = 가격 P에서의 감축량
```

구현: `_static_eq()` — `_excess_demand`의 근을 이분법으로 찾는다.
해가 없으면(공급 과잉) 하한 100원, 초과수요가 극단이면 `PRICE_CEIL`.

### 3.2 제약 Hotelling (이월 균형)

이월이 가능하면 배출권은 고갈성 자원처럼 행동한다. 균형 조건은 **할인가격의
비증가**다.

```
e^{−rt} · P_t  는 t에 대해 비증가
  · bank_t > 0 구간 : P_t 는 정확히 r로 상승   (기간 간 무차익)
  · bank_t = 0 시점 : 하향 점프 허용            (차입 불가 제약이 binding)
  · 상향 점프       : 어떤 경우에도 불가        (매입·이월 차익이 생기므로)
```

(Rubin 1996; Schennach 2000)

**구현이 까다로운 지점**: 단순히 "은행잔고가 처음 음수가 되는 해에서 자르는" 방식은
경계에서 **상향 점프**를 만들어 차익 기회를 남긴다. v0.7에서 "MSR이 근시일 가격을
낮춘다"는 역설이 나온 원인이 이것이었다.

v0.8 이후의 알고리즘(`_solve_constrained_hotelling`)은 상(phase) 분해로 푼다:

1. 잔여 구간의 모든 후보 소진연도 `h`에 대해, "h에서 은행잔고가 정확히 0"이 되는
   Hotelling 초기가 `p0(h)`를 푼다.
2. `h* = argmax_h p0(h)` 를 상 경계로 채택한다.
3. `p0* = max` 이므로 구간 내 모든 `t ≤ h*`에서 잔고가 음수가 되지 않고, 후속 상의
   초기 할인가는 `p0*`를 넘을 수 없다 → **경계 점프는 항상 하향** → 무차익 충족.

`r = discount_rate + risk_premium` (엑셀 `모형파라미터` 시트).

**이월 상한**의 역할: 상한에 걸린 보유자는 포지션을 더 늘릴 수 없으므로 기대 상승률이
통상의 보유 조건을 초과할 수 있다. 이것이 "최저가격을 이자율보다 빨리 올리면 무한
차익 수요가 생긴다"는 반론을 무력화한다. 단, 이는 **수량 수요에 상한이 걸린다**는
뜻이지 "경매가 반드시 유찰된다"는 뜻이 아니다 — 이 구분이 §5의 해석 주의사항이다.

### 3.3 유동성 전달 λ

```
P_realized(t) = P_static(t) + λ(t) · [ P_hotelling(t) − P_static(t) ]
```

`kets/liquidity.py` · `KETSModel.level_bridge_path()`

- λ는 **역산값**이다: `λ_implied = (P_obs − P_static) / (P_hotelling − P_static)`.
  2026년 6월 관측가 22,750원 기준 λ ≈ **0.575**. `scripts/calibrate_liquidity.py`가
  이 값을 재계산해 `유동성모수` 시트와 대조하고, 어긋나면 실패한다(시트 stale 방지).
- `lambda_ramp(λ₀, λ_terminal, ramp_years)` 로 시간 경로를 준다.
- 레짐 3종: `relapse`(다시 0으로) · `hold`(유지) · `consolidate`(1로 수렴).
  §7 민감도의 축 하나가 이것이다.
- ψ(이월제한 이벤트 전달계수)는 문헌 범위 [−0.5, 0]으로만 특정했고 점추정 미착수
  (`transmission_multiplier`, `calibrate_psi_from_event`).

---

## 4. MSR 고정점

MSR 흡수량 `I_t`는 전년도 잉여(TNAC ≈ `bank_{t−1}`)에 의존하고, 잉여는 가격 경로에
의존한다 → **고정점 문제**.

임계형(트리거) 규칙은 불연속이라 단순 반복이 진동한다. `_msr_fixed_point()`는
감쇠 계수 α = 0.5의 완화 반복(최대 120회)으로 수렴시킨다.

MSR 레버 (`msr` dict):

| 키 | 뜻 |
|---|---|
| `rho` | 흡수 비율 (잉여의 몇 %를 빨아들이나) |
| `theta_plus` | 흡수 발동 상한 임계 (TNAC이 이보다 크면 흡수) |
| `theta_minus` | 방출 발동 하한 임계 |
| `release` | 연간 방출량 |
| `cancel` | 흡수분 중 **영구 취소** 비율 |
| `carve_reserve` | 예비분 carve-out — 4차 cap이 예비분을 포함하므로, carve 없이 방출하면 이중계상된다 |

**`cancel`이 결론을 가른다.** 흡수만 하고 나중에 방출하면 누적 공급이 불변이라
장기 가격이 움직이지 않는다(워터베드, Perino & Willner 2016). 취소해야 누적 공급이
줄어 희소성이 유지된다. 보고서 §4에서 P1이 2040년 가격을 못 올리는 이유가 이것이다.

---

## 5. 운영규칙(패키지) 풀이

`KETSModel.solve_package(pkg)` — `정책패키지` 시트의 행 하나가 운영규칙 하나다.

- **P0** 무정책 반사실: L0, 하한 없음, base cap, λ hold
- **P1** 시행령 초안대로: L3 수량규칙 + M_mid 하한
- **A** 가격약속형: 회랑 하한(2026 관측가 → 목표연도 기술 문턱) + carve-only 백스톱,
  미유찰 보류물량 무효화
- **B** 수량약속형: 2035 개시 사전공표, 무조건 경매물량 50% 흡수·전량 취소

회랑 하한 경로는 `corridor_floor_path(sid, target_tech_sub, target_year, ...)`가
생성한다 — 시작점(관측가)과 종점(목표 기술 문턱)을 잇는 사전공표 경로다.

반환 레코드 필드:

| 필드 | 뜻 |
|---|---|
| `kau` | 실현가 (λ 전달 적용 후) |
| `kau_prefloor` | 하한 적용 전 가격 |
| `static` / `hotelling` | 두 극단 (전달 분해용) |
| `floor` | 그 해 하한 |
| `defended` | 하한 방어 여부 |
| `headroom` | 방어 여유율 |
| `bank_Mt` | 은행잔고 |
| `intake_Mt` / `release_Mt` | MSR 흡수·방출 |

---

## 6. 경매 최저가격 시나리오

`scripts/run_escalator_floor.py` — 출발가격 × 실질 상승률 격자.

```
floor(t) = f₀ · (1 + g)^(t − 2026)      # g = 실질 상승률
```

**필요보류량(required withholding)** = 기준 균형가격에서 제안 하한까지 가격을
올리는 데 대응하는 **정태적 공급 감소량**.

> 이것은 유찰량 예측이 **아니다**. 실제 유찰은 경매 수요곡선에 달렸고 이 모형은
> 경매 수요곡선을 추정하지 않는다. 산출 JSON의 `meta.interpretation`에 같은
> 경고가 들어 있다.

기술비용 ±20% 격자로 실현가능성을 검사한다 → 보고서 §6 표.

---

## 7. 이론 확장 레이어

`kets/taschini_extensions.py` — 세 문헌의 장치를 K-ETS 수치에 얹는다.

| 출처 | 장치 | 산출 |
|---|---|---|
| Kollenberg & Taschini (2019) | 불확실성 하 위험조정 가격 밴드 | `taschini_uncertainty_band.csv` |
| Grüll & Taschini (2011) | 가격 하한 = 풋옵션, 그 옵션가치 | `taschini_floor_option_value.csv` |
| Borghesi et al. (2025) | CCR(비용억제예비분) vs TNAC 규칙 비교 | `taschini_ccr_vs_tnac.csv` |

우리 모형은 KT2019의 **위험중립 극한**에 해당한다. 이건 결함이 아니라 재현이다 —
KT2019 원문(GRI WP 195 초록)이 "for risk-neutral firms a cap-preserving MSR is largely
irrelevant"라고 못박는다. 총량을 보존하는 수량규칙(P1 시행령 초안)이 2040 가격을
움직이지 않는 것은 그 정리의 결과이며, `test_p1_does_not_move_2040_price`가 잠근다.
위험회피를 넣으면 부호가 뒤집힌다(예비분 축적 → 변동성↑ → 위험프리미엄↑ → 은행 조기소진
→ 감축↓ → 가격↓) — 그것이 위 표 첫 줄의 불확실성 채널이다.

### 7.1 풋옵션 분해의 한계 (미해소)

GT2011은 하이브리드 설계를 일반 cap-and-trade + **유럽형 또는 미국형** 콜·풋의 결합으로
분해한다. `_black76_put()`은 **유럽형 하나**를 쓴다. 그러나 경매마다 최저가격을 거는
규칙은 엄밀히는 **경매 횟수만큼의 유럽형 풋 다발(strip)** 이고, 다발의 가치는 단일
옵션과 같지 않다(각 만기의 분산이 다르고, 행사가 경로가 에스컬레이션을 따른다).

현 구현은 근사이며 방어비용의 **수준**이 아니라 **비교**(하한별 상대 크기)에만 쓴다.
정확히 하려면 경매 일정에 맞춘 만기 사다리로 재구현해야 한다. GT2011 전문은 미대조
(ScienceDirect 403, SSRN 1518102 미확인) — 인용을 강화하려면 그 대조가 선행돼야 한다.

실행: `python3 scripts/run_taschini_extensions.py`

---

## 8. 검증

| 검증 | 위치 |
|---|---|
| 엔진 단위 테스트 (커버리지 89%) | `tests/test_engine.py` |
| MACC 형태·시장청산 | `tests/test_macc.py`, `tests/test_market_clearing.py` |
| 이론 확장 | `tests/test_taschini_extensions.py` |
| **보고서 헤드라인 골든 회귀** | `tests/test_reproducibility.py` |
| **MCP 프로토콜 계약 + 엔진 일치** | `tests/test_mcp_server.py` |

골든 회귀는 `docs/report.md`에 인쇄된 값을 그대로 잠근다. 엔진을 고쳐 숫자가
달라지면 테스트가 먼저 깨지고, 그때 보고서도 함께 고쳐야 한다는 신호가 된다.
값을 맞추려고 상수를 바꾸지 말 것.

# K-ETS Outlook MCP 서버

Claude가 K-ETS 배출권 가격전망 모형을 직접 돌리게 하는 MCP 서버.
"2035년 개시 수량규칙이면 철강 문턱을 언제 넘나?" 같은 질문에 대해, 요약된 텍스트가
아니라 **실제 엔진을 돌린 결과**로 답하게 된다.

## 설치

없다. 표준 라이브러리 + numpy만 쓴다.

```bash
pip install numpy
```

MCP 프로토콜 표면이 작아서(`initialize` / `tools/list` / `tools/call` / `ping`)
SDK 없이 직접 구현했다 — 의존성 하나를 줄이는 대신 서버 파일 하나로 끝난다.

## 등록

**Claude Code** — `~/.claude.json` 또는 프로젝트 `.mcp.json`:

```json
{
  "mcpServers": {
    "kets": {
      "command": "python3",
      "args": ["/절대경로/kets-outlook/mcp/server.py"]
    }
  }
}
```

**Claude Desktop** — `claude_desktop_config.json`에 같은 블록.

## 도구

| 도구 | 인자 | 반환 |
|---|---|---|
| `list_packages` | — | 운영규칙 4종(P0/P1/A/B) 메타 · 시나리오 레버 선택지 · MSR 프리셋 · λ 기본값 |
| `solve_package` | `package_id`, `macc_mode`, `overrides` | 2026–2040 연도별 가격경로, 기술 활성화 연도, 최대낙폭, 누적흡수량 |
| `solve_custom` | `scenario`, `macc_mode`, `msr`, `liquidity`, `overrides` | 정태·Hotelling·실현가 3층 분해 경로 |
| `scenario_grid` | `packages`, `h2_scenarios`, `elec_scenarios`, `tech_scenarios`, `cost_multipliers` | 레버 조합 전체를 한 표로 (조합 상한 64) |
| `list_data_sheets` | — | 데이터 계약 시트 목록 + 행 수 |
| `get_data_sheet` | `name`, `limit` | 시트 실제 행 (cap 경로·MACC 기술상세 등) |
| `list_runs` | — | 저장된 실행 결과 JSON 목록 |
| `get_run` | `name`, `key` | 저장 결과 조회 (`key`로 점 표기 하위 경로) |

## 시나리오 레버

두 종류를 구분한다. **정책 레버**는 정부가 무엇을 약속하는가, **모형 레버**는
어떤 세계에서 그 약속을 하는가다. 둘 다 `overrides`로 준다.

| 키 | 값 | 무엇을 바꾸나 |
|---|---|---|
| `cap_scenario` | `base` `middle` `ideal` | 배출허용총량 경로 (정책) |
| `lambda_regime` | `relapse` `hold` `consolidate` | 유동성 전달 λ의 향후 레짐 (정책) |
| `corridor_target_year` | 연도 | 가격회랑이 문턱에 닿아야 하는 해 (정책) |
| `h2_scenario` | `gov` `conservative` | 수소 도입가격 경로 → **H₂-DRI 비용** |
| `elec_scenario` | `gov_invest` `conservative` | 전력가격 경로 → **e-NCC·전기가열로 비용** |
| `tech_scenario` | `base` `middle` `ideal` | 학습곡선. 미지정이면 `cap_scenario`를 따른다 |
| `cost_multiplier` | 0.1–5.0 | MACC 자본비용 일괄 배율 (논문 민감도 = 0.8/1.0/1.2) |

세 비용 채널은 서로 겹치지 않는다 — 에너지집약도가 있는 기술(H₂-DRI·e-NCC)은
에너지가격 경로를 타고, 나머지는 학습곡선을 탄다. 자본비용 배율은 둘 다에 곱해진다.
따라서 **헤드라인 2기술은 `tech_scenario`에 반응하지 않는다**(설계이며
`tests/test_scenario_levers.py`가 그 경계를 잠근다).

선언되지 않은 키는 조용히 무시된다 — 엑셀 SSOT를 지키기 위해서다. 무엇이 실제로
적용됐는지는 응답의 `meta.model_levers.explicit`에 되돌아온다. 존재하지 않는 값
(`h2_scenario: "nope"`)은 무시하지 않고 오류로 돌려준다.

### 예: 비용이 20% 비싸고 수소가 늦으면 어느 규칙이 살아남나

```
scenario_grid(packages=["A","B"], elec_scenarios=["gov_invest"],
              cost_multipliers=[0.8, 1.0, 1.2])
```

12칸 전부에서 A는 H₂-DRI를 살리고, B는 6칸 중 4칸에서 못 살린다. B는 비용이
**싸질 때도** 실패한다(0.8) — 감축이 늘어 희소성이 사라지고 가격이 문턱 아래로
내려가기 때문이다. 수량규칙이 자기보정하지 못한다는 §7 논증의 직접 증거다.

## 수동 확인

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 mcp/server.py
```

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"solve_package","arguments":{"package_id":"A"}}}' \
  | python3 mcp/server.py
```

## 계약 검증

```bash
python3 -m pytest tests/test_mcp_server.py -q
```

실제 서브프로세스를 띄워 검증한다:

- `initialize` → `tools/list` 순서와 알림(notification) 무응답 처리
- 도구 8종의 스키마 존재 + 시나리오 레버가 스키마에 **열거**돼 있는지
  (설명문에만 적으면 모델이 키를 지어내거나 아예 안 쓴다)
- 레버가 전송 계층을 타고도 실제로 답을 바꾸는지 (조용한 무시 방지)
- `scenario_grid`가 개별 solve와 같은 답을 내는지 + 조합 상한을 지키는지
- **`solve_package` 결과가 엔진 직접 호출과 동일** (전송만 다르고 계산은 하나)
- 도구 오류는 `isError` 결과로 — JSON-RPC error로 던지면 클라이언트가 세션을 끊는다
- 미지 메서드는 `-32601`

## 설계 메모

모형 로직은 `api/solve.py`를 그대로 import해 쓴다. 웹 API(Vercel)와 MCP가 같은 코드
경로를 타므로 두 결과가 갈라질 수 없다. 데이터는 `public/model/kets_data.json`을
프로세스 시작 시 1회 로드한다.

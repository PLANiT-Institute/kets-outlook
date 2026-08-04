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
| `list_packages` | — | 운영규칙 4종(P0/P1/A/B) 메타 · 시나리오 · MSR 프리셋 · λ 기본값 |
| `solve_package` | `package_id`, `macc_mode`, `overrides` | 2026–2040 연도별 가격경로, 기술 활성화 연도, 최대낙폭, 누적흡수량 |
| `solve_custom` | `scenario`, `macc_mode`, `msr`, `liquidity` | 정태·Hotelling·실현가 3층 분해 경로 |
| `list_data_sheets` | — | 데이터 계약 시트 목록 + 행 수 |
| `get_data_sheet` | `name`, `limit` | 시트 실제 행 (cap 경로·MACC 기술상세 등) |
| `list_runs` | — | 저장된 실행 결과 JSON 목록 |
| `get_run` | `name`, `key` | 저장 결과 조회 (`key`로 점 표기 하위 경로) |

`solve_package`의 `overrides` 허용 키: `corridor_target_year`, `corridor_tech2`,
`corridor_target_year2`, `lambda_regime`(`relapse`|`hold`|`consolidate`),
`cap_scenario`(`base`|`middle`|`ideal`). 그 외 키는 무시된다 — 엑셀 SSOT를 지키기
위해서다.

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
- 도구 7종의 스키마 존재
- **`solve_package` 결과가 엔진 직접 호출과 동일** (전송만 다르고 계산은 하나)
- 도구 오류는 `isError` 결과로 — JSON-RPC error로 던지면 클라이언트가 세션을 끊는다
- 미지 메서드는 `-32601`

## 설계 메모

모형 로직은 `api/solve.py`를 그대로 import해 쓴다. 웹 API(Vercel)와 MCP가 같은 코드
경로를 타므로 두 결과가 갈라질 수 없다. 데이터는 `public/model/kets_data.json`을
프로세스 시작 시 1회 로드한다.

"""K-ETS Outlook MCP 서버 — Claude가 K-ETS 가격전망 모형을 직접 돌리게 한다.

전송: stdio · JSON-RPC 2.0 (MCP 명세). 줄 단위 JSON.
의존성: numpy + 표준 라이브러리뿐. `pip install mcp` 불필요 — 프로토콜 표면이
작아서(initialize / tools/list / tools/call / ping) SDK 없이 직접 구현했다.

모형 로직은 `api/solve.py`를 그대로 재사용한다 — 웹 API와 MCP가 같은 코드 경로를
쓰므로 둘의 결과가 갈라질 수 없다.

등록 (Claude Desktop / Claude Code):
    {"mcpServers": {"kets": {"command": "python3",
                             "args": ["<repo>/mcp/server.py"]}}}

수동 확인:
    echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 mcp/server.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from api import solve  # noqa: E402  (엔진 + 데이터 로딩을 웹 API와 공유)

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "kets-outlook", "version": "1.0.0"}
RUNS_DIR = _ROOT / "outputs" / "runs"


# ─── 도구 구현 ────────────────────────────────────────────────

def _list_packages() -> dict:
    """운영규칙(정책패키지) 목록 + 시뮬레이터 기본값."""
    m = solve.meta()
    return {"packages": m["packages"], "scenarios": m["scenarios"],
            "macc_modes": m["macc_modes"], "years": m["years"],
            "liquidity_defaults": m["liquidity_defaults"],
            "msr_presets": m["presets"]}


def _solve_package(package_id: str, overrides: dict | None = None,
                   macc_mode: str = "step") -> dict:
    return solve.run_package({"package_id": package_id, "macc_mode": macc_mode,
                              "overrides": overrides or {}})


def _solve_custom(scenario: str = "base", macc_mode: str = "step",
                  msr: dict | None = None, liquidity: dict | None = None) -> dict:
    return solve.run({"scenario": scenario, "macc_mode": macc_mode,
                      "msr": msr or {}, "liquidity": liquidity or {}})


def _list_data_sheets() -> dict:
    sheets = solve._RAW["sheets"]
    return {"source": solve._RAW.get("_meta", {}).get("source"),
            "sheets": [{"name": k, "rows": len(v)} for k, v in sheets.items()]}


def _get_data_sheet(name: str, limit: int = 200) -> dict:
    sheets = solve._RAW["sheets"]
    if name not in sheets:
        raise ValueError(f"unknown sheet: {name} (available: {list(sheets)})")
    rows = sheets[name]
    return {"name": name, "total_rows": len(rows), "returned": min(limit, len(rows)),
            "rows": rows[:limit]}


def _list_runs() -> dict:
    return {"runs": sorted(p.name for p in RUNS_DIR.glob("*.json"))}


def _get_run(name: str, key: str | None = None) -> dict:
    path = RUNS_DIR / name
    if not path.is_file() or path.suffix != ".json" or path.parent != RUNS_DIR:
        raise ValueError(f"unknown run file: {name} (see list_runs)")
    data = json.loads(path.read_text(encoding="utf-8"))
    if key:
        for part in key.split("."):
            if isinstance(data, list):
                data = data[int(part)]
            else:
                data = data[part]
    return {"file": name, "key": key, "value": data}


TOOLS = [
    {
        "name": "list_packages",
        "description": ("K-MSR 운영규칙 4종(P0 무정책 · P1 시행령초안 · A 가격약속형 · "
                        "B 수량약속형)과 시뮬레이터 기본값·MSR 프리셋을 반환한다. "
                        "다른 도구를 쓰기 전에 먼저 호출해 선택지를 확인하라."),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "solve_package",
        "description": ("운영규칙 하나를 실제 엔진으로 풀어 2026–2040 KAU 가격경로를 낸다. "
                        "반환: 연도별 kau(실현가)·floor(하한)·defended(하한방어 여부)·"
                        "headroom(방어여유)·bank_Mt(이월잔고), 기술활성화 연도, 최대낙폭, 누적흡수량."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "package_id": {"type": "string", "enum": ["P0", "P1", "A", "B"],
                               "description": "운영규칙 ID"},
                "macc_mode": {"type": "string", "enum": ["step", "exponential"],
                              "default": "step",
                              "description": "MACC 함수형태. step=기술 단위 계단형(기본)"},
                "overrides": {
                    "type": "object",
                    "description": ("선택 오버라이드. 허용 키: corridor_target_year(회랑 목표연도), "
                                    "corridor_tech2, corridor_target_year2, "
                                    "lambda_regime(relapse|hold|consolidate), "
                                    "cap_scenario(base|middle|ideal). 그 외 키는 무시된다."),
                },
            },
            "required": ["package_id"],
        },
    },
    {
        "name": "solve_custom",
        "description": ("정책 레버를 직접 지정해 가격경로를 낸다(패키지 밖 임의 시나리오). "
                        "정태(Coase)·Hotelling·실현가를 함께 반환하므로 유동성 전달(λ)의 "
                        "효과를 분해해 볼 수 있다."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "scenario": {"type": "string", "enum": ["base", "middle", "ideal"],
                             "default": "base", "description": "배출허용총량(cap) 경로"},
                "macc_mode": {"type": "string", "enum": ["step", "exponential"], "default": "step"},
                "msr": {
                    "type": "object",
                    "description": ("MSR 레버. rho(흡수비율 0–1), theta_plus_Mt(흡수 발동 상한 임계), "
                                    "theta_minus_Mt(방출 발동 하한 임계), release_Mt(연간 방출량), "
                                    "cancel(흡수분 영구취소 비율 0–1), carve_reserve(예비분 carve-out)."),
                },
                "liquidity": {
                    "type": "object",
                    "description": ("유동성 전달. lam_0(초기 λ, 0=정태·1=완전차익거래), "
                                    "lam_terminal(종착 λ), ramp_years(수렴 연수). "
                                    "2026 관측가 기준 implied λ ≈ 0.55."),
                },
            },
        },
    },
    {
        "name": "list_data_sheets",
        "description": "마스터 엑셀에서 export된 데이터 계약의 시트 목록과 행 수. 모든 모형 입력의 출처.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_data_sheet",
        "description": "데이터 시트 하나의 실제 행을 반환한다(cap 경로·MACC 기술상세·무상할당비율 등).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "시트명 (list_data_sheets 참조)"},
                "limit": {"type": "integer", "default": 200, "description": "반환 최대 행 수"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "list_runs",
        "description": "저장된 모형 실행 결과 JSON 목록(재계산 없이 조회 가능한 확정 산출물).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_run",
        "description": ("저장된 실행 결과를 읽는다. key로 점 표기 경로를 주면 해당 하위만 반환"
                        "(예: '40k_7pct.summary'). 전체 파일은 크므로 key 사용을 권장."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "파일명 (list_runs 참조)"},
                "key": {"type": "string", "description": "점 표기 하위 경로 (선택)"},
            },
            "required": ["name"],
        },
    },
]

HANDLERS = {
    "list_packages": _list_packages,
    "solve_package": _solve_package,
    "solve_custom": _solve_custom,
    "list_data_sheets": _list_data_sheets,
    "get_data_sheet": _get_data_sheet,
    "list_runs": _list_runs,
    "get_run": _get_run,
}


# ─── JSON-RPC 루프 ────────────────────────────────────────────

def _call_tool(params: dict) -> dict:
    name = params.get("name")
    fn = HANDLERS.get(name)
    if fn is None:
        raise ValueError(f"unknown tool: {name}")
    try:
        result = fn(**(params.get("arguments") or {}))
        text = json.dumps(result, ensure_ascii=False, indent=1)
        return {"content": [{"type": "text", "text": text}]}
    except Exception as e:  # 도구 오류는 프로토콜 오류가 아니라 결과로 돌려준다(MCP 규약)
        return {"content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}],
                "isError": True}


def dispatch(req: dict):
    """요청 → 결과. 알림(id 없음)이면 None을 돌려 응답을 생략한다."""
    method = req.get("method")
    if method == "initialize":
        return {"protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        return _call_tool(req.get("params") or {})
    if method == "ping":
        return {}
    if method.startswith("notifications/"):
        return None
    raise LookupError(f"method not found: {method}")


def main() -> None:
    out = sys.stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue                      # 파싱 불가 프레임은 무시(응답할 id가 없다)
        req_id = req.get("id")
        try:
            result = dispatch(req)
        except LookupError as e:
            resp = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": str(e)}}
        except Exception as e:  # noqa: BLE001
            resp = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": str(e)}}
        else:
            if req_id is None:            # 알림 — 응답 금지
                continue
            resp = {"jsonrpc": "2.0", "id": req_id, "result": result}
        out.write(json.dumps(resp, ensure_ascii=False) + "\n")
        out.flush()


if __name__ == "__main__":
    main()

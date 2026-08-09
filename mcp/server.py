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
    """운영규칙(정책패키지) 목록 + 시뮬레이터 기본값 + 시나리오 레버 선택지."""
    m = solve.meta()
    return {"packages": m["packages"], "scenarios": m["scenarios"],
            "macc_modes": m["macc_modes"], "years": m["years"],
            "liquidity_defaults": m["liquidity_defaults"],
            "msr_presets": m["presets"],
            "model_levers": m["model_levers"]}


def _solve_package(package_id: str, overrides: dict | None = None,
                   macc_mode: str = "step") -> dict:
    return solve.run_package({"package_id": package_id, "macc_mode": macc_mode,
                              "overrides": overrides or {}})


def _solve_custom(scenario: str = "base", macc_mode: str = "step",
                  msr: dict | None = None, liquidity: dict | None = None,
                  overrides: dict | None = None) -> dict:
    return solve.run({"scenario": scenario, "macc_mode": macc_mode,
                      "msr": msr or {}, "liquidity": liquidity or {},
                      "overrides": overrides or {}})


# 시나리오 레버 스키마 — 두 solve 도구가 공유한다.
# 값 목록은 시트에서 읽어 채운다(코드에 박지 않는다 — 엑셀이 SSOT).
def _lever_schema(extra: dict) -> dict:
    lv = solve.meta()["model_levers"]
    props = {
        "h2_scenario": {"type": "string", "enum": lv["h2_scenario"]["values"],
                        "description": "수소 도입가격 경로. H₂-DRI 비용을 구동한다."},
        "elec_scenario": {"type": "string", "enum": lv["elec_scenario"]["values"],
                          "description": "전력가격 경로. e-NCC·전기가열로 비용을 구동한다."},
        "tech_scenario": {"type": "string", "enum": lv["tech_scenario"]["values"],
                          "description": ("감축기술 학습곡선. 미지정이면 cap 시나리오를 따른다. "
                                          "에너지집약도가 없는 기술에만 작용한다.")},
        "cost_multiplier": {"type": "number", "minimum": 0.1, "maximum": 5.0,
                            "description": "MACC 자본비용 일괄 배율. 논문 민감도는 0.8/1.0/1.2."},
    }
    props.update(extra)
    return {"type": "object", "properties": props, "additionalProperties": False,
            "description": "선언되지 않은 키는 무시된다 — 엑셀 SSOT를 보호하기 위해서다."}


_PKG_OVERRIDES = _lever_schema({
    "cap_scenario": {"type": "string", "enum": ["base", "middle", "ideal"],
                     "description": "배출허용총량(cap) 경로"},
    "lambda_regime": {"type": "string", "enum": ["relapse", "hold", "consolidate"],
                      "description": "유동성 전달 λ의 향후 레짐"},
    "corridor_target_year": {"type": "integer",
                             "description": "회랑이 1순위 기술 문턱에 닿아야 하는 연도"},
    "corridor_tech2": {"type": "string", "description": "2순위 추종 기술명"},
    "corridor_target_year2": {"type": "integer", "description": "2순위 기술 목표연도"},
})

_CUSTOM_OVERRIDES = _lever_schema({})


_GRID_MAX = 64      # 조합 상한 — 한 호출이 수십 초를 넘지 않게 한다


def _scenario_grid(packages: list | None = None, h2_scenarios: list | None = None,
                   elec_scenarios: list | None = None, tech_scenarios: list | None = None,
                   cost_multipliers: list | None = None, macc_mode: str = "step") -> dict:
    """레버 조합의 데카르트 곱을 전부 풀어 한 표로 돌려준다.

    한 시나리오씩 물어보는 대신 "수소가 늦고 전력이 안 떨어지고 비용이 20% 높으면
    어느 운영규칙이 살아남나"를 한 번에 본다. 시나리오 분석의 기본 단위다.
    """
    import itertools

    lv = solve.meta()["model_levers"]
    grid = {
        "package_id": packages or ["P0", "P1", "A", "B"],
        "h2_scenario": h2_scenarios or lv["h2_scenario"]["values"],
        "elec_scenario": elec_scenarios or lv["elec_scenario"]["values"],
        "tech_scenario": tech_scenarios or [None],
        "cost_multiplier": cost_multipliers or [1.0],
    }
    combos = list(itertools.product(*grid.values()))
    if len(combos) > _GRID_MAX:
        raise ValueError(f"{len(combos)} 조합은 상한 {_GRID_MAX}을 넘는다 — "
                         f"레버 목록을 좁혀라. 축 크기: "
                         f"{ {k: len(v) for k, v in grid.items()} }")

    rows = []
    for pid, h2, elec, tech, mult in combos:
        overrides = {"h2_scenario": h2, "elec_scenario": elec, "cost_multiplier": mult}
        if tech is not None:
            overrides["tech_scenario"] = tech
        r = solve.run_package({"package_id": pid, "macc_mode": macc_mode,
                               "overrides": overrides})
        acts = r["activation_headline"]
        rows.append({
            "package_id": pid, "h2_scenario": h2, "elec_scenario": elec,
            "tech_scenario": tech or r["meta"]["model_levers"]["tech_scenario"],
            "cost_multiplier": mult,
            "kau_2040": r["path"][-1]["kau"],
            "activation": acts,
            "all_headline_techs_activate": all(v is not None for v in acts.values()),
            "defended_all": r["defended_all"],
            "max_drawdown": r["max_drawdown"],
        })
    return {"axes": {k: list(v) for k, v in grid.items()},
            "n_runs": len(rows), "rows": rows}


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
                        "B 수량약속형)과 시뮬레이터 기본값·MSR 프리셋·시나리오 레버 "
                        "선택지를 반환한다. 다른 도구를 쓰기 전에 먼저 호출해 선택지를 확인하라."),
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
                "overrides": _PKG_OVERRIDES,
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
                                    "2026 관측가 기준 implied λ ≈ 0.575."),
                },
                "overrides": _CUSTOM_OVERRIDES,
            },
        },
    },
    {
        "name": "scenario_grid",
        "description": ("레버 조합을 전부 풀어 한 표로 비교한다. 축을 비워두면 기본 전체 "
                        "(운영규칙 4종 × 수소 2종 × 전력 2종). 각 행은 2040 KAU·헤드라인 "
                        "기술 활성화 연도·하한 방어 여부·최대낙폭을 담는다. "
                        f"조합 상한 {_GRID_MAX}개."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "packages": {"type": "array", "items": {"type": "string",
                                                        "enum": ["P0", "P1", "A", "B"]},
                             "description": "비교할 운영규칙 (기본 전체)"},
                "h2_scenarios": {"type": "array", "items": {"type": "string"},
                                 "description": "수소가격 경로 (기본 전체)"},
                "elec_scenarios": {"type": "array", "items": {"type": "string"},
                                   "description": "전력가격 경로 (기본 전체)"},
                "tech_scenarios": {"type": "array", "items": {"type": "string"},
                                   "description": "학습곡선 (기본: cap 시나리오 추종)"},
                "cost_multipliers": {"type": "array", "items": {"type": "number"},
                                     "description": "자본비용 배율 (기본 [1.0]. 민감도 예: [0.8,1.0,1.2])"},
                "macc_mode": {"type": "string", "enum": ["step", "exponential"],
                              "default": "step"},
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
    "scenario_grid": _scenario_grid,
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

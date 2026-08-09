"""MCP 서버 계약 검증 — 실제 stdio 서브프로세스로 핸드셰이크를 돈다.

프로토콜 표면(initialize / tools/list / tools/call / 알림 무응답 / 미지 메서드)이
깨지면 Claude가 서버를 붙이지 못한다. 서버 함수를 직접 부르지 않고 프로세스를
띄우는 이유가 이것 — 프레이밍·flush·알림 처리까지 함께 검증한다.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "mcp" / "server.py"


def _rpc(*requests: dict) -> list[dict]:
    """요청들을 stdio로 보내고 응답 줄들을 파싱해 돌려준다."""
    payload = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in requests)
    proc = subprocess.run([sys.executable, str(SERVER)], input=payload,
                          capture_output=True, text=True, timeout=180, cwd=ROOT)
    assert proc.returncode == 0, proc.stderr
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]


def test_initialize_and_tools_list():
    out = _rpc(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},   # 알림 → 응답 없어야 함
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    )
    assert [r["id"] for r in out] == [1, 2], "알림에 응답하면 클라이언트가 프로토콜 위반으로 끊는다"

    init = out[0]["result"]
    assert init["protocolVersion"]
    assert "tools" in init["capabilities"]

    names = {t["name"] for t in out[1]["result"]["tools"]}
    assert names == {"list_packages", "solve_package", "solve_custom", "scenario_grid",
                     "list_data_sheets", "get_data_sheet", "list_runs", "get_run"}
    for tool in out[1]["result"]["tools"]:
        assert tool["description"] and tool["inputSchema"]["type"] == "object"


def test_solve_package_matches_engine():
    """MCP 경로 결과가 엔진 직접 호출과 같아야 한다 — 전송만 다르고 계산은 하나."""
    out = _rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "solve_package", "arguments": {"package_id": "P0"}}})
    payload = json.loads(out[0]["result"]["content"][0]["text"])
    path = {row["year"]: row["kau"] for row in payload["path"]}

    sys.path.insert(0, str(ROOT))
    from kets.engine import KETSModel
    model = KETSModel.from_json(ROOT / "public" / "model" / "kets_data.json")
    pkg = next(p for p in model.packages if p["package_id"] == "P0")
    direct = {r["year"]: round(r["kau"], 3) for r in model.solve_package(pkg)}

    assert path == direct


def test_scenario_levers_are_declared_in_tool_schema():
    """레버가 스키마에 열거돼야 클라이언트(Claude)가 존재를 안다.

    설명문에만 적어두면 모델이 키를 지어내거나 아예 안 쓴다.
    """
    out = _rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    tools = {t["name"]: t for t in out[0]["result"]["tools"]}
    for name in ("solve_package", "solve_custom"):
        props = tools[name]["inputSchema"]["properties"]["overrides"]["properties"]
        assert {"h2_scenario", "elec_scenario", "tech_scenario",
                "cost_multiplier"} <= set(props), name
        assert props["h2_scenario"]["enum"] == ["gov", "conservative"], name


def test_scenario_lever_changes_the_answer_over_mcp():
    """전송 계층까지 태운 레버가 실제로 결과를 바꾼다 — 조용히 무시되지 않는다."""
    def activation(overrides):
        out = _rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": "solve_package",
                               "arguments": {"package_id": "B", "overrides": overrides}}})
        payload = json.loads(out[0]["result"]["content"][0]["text"])
        return payload["activation_headline"]["수소환원제철 (H₂-DRI-EAF)"]

    assert activation({}) == 2035
    assert activation({"h2_scenario": "conservative"}) is None


def test_scenario_grid_spans_the_axes_and_agrees_with_single_solves():
    """격자의 각 칸이 개별 solve와 같은 답을 낸다 — 격자가 지름길로 근사하지 않는다."""
    out = _rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "scenario_grid",
                           "arguments": {"packages": ["A", "B"],
                                         "h2_scenarios": ["gov", "conservative"],
                                         "elec_scenarios": ["gov_invest"]}}})
    grid = json.loads(out[0]["result"]["content"][0]["text"])
    assert grid["n_runs"] == 4
    cell = next(r for r in grid["rows"]
                if r["package_id"] == "B" and r["h2_scenario"] == "conservative")
    assert cell["activation"]["수소환원제철 (H₂-DRI-EAF)"] is None
    assert cell["all_headline_techs_activate"] is False


def test_scenario_grid_refuses_to_explode():
    """상한 없는 데카르트 곱은 클라이언트 타임아웃으로 나타난다 — 미리 거절한다."""
    out = _rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "scenario_grid",
                           "arguments": {"tech_scenarios": ["base", "middle", "ideal"],
                                         "cost_multipliers": [0.8, 0.9, 1.0, 1.1, 1.2]}}})
    assert out[0]["result"]["isError"] is True


def test_tool_error_is_result_not_protocol_error():
    """도구 오류는 isError 결과로 — JSON-RPC error로 던지면 클라이언트가 세션을 죽인다."""
    out = _rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "get_data_sheet", "arguments": {"name": "no_such_sheet"}}})
    assert "error" not in out[0]
    assert out[0]["result"]["isError"] is True


def test_unknown_method_returns_jsonrpc_error():
    out = _rpc({"jsonrpc": "2.0", "id": 9, "method": "does/not/exist"})
    assert out[0]["error"]["code"] == -32601

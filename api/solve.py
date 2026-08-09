"""Vercel Python Serverless Function — POST /api/solve.

슬라이더 정책 레버 → 실제 K-ETS 엔진(kets/engine.py) 라이브 구동 →
정태·Hotelling·실현(레벨-브리지) 가격경로 반환. 데이터는 빌드타임 export된
kets_data.json에서 로드(하드코딩 없음). 의존성은 numpy + stdlib뿐.

두 가지 POST 계약(하위호환):
  1. 커스텀 레버(기존): {"scenario", "macc_mode", "msr": {...}, "liquidity": {...}}
     → level_bridge_path
  2. 정책패키지(v4):   {"package_id": "P0"|"P1"|"A"|"B",
                        "overrides": {"corridor_target_year": 2033, ...}(선택)}
     → engine.solve_package (정책패키지 시트 운영규칙) + 헤드라인 기술 활성화 연도

로컬 테스트:  python api/solve.py  → http://localhost:8531
  curl -s localhost:8531/api/solve -X POST -d '{"scenario":"base"}' | python -m json.tool
  curl -s localhost:8531/api/solve -X POST -d '{"package_id":"A"}' | python -m json.tool

Vercel: `api/solve.py`의 `handler`를 @vercel/python 런타임이 자동 인식.
"""

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# import 경로: 로컬은 kets/ 패키지, Vercel 번들은 vendored api/_engine
# (Vercel은 함수 파일과 그 하위만 번들에 넣으므로 kets/가 없다 — scripts/sync_engine.py 참조)
_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[1]           # 리포 루트
sys.path.insert(0, str(_ROOT))
try:
    from kets.engine import KETSModel          # 로컬 개발 경로
except ImportError:
    from api._engine.engine import KETSModel   # Vercel vendored 경로

_DATA = _ROOT / "public" / "model" / "kets_data.json"

# 콜드스타트 1회: 원시 데이터 로드 (웜 인보케이션 재사용)
with open(_DATA, encoding="utf-8") as _f:
    _RAW = json.load(_f)


# ─── 정책패키지 (v4 운영규칙) ───────────────────────────────

# 패키지 오버라이드로 허용하는 키 (그 외는 무시 — 시트 SSOT 보호)
_PKG_OVERRIDE_KEYS = {"corridor_target_year", "corridor_tech2", "corridor_target_year2",
                      "lambda_regime", "cap_scenario"}

# 모형 생성 시점에 적용되는 레버 — 비용·에너지가격 세계를 바꾼다.
# 패키지 레버(위)가 "정부가 무엇을 약속하는가"라면, 이쪽은 "어떤 세계에서 그러는가"다.
#   h2_scenario   수소가격시나리오 시트의 scenario_id  (gov | conservative)
#   elec_scenario 전력가격시나리오 시트의 scenario_id  (gov_invest | conservative)
#   tech_scenario 학습곡선 시트의 scenario_id         (base | middle | ideal)
#                 미지정이면 cap 시나리오를 따른다(기존 동작).
#   cost_multiplier  MACC기술상세 자본비용 일괄 배율 (1.0 = 시트값)
_MODEL_LEVER_KEYS = {"h2_scenario", "elec_scenario", "tech_scenario", "cost_multiplier"}


def _scenario_ids(sheet: str) -> list[str]:
    """시트에 실제로 존재하는 scenario_id (하드코딩 금지 — 데이터가 목록의 출처)."""
    seen = []
    for r in _RAW["sheets"].get(sheet, []):
        sid = r.get("scenario_id")
        if isinstance(sid, str) and sid not in seen:
            seen.append(sid)
    return seen


def _build_model(body: dict, macc_mode: str) -> tuple[KETSModel, dict]:
    """모형 레버를 model_params에 얹어 엔진을 만든다. 반환: (모형, 적용된 레버)."""
    levers = {k: v for k, v in (body.get("overrides") or {}).items()
              if k in _MODEL_LEVER_KEYS}
    levers.update({k: v for k, v in body.items() if k in _MODEL_LEVER_KEYS})
    if not levers:
        return KETSModel(_RAW, macc_mode=macc_mode), {}

    for key, sheet in (("h2_scenario", "수소가격시나리오"),
                       ("elec_scenario", "전력가격시나리오"),
                       ("tech_scenario", "학습곡선")):
        if key in levers:
            allowed = _scenario_ids(sheet)
            if str(levers[key]) not in allowed:
                raise ValueError(f"unknown {key}: {levers[key]} (available: {allowed})")
    if "cost_multiplier" in levers:
        mult = float(levers["cost_multiplier"])
        if not 0.1 <= mult <= 5.0:
            raise ValueError(f"cost_multiplier out of range: {mult} (expected 0.1–5.0)")
        levers["cost_multiplier"] = mult

    data = {**_RAW, "model_params": {**_RAW["model_params"], **levers}}
    return KETSModel(data, macc_mode=macc_mode), levers

# 패키지 경로 응답 필드 (solve_package 레코드에서 추출)
_PKG_PATH_FIELDS = ("year", "kau", "kau_prefloor", "floor", "defended", "headroom",
                    "static", "hotelling", "lambda", "intake_Mt", "release_Mt", "bank_Mt")


def _package_headline(pkg: dict) -> dict:
    """GET meta·POST 응답 공용 패키지 헤드라인 메타."""
    return {"id": pkg.get("package_id"),
            "name_en": pkg.get("name_en"), "name_kr": pkg.get("name_kr"),
            "msr_level": pkg.get("msr_level"), "floor_id": pkg.get("floor_id"),
            "auction_lever": pkg.get("auction_lever"),
            "cap_scenario": pkg.get("cap_scenario"),
            "lambda_regime": pkg.get("lambda_regime"),
            "corridor_target_year": pkg.get("corridor_target_year")}


def _max_drawdown(prices: list[float]) -> float:
    """가격경로 최대 낙폭(peak-to-trough 비율) — 수량규칙 급등·붕락 위험 지표."""
    peak, dd = prices[0], 0.0
    for p in prices:
        peak = max(peak, p)
        if peak > 0:
            dd = max(dd, (peak - p) / peak)
    return dd


def run_package(body: dict) -> dict:
    """{"package_id": ...} → 정책패키지 시트 운영규칙으로 solve_package 실행."""
    pid = str(body["package_id"])
    macc_mode = body.get("macc_mode", "step")
    model, levers = _build_model(body, macc_mode)
    pkg = next((p for p in model.packages if p.get("package_id") == pid), None)
    if pkg is None:
        ids = [p.get("package_id") for p in model.packages]
        raise ValueError(f"unknown package_id: {pid} (available: {ids})")

    overrides = body.get("overrides") or {}
    applied = {k: v for k, v in overrides.items() if k in _PKG_OVERRIDE_KEYS}
    pkg = {**pkg, **applied}

    path = model.solve_package(pkg)
    prices = [r["kau"] for r in path]
    activation = model.tech_activation_years(prices, pkg["cap_scenario"], headline_only=True)
    rows = [{k: (round(r[k], 3) if isinstance(r[k], float) else r[k])
             for k in _PKG_PATH_FIELDS} for r in path]
    return {
        "meta": {
            "package": _package_headline(pkg),
            "overrides_applied": applied,
            "model_levers": {"h2_scenario": model.h2_scenario,
                             "elec_scenario": model.elec_scenario,
                             "tech_scenario": model.tech_scenario or pkg["cap_scenario"],
                             "cost_multiplier": model.cost_multiplier,
                             "explicit": levers},
            "macc_mode": macc_mode,
            "years": model.years,
        },
        "activation_headline": activation,
        "defended_all": all(r["defended"] for r in path),
        "min_headroom": round(min(r["headroom"] for r in path), 3),
        "max_drawdown": round(_max_drawdown(prices), 3),
        "cum_intake_Mt": round(sum(r["intake_Mt"] for r in path), 1),
        "path": rows,
    }


def run(body: dict) -> dict:
    """요청 body → 레벨-브리지 경로. 기저 데이터는 _RAW 고정, 레버만 변동."""
    if body.get("package_id"):
        return run_package(body)
    scenario = body.get("scenario", "base")
    macc_mode = body.get("macc_mode", "step")
    model, levers = _build_model(body, macc_mode)

    presets = model.msr_presets()
    m = body.get("msr") or {}
    base = presets.get("L0")
    msr = {
        "id": "custom", "name": "custom",
        "rho": float(m.get("rho", base["rho"])),
        "theta_plus": float(m.get("theta_plus_Mt", base["theta_plus"] / 1e6)) * 1e6,
        "theta_minus": float(m.get("theta_minus_Mt", base["theta_minus"] / 1e6)) * 1e6,
        "release": float(m.get("release_Mt", base["release"] / 1e6)) * 1e6,
        "cancel": float(m.get("cancel", base["cancel"])),
    }
    # 예비분 carve-out: MSR이 실질 작동하면 기본 적용 (명시 오버라이드 가능).
    # v0.8 회계 — 4차 cap은 예비분 포함이므로 carve 없인 방출이 이중계상.
    if "carve_reserve" in m:
        msr["carve_reserve"] = bool(m["carve_reserve"])
    else:
        msr["carve_reserve"] = bool(msr["rho"] > 0 or msr["release"] > 0)
    liq = body.get("liquidity") or {}
    lam_0 = float(liq.get("lam_0", 0.0))
    lam_terminal = liq.get("lam_terminal")
    lam_terminal = float(lam_terminal) if lam_terminal is not None else None
    ramp_years = float(liq.get("ramp_years", 0.0))

    path = model.level_bridge_path(scenario, msr, lam_0=lam_0,
                                   lam_terminal=lam_terminal, ramp_years=ramp_years)
    return {
        "meta": {
            "scenario": scenario, "macc_mode": macc_mode,
            "model_levers": {"h2_scenario": model.h2_scenario,
                             "elec_scenario": model.elec_scenario,
                             "tech_scenario": model.tech_scenario or scenario,
                             "cost_multiplier": model.cost_multiplier,
                             "explicit": levers},
            "years": model.years,
            "eua": {str(y): model.eua[y] for y in model.years},
            "presets": {k: {"name": v["name"], "rho": v["rho"],
                            "theta_plus_Mt": v["theta_plus"] / 1e6,
                            "theta_minus_Mt": v["theta_minus"] / 1e6,
                            "release_Mt": v["release"] / 1e6, "cancel": v["cancel"]}
                        for k, v in presets.items()},
        },
        "path": [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in row.items()}
                 for row in path],
    }


def meta() -> dict:
    """GET — 프런트 UI 초기화용 시나리오·프리셋·연도."""
    model = KETSModel(_RAW)
    presets = model.msr_presets()
    return {
        "scenarios": ["base", "middle", "ideal"],
        "macc_modes": ["step", "exponential"],
        "years": model.years,
        "packages": [_package_headline(p) for p in model.packages],
        # 시나리오 레버 — 값은 시트에서 읽는다(코드에 목록을 박지 않는다).
        "model_levers": {
            "h2_scenario": {"values": _scenario_ids("수소가격시나리오"),
                            "default": model.h2_scenario,
                            "desc": "수소 도입가격 경로 (H₂-DRI 비용을 구동)"},
            "elec_scenario": {"values": _scenario_ids("전력가격시나리오"),
                              "default": model.elec_scenario,
                              "desc": "전력가격 경로 (e-NCC·전기가열로 비용을 구동)"},
            "tech_scenario": {"values": _scenario_ids("학습곡선"),
                              "default": None,
                              "desc": "감축기술 학습곡선. 미지정이면 cap 시나리오를 따른다"},
            "cost_multiplier": {"range": [0.1, 5.0], "default": 1.0,
                                "desc": "MACC 자본비용 일괄 배율 (논문 민감도 = 0.8/1.0/1.2)"},
        },
        "liquidity_defaults": _RAW.get("liquidity_defaults", {}),
        "presets": {k: {"name": v["name"], "rho": v["rho"],
                        "theta_plus_Mt": v["theta_plus"] / 1e6,
                        "theta_minus_Mt": v["theta_minus"] / 1e6,
                        "release_Mt": v["release"] / 1e6, "cancel": v["cancel"]}
                    for k, v in presets.items()},
    }


class handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        try:
            self._send(200, meta())
        except Exception as e:  # noqa: BLE001
            self._send(500, {"error": str(e)})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            self._send(200, run(body))
        except Exception as e:  # noqa: BLE001
            self._send(500, {"error": str(e)})


if __name__ == "__main__":
    from http.server import HTTPServer
    port = 8531
    print(f"local: http://localhost:{port}  (GET /api/solve, POST /api/solve)")
    HTTPServer(("", port), handler).serve_forever()

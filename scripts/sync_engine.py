"""엔진을 api/_engine/으로 vendoring — Vercel 서버리스 함수 배포용.

kets/{engine,hotelling,liquidity,policy_grid}.py를 복사하되 import 경로를
vendored 경로로 재작성한다. 산출 파일은 GENERATED 헤더를 달아 직접 수정을 막는다.

이유: @vercel/python은 함수 파일과 그 하위 디렉터리만 번들에 넣는다. 리포 루트의
`kets/` 패키지는 번들에 포함되지 않으므로 함수 옆(api/_engine/)에 복사해 둔다.
런타임 의존성은 numpy 하나 — requirements.txt(루트)가 그 계약이다.
개발용 pandas·openpyxl·matplotlib는 requirements-dev.txt로 분리해 함수 번들
크기(250MB 한도)를 건드리지 않는다.

사용: python3 scripts/sync_engine.py   (export_web_data.py와 함께 빌드타임 실행)
"""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "kets"
DST = PROJECT_ROOT / "api" / "_engine"
FILES = ["engine.py", "hotelling.py", "liquidity.py", "policy_grid.py"]

HEADER = ("# GENERATED — DO NOT EDIT. 원본: kets/{name} "
          "(scripts/sync_engine.py가 재생성)\n")

DST.mkdir(parents=True, exist_ok=True)
(DST / "__init__.py").write_text("", encoding="utf-8")

for name in FILES:
    text = (SRC / name).read_text(encoding="utf-8")
    # 절대 import → vendored 경로
    text = re.sub(r"from kets\.(\w+) import", r"from api._engine.\1 import", text)
    # excel/config lazy import(effective_rate·from_excel 내부)는 프로덕션 경로에서
    # 호출되지 않으므로 그대로 둔다 — 호출 시 ImportError가 곧 명확한 신호.
    out = HEADER.format(name=name) + text
    (DST / name).write_text(out, encoding="utf-8")
    print(f"vendored: api/_engine/{name} ({len(out)//1024} KB)")

# 검증: vendored 엔진 단독 import + JSON solve smoke test
sys.path.insert(0, str(PROJECT_ROOT))
sys.modules.pop("api", None)
from api._engine.engine import KETSModel  # noqa: E402

m = KETSModel.from_json(PROJECT_ROOT / "public" / "model" / "kets_data.json")
p = m.level_bridge_path("base", m.msr_presets()["L0"], lam_0=0.0)
print(f"smoke: 2026 static={p[0]['static']:.0f} hotelling={p[0]['hotelling']:.0f} → OK")

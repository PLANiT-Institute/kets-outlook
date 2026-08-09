"""원고에 인쇄된 숫자가 엔진 산출물로 되돌아가는지 대조한다.

논문은 이 저장소 밖(비공개)에 있으므로 테스트로 잠글 수 없다. 대신 경로를 받아
검사한다. 판정은 **인쇄 정밀도 기준**이다 — 원고의 `92.140`은 산출물의
92.140327이 반올림된 값이므로 추적됨으로 본다.

    python3 scripts/audit_paper_numbers.py --paper /경로/K-MSR_paper_CCE_revised.md

게이트가 아니라 감사 보조다. UNTRACED가 곧 오류는 아니다 — 인용된 문헌 수치,
제도 상수, 산문에서 계산한 비율이 여기 섞인다. 사람이 훑어보라고 만든 목록이다.
종료코드는 항상 0이며, `--strict`를 주면 UNTRACED가 하나라도 있을 때 1을 낸다.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "outputs" / "runs"
CSVS = ROOT / "outputs" / "csv"

# 숫자 토큰: 1,234.56 / 0.1676 / 40,000 / 7 — 부호는 문맥이 삼키므로 절댓값으로 본다
NUM = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(?![\w])")

# URL·DOI 구간 — 안의 숫자는 수치 주장이 아니다
URL = re.compile(r"https?://\S+|\bdoi\.org/\S+|\b10\.\d{4,}/\S+")

# 명백한 비수치 문맥 — 연도·절번호·식번호·DOI·쪽수
SKIP_CONTEXT = re.compile(
    r"(19|20)\d{2}|Equation|Eq\.|Figure|Table|Section|§|doi|pp?\.|ISSN|vol\.",
    re.IGNORECASE)


def collect_output_values() -> set[float]:
    """outputs/ 아래 모든 수치 잎(leaf)을 모은다 — 원고가 인용할 수 있는 값의 전체 집합."""
    values: set[float] = set()

    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, bool):
            pass
        elif isinstance(node, (int, float)):
            values.add(float(node))

    for path in sorted(RUNS.glob("*.json")):
        walk(json.loads(path.read_text(encoding="utf-8")))
    for path in sorted(CSVS.glob("*.csv")):
        with path.open(encoding="utf-8") as f:
            for row in csv.reader(f):
                for cell in row:
                    try:
                        values.add(float(cell.replace(",", "")))
                    except ValueError:
                        pass
    return values


def traces(printed: float, decimals: int, pool: set[float]) -> bool:
    """인쇄 정밀도로 반올림하면 일치하는 산출값이 있는가.

    반올림 오차 상한은 마지막 자리의 절반. 단위 표기 차이도 함께 본다:
      ×1/100  백분율 (7% → 0.07)
      ×1e6    Mt로 인쇄, 산출은 tCO2 (212.4 Mt → 212,400,000 t)
      ×1e-6   그 반대
    허용오차도 같은 배율로 스케일해야 정밀도가 유지된다.
    """
    tol = 0.5 * 10 ** (-decimals)
    for scale in (1.0, 0.01, 1e6, 1e-6):
        candidate, ctol = printed * scale, tol * scale
        for v in pool:
            if abs(v - candidate) <= ctol + 1e-12:
                return True
    return False


def audit(paper: Path, pool: set[float], min_value: float) -> list[tuple[str, str]]:
    """반환: (숫자, 문맥) 목록 — 산출물로 추적되지 않은 것만."""
    text = paper.read_text(encoding="utf-8")
    untraced, seen = [], set()
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith(("|---", "```")):
            continue
        # URL·DOI 안의 숫자는 수치 주장이 아니다 (10.1016/… , ?lsJoLnkSeq=900328309)
        spans = [(m.start(), m.end()) for m in URL.finditer(line)]
        for m in NUM.finditer(line):
            if any(a <= m.start() < b for a, b in spans):
                continue
            whole, frac = m.group(1).replace(",", ""), m.group(2)
            printed = float(f"{whole}.{frac}") if frac else float(whole)
            decimals = len(frac) if frac else 0
            if printed < min_value and decimals == 0:
                continue                       # 한두 자리 정수는 문장 번호·개수
            token = m.group(0)
            context = line[max(0, m.start() - 60):m.end() + 60].strip()
            if SKIP_CONTEXT.search(context) and decimals == 0:
                continue
            if traces(printed, decimals, pool):
                continue
            key = (token, context[:40])
            if key in seen:
                continue
            seen.add(key)
            untraced.append((token, context))
    return untraced


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--paper", required=True, type=Path, help="원고 마크다운 경로")
    ap.add_argument("--min-value", type=float, default=100.0,
                    help="이 값 미만의 정수는 건너뛴다 (기본 100)")
    ap.add_argument("--strict", action="store_true",
                    help="UNTRACED가 있으면 종료코드 1")
    args = ap.parse_args()

    if not args.paper.is_file():
        print(f"원고를 찾을 수 없다: {args.paper}", file=sys.stderr)
        return 2

    pool = collect_output_values()
    untraced = audit(args.paper, pool, args.min_value)

    print(f"원고   : {args.paper}")
    print(f"대조군 : outputs/runs {len(list(RUNS.glob('*.json')))}개 · "
          f"outputs/csv {len(list(CSVS.glob('*.csv')))}개 → 수치 {len(pool):,}개")
    print(f"미추적 : {len(untraced)}건\n")
    for token, context in untraced:
        print(f"  {token:>12s}  …{context}…")
    if untraced:
        print("\n미추적이 곧 오류는 아니다 — 인용 문헌 수치·제도 상수·산문 계산이 섞인다.")
        print("모형이 낸 수치인데 여기 뜬다면, 산출물에 남지 않는 경로로 인쇄된 것이다.")
    return 1 if (args.strict and untraced) else 0


if __name__ == "__main__":
    raise SystemExit(main())

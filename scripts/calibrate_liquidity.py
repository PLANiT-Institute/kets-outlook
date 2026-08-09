"""유동성 모수(λ, ψ) 실증 캘리브레이션 — 1차 추정.

원칙(피드백): 가정값 금지, 실제 데이터·출처 명시. 데이터가 없는 부분은 명시.

방법 1 — λ '가격 웨지'로 직접 추정 (주 방법, 관측가격 기반):
    관측 KAU가 정태(λ=0, 차익거래 없음)와 Hotelling(λ=1, 완전차익거래) 사이
    어디에 있는지로 λ를 역산한다:
        λ_implied = (P_obs − P_static) / (P_Hotelling − P_static)
    P_static·P_Hotelling은 엔진(스텝 MACC)이 산출.

방법 1b — H1-2026 리프라이싱 λ (현행 모형이 실제 쓰는 값):
    4차 계획기간 개시·MSR 법제화로 KAU가 2026 상반기에 급등했다. 같은 웨지 식을
    2026 관측가에 적용하면 λ₂₀₂₆가 나오며, 이 값이 유동성모수 시트의
    `lambda_2026_implied`(엔진 lambda_regime_path의 앵커)와 일치해야 한다.
    불일치하면 시트가 stale이라는 뜻이므로 이 스크립트가 실패한다.

방법 2 — λ 회전율 교차검증 (보조):
    turnover = 연간 거래량 / 유통물량(전년 carryover).  거래량은 3개 연도만 존재.

ψ — 이월제한 선행연구 2편에서 범위 (연간데이터로 재추정 불가 → 발표결과 인용).
    2026-08-09 KCI 서지 대조 완료 — 두 편 모두 제1저자는 유종민(Jongmin Yu)이다:
    Yu & Lee (2020, 한국기후변화학회지 11(3):177–186, 이벤트스터디):
        2019-06 이월제한 발표 직후 KAU18 일시 하락 후 추세 복귀 → ψ ≈ 0
    Yu & Lee (2023, 자원환경경제연구 32(3):149–166, 동태 비선형최적화):
        규제기간 중 매물출하 효과로 가격 하락 → ψ < 0
    → ψ ∈ [−0.5, 0]. 점추정은 두 논문의 원자료로 프런티어 재추정 필요(미착수).

실행:  python scripts/calibrate_liquidity.py
"""

import csv
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from kets.engine import KETSModel
from kets.liquidity import liquidity_lambda
from kets.config import get_sheet


def main():
    m = KETSModel.from_excel(macc_mode="step")
    presets = m.msr_presets()

    # ── 방법 1: 가격 웨지 λ ──
    lb = m.level_bridge_path("base", presets["L0"], lam_0=0.0)  # λ 무관(정태·Hotelling만 필요)
    p_static_2026 = lb[0]["static"]
    p_hotel_2026 = lb[0]["hotelling"]

    kau = get_sheet("KAU과거가격")
    obs = {int(r["year"]): float(r["kau_avg_krw"]) for _, r in kau.iterrows()
           if r["kau_avg_krw"] == r["kau_avg_krw"]}  # NaN 제외
    recent = {y: obs[y] for y in (2023, 2024, 2025) if y in obs}

    print("═══ 방법 1: 가격 웨지 λ (모델 2026 정태/Hotelling 기준) ═══")
    print(f"  정태(λ=0)={p_static_2026:,.0f}원   Hotelling(λ=1)={p_hotel_2026:,.0f}원")
    for y, p in recent.items():
        lam = (p - p_static_2026) / (p_hotel_2026 - p_static_2026)
        print(f"  관측 {y} = {p:>7,.0f}원  →  λ_implied = {lam:+.3f}")
    avg_lam = sum((p - p_static_2026) / (p_hotel_2026 - p_static_2026) for p in recent.values()) / len(recent)
    print(f"  → λ₀ ≈ {avg_lam:.3f}  (관측 ≈ 정태 → 기간간 차익거래 사실상 부재)")

    # ── 방법 1b: H1-2026 리프라이싱 λ (모형이 실제 쓰는 앵커) ──
    q2026 = get_sheet("KAU2026시세")
    quotes = [(str(r["date"]), float(r["kau_krw"])) for _, r in q2026.iterrows()
              if r["kau_krw"] == r["kau_krw"]]
    print("\n═══ 방법 1b: H1-2026 리프라이싱 λ (모형 앵커) ═══")
    for d, p in quotes:
        lam = (p - p_static_2026) / (p_hotel_2026 - p_static_2026)
        print(f"  {d:>12} = {p:>7,.0f}원  →  λ_implied = {lam:+.3f}")
    latest_date, latest_px = quotes[-1]
    lam_2026 = (latest_px - p_static_2026) / (p_hotel_2026 - p_static_2026)
    sheet_lam = float({r["parameter"]: r["value"]
                       for _, r in get_sheet("유동성모수").iterrows()}["lambda_2026_implied"])
    print(f"  최신 관측 {latest_date} {latest_px:,.0f}원 → λ₂₀₂₆ = {lam_2026:.4f}")
    print(f"  유동성모수 시트 lambda_2026_implied = {sheet_lam}")
    assert abs(lam_2026 - sheet_lam) < 0.01, (
        f"시트 λ({sheet_lam})와 관측 역산 λ({lam_2026:.4f})가 어긋난다 — "
        "KAU2026시세 갱신 후 유동성모수 시트를 맞추거나, 그 반대를 확인하라.")
    print(f"  ✅ 일치 (허용오차 0.01) — 보고서 λ={sheet_lam}의 재현 근거")

    # ── 방법 2: 회전율 λ 교차검증 ──
    surplus = get_sheet("시장잉여추정")
    carry = {}
    for _, r in surplus.iterrows():
        try:
            carry[int(r["year"])] = float(r["carryover_total_Mt"])
        except (ValueError, TypeError):
            pass
    vol = {int(r["year"]): float(r["trading_volume_Mt"]) for _, r in kau.iterrows()
           if r["trading_volume_Mt"] == r["trading_volume_Mt"]}

    print("\n═══ 방법 2: 회전율 교차검증 (거래량 존재 연도만) ═══")
    print("  turnover = 거래량 / 전년 유통물량(carryover)")
    for y, v in sorted(vol.items()):
        prev_carry = carry.get(y - 1) or carry.get(y)
        if prev_carry:
            tr = v / prev_carry
            print(f"  {y}: 거래량 {v:>6.1f}Mt / 유통 {prev_carry:>4.0f}Mt = 회전율 {tr:.2f}")
    print("  주의: 거래량이 2015·2020·2024 3개년만 존재 → 시계열 λ 산출 불가(데이터 공백).")

    # ── ψ: 문헌 범위 ──
    print("\n═══ ψ (행태승수) — 이월제한 선행연구 범위 ═══")
    print("  Yu & Lee (2020, 한국기후변화학회지 11(3)): 일시 하락 후 추세 복귀 → ψ ≈ 0")
    print("  Yu & Lee (2023, 자원환경경제연구 32(3)): 규제기간 중 매물출하    → ψ < 0")
    print("  → 채택 범위 ψ ∈ [−0.5, 0]. 점추정은 원자료 프런티어 재추정 필요(미착수).")

    # ── 산출물: 관측점별 implied λ ──
    # 보고서 §9 한계 4가 "어느 관측을 고르느냐로 λ가 갈린다"고 쓰는 근거.
    # 원자료 월별 VWAP은 build_carry_analysis가 남긴 산출물에서 읽는다
    # (ets_data.xlsx는 그 스크립트만 읽는다 — AGENTS.md 절대규칙 1).
    rows = [("KAU과거가격", str(y), p) for y, p in sorted(recent.items())]
    rows += [("KAU2026시세", d, p) for d, p in quotes]
    carry_json = _ROOT / "outputs" / "runs" / "carry_analysis_cce_v2.0.json"
    if carry_json.is_file():
        import json
        monthly = json.loads(carry_json.read_text(encoding="utf-8")).get("kau25_2026_monthly", {})
        for month, rec in sorted(monthly.items()):
            if rec.get("vwap_krw"):
                rows.append(("원자료 VWAP", month, rec["vwap_krw"]))
                rows.append(("원자료 종가최저", month, rec["close_min_krw"]))
                rows.append(("원자료 종가최고", month, rec["close_max_krw"]))

    out_csv = _ROOT / "outputs" / "csv" / "lambda_implied.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source", "observation", "kau_krw", "p_static_krw", "p_hotelling_krw",
                    "lambda_implied"])
        for src, label, px in rows:
            lam = (px - p_static_2026) / (p_hotel_2026 - p_static_2026)
            w.writerow([src, label, round(px, 1), round(p_static_2026, 1),
                        round(p_hotel_2026, 1), round(lam, 4)])
    print(f"\nsaved: {out_csv.relative_to(_ROOT)} ({len(rows)}행)")

    print("\n═══ 1차 캘리브레이션 결론 ═══")
    print(f"  λ₀ ≈ {avg_lam:.2f}  (현 K-ETS ≈ 정태; 유동성 개혁으로 λ↑ 시나리오)")
    print("  ψ  ∈ [−0.5, 0]  (문헌 범위; 저유동에서 긴축이 무반응~dumping)")


if __name__ == "__main__":
    main()

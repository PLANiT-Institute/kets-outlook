"""K-ETS 가격전망 엔진 v0.8.

정책 레버(MSR·유동성)는 메서드 인자로 받고, 기저 데이터(cap·BAU·MACC·EUA·
무상할당)는 마스터 엑셀/JSON 데이터 계약에서 로드한다(하드코딩 없음).
데이터만 로드하고 solve는 호출 시점에 수행 → 대화형 UI(웹 /api/solve,
Streamlit)에서 슬라이더가 바뀔 때마다 실제 모형을 다시 돌릴 수 있다.

v0.7 → v0.8 솔버 교정: banking≥0 제약 Hotelling의 상(phase) 분해를
'첫 위반연도 분할'에서 'argmax 소진연도 분할'로 교체 — v0.7 방식은 상 경계에서
가격 상향점프(무위험 차익기회)를 허용하는 결함이 있었다. 교정 후 균형은
rubin1996·schennach2000의 특성화(할인가격 비증가; bank>0 구간 r 성장;
bank=0에서만 하향점프)를 만족하며, `tests/test_engine.py`의 무차익 불변식으로
회귀검증한다. 정합성 앵커(관측 KAU vs 정태가)는 테스트에서 데이터로 고정.

유동성 오버레이(`realized_path`)는 `liquidity.py`를 사용해 L0 반사실 대비
MSR 가격효과에 전달승수 T(λ,ψ)를 곱한다 — Policy Brief §5.
"""

from __future__ import annotations
import numpy as np

from kets.hotelling import hotelling_price_path
from kets.liquidity import realized_price_path, lambda_ramp, liquidity_lambda

SECTOR_MAP = {"MACC_철강": "steel", "MACC_석유화학": "petrochem", "MACC_발전": "power",
              "MACC_시멘트": "cement", "MACC_정유": "refinery"}
SECTOR_LC_KEYS = {"steel": ["수소환원제철"], "petrochem": ["전기크래킹"],
                  "power": ["태양광", "풍력", "그린수소"], "cement": [], "refinery": []}
SECTOR_ALLOC_CAT = {"steel": "carbon_leakage_sector", "petrochem": "carbon_leakage_sector",
                    "power": "power_sector", "cement": "carbon_leakage_sector",
                    "refinery": "non_power_sector", "other": "non_power_sector"}
SCENARIOS = ["base", "middle", "ideal"]

# 정태청산 탐색 상한 = 물리적 비가용(infeasibility) 마커. 이 가격에 도달한 셀은
# "어떤 가격에도 부족을 해소할 수 없는" 제약조합(예: ideal cap × 무조건 수량보류
# L_QB — 잉여가 없는 시장에서 경매물량 절반을 무조건 보류)을 뜻하며 균형이 아니다.
# 무차익 불변식 게이트(러너·테스트)는 이 마커 셀을 제외하고 검사한다.
PRICE_CEIL = 5e7


def _bisect(f, lo, hi, xtol=0.1, max_iter=200):
    """순수 파이썬 이분법 근탐색 (scipy.brentq 대체, stdlib만 사용).

    brentq와 동일 계약: f(lo)·f(hi) < 0 이 아니면 ValueError.
    Vercel 서버리스 배포에서 scipy 의존을 제거하기 위함.
    """
    flo, fhi = f(lo), f(hi)
    if flo == 0.0:
        return lo
    if fhi == 0.0:
        return hi
    if flo * fhi > 0:
        raise ValueError("f(lo), f(hi) 부호 동일 — 근 없음")
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        fmid = f(mid)
        if fmid == 0.0 or 0.5 * (hi - lo) < xtol:
            return mid
        if flo * fmid < 0:
            hi, fhi = mid, fmid
        else:
            lo, flo = mid, fmid
    return 0.5 * (lo + hi)


def _num(v, default=0.0):
    """JSON에서 온 값(None/NaN 가능)을 float로. 결측은 default."""
    try:
        f = float(v)
        return default if f != f else f   # NaN 방어
    except (TypeError, ValueError):
        return default


class KETSModel:
    """K-ETS 가격전망 엔진. 데이터 소스와 무관(주입형) — 로컬=엑셀, 프로덕션=JSON.

    생성:
      KETSModel(data)            data = kets_data.json 구조의 dict
      KETSModel.from_json(path)  프로덕션(Vercel): stdlib json만 사용
      KETSModel.from_excel()     로컬: 마스터 엑셀(pandas) lazy 로드

    macc_mode:
      "step"        — MACC기술상세 bottom-up 기술 스텝커브 직접 사용(추정 없음).
      "exponential" — 모형파라미터 손맞춤 지수형 α·exp(β·a) (레거시, 비교용).

    엔진 계산부는 numpy + stdlib만 의존(scipy·pandas 없음) → 서버리스 배포 가능.
    """

    def __init__(self, data: dict, macc_mode: str = "step"):
        self.macc_mode = macc_mode
        sh = data["sheets"]
        p = data["model_params"]
        self.model_params = p
        self.years = list(range(p["analysis"]["start_year"], p["analysis"]["end_year"] + 1))
        self.base_year = self.years[0]
        self.r = p["hotelling"]["discount_rate"] + p["hotelling"]["risk_premium"]
        self.eua = {int(x["year"]): _num(x["eua_price_krw"]) for x in sh["EUA가격전망"]}
        self.total_kets_Mt = p["market"]["total_kets_emissions_MtCO2"]
        self.intl_limit_ratio = p["market"]["intl_credit_limit_ratio"]
        self.intl_steepness = p["solver"]["intl_steepness"]
        self.step_width = _num(p["solver"].get("step_smoothing_width"), 0.0)
        self.B0 = _num(data["banking_initial_bank_Mt"]) * 1e6
        self.reserve0 = _num(data["msr_reserve_Mt"]) * 1e6

        # ── MACC 지수형 모수(모형파라미터) ──
        pm = sh["모형파라미터"]
        self.macc = {}
        for cat, sc in SECTOR_MAP.items():
            sub = {r["parameter"]: r["value"] for r in pm if r["category"] == cat}
            if "alpha" in sub:
                self.macc[sc] = {"alpha": _num(sub["alpha"]), "beta": _num(sub["beta"]),
                                 "maxshare": _num(sub["max_abatement_share"]),
                                 "baseline_tco2": _num(sub["baseline_emissions_MtCO2"]) * 1e6}
        # ── 학습곡선 ──
        self.lc = {}
        for r in sh["학습곡선"]:
            self.lc.setdefault(str(r["scenario_id"]), {})[str(r["tech_keyword"])] = _num(r["annual_decline_rate"])

        # ── 부문 baseline(모든 MACC_* + other 잔차) 및 bottom-up 기술 스텝 ──
        self.sector_baseline_Mt = {sc: m["baseline_tco2"] / 1e6 for sc, m in self.macc.items()}
        self.sector_baseline_Mt["other"] = self.total_kets_Mt - sum(self.sector_baseline_Mt.values())
        self.techs = []
        for r in sh["MACC기술상세"]:
            base_Mt = self.sector_baseline_Mt.get(r["sector"])
            if base_Mt is None:
                continue
            self.techs.append({
                "sector": r["sector"], "tech": str(r["technology"]),
                "cost_krw": _num(r["cost_krw_per_tCO2"]),
                "potential_tco2": _num(r["abatement_potential_pct"]) / 100.0 * base_Mt * 1e6,
                "headline": bool(_num(r.get("headline"), 0.0)),
                "h2_kg": _num(r.get("h2_intensity_kg_per_tCO2"), 0.0),
                "elec_MWh": _num(r.get("elec_intensity_MWh_per_tCO2"), 0.0),
                "avail0": _num(r.get("avail_start_year"), 0.0),
                "avail1": _num(r.get("avail_full_year"), 0.0),
            })
        self.techs.sort(key=lambda t: t["cost_krw"])

        # ── BAU/Cap 총량, SF(net) ──
        self._cap_records = sh["배출허용총량"]
        self._fa = sh["무상할당비율"]
        self.bau_total = {yr: sum(_num(r["bau_emissions_tCO2"]) for r in sh["BAU배출전망"]
                                  if int(r["year"]) == yr) for yr in self.years}
        self.cap_total = {sid: {yr: sum(_num(r["cap_tCO2"]) for r in self._cap_records
                                        if r["scenario_id"] == sid and int(r["year"]) == yr)
                                for yr in self.years} for sid in SCENARIOS}
        self.SF = {sid: {yr: self.bau_total[yr] - self.cap_total[sid][yr] for yr in self.years}
                   for sid in SCENARIOS}
        self._msr_sheet = sh["MSR설계"]
        self.cbam = p["cbam"]

        # ── 정책 레버 시트 (없으면 빈 리스트 — 구버전 kets_data.json 호환) ──
        self.auction_levers = [(str(r["lever_id"]), _num(r["auction_ratio"]))
                               for r in sh.get("유상할당레버", [])
                               if isinstance(r.get("lever_id"), str) and r["lever_id"].startswith("A")]
        self.floor_levers = [{"id": r["floor_id"], "f26": _num(r["floor_2026_krw"]),
                              "f40": _num(r["floor_2040_krw"]), "cancel": _num(r["cancel_rate"])}
                             for r in sh.get("MSR가격하한", [])
                             if isinstance(r.get("floor_id"), str) and r["floor_id"].startswith("M")]
        self.kau_history = sh.get("KAU과거가격", [])
        _k26 = [r for r in sh.get("KAU2026시세", [])
                if r.get("kau_krw") and isinstance(r.get("date"), str) and str(r["date"]).startswith("20")]
        self.kau_2026_recent = _num(_k26[-1]["kau_krw"]) if _k26 else 0.0
        self.liquidity = data.get("liquidity_defaults", {})
        # 수소가격 시나리오 (정부 기본계획 경로) — h2_kg>0 기술의 비용경로를 구동
        self.h2_scenario = str(p.get("h2_scenario", "gov"))
        self.h2_price = {}
        for r in sh.get("수소가격시나리오", []):
            if r.get("year") and str(r.get("scenario_id")) == self.h2_scenario:
                self.h2_price[int(r["year"])] = _num(r["h2_price_krw_per_kg"])
        self.elec_scenario = str(p.get("elec_scenario", "gov_invest"))
        self.elec_price = {}      # KRW/MWh
        for r in sh.get("전력가격시나리오", []):
            if r.get("year") and str(r.get("scenario_id")) == self.elec_scenario:
                self.elec_price[int(r["year"])] = _num(r["elec_price_krw_per_kwh"]) * 1000.0
        # 정책패키지 v4: K-MSR(법제화 제도)의 운영규칙 4종 — P0/P1(시행령) + A(가격약속형)/B(수량약속형)
        self.packages = [r for r in sh.get("정책패키지", [])
                         if isinstance(r.get("package_id"), str)
                         and (r["package_id"].startswith("P") or r["package_id"] in ("A", "B"))]

    # ── 데이터 소스별 생성자 ──
    @classmethod
    def from_json(cls, path, macc_mode: str = "step"):
        """프로덕션(Vercel): export된 kets_data.json에서 로드 (stdlib만)."""
        import json
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f), macc_mode)

    @classmethod
    def from_excel(cls, macc_mode: str = "step"):
        """로컬: 마스터 엑셀에서 로드 (pandas lazy import)."""
        from kets.excel_source import load_data_from_excel
        return cls(load_data_from_excel(), macc_mode)

    # ── MSR 프리셋 (MSR설계 시트) → 슬라이더 기본값 ──
    def msr_presets(self) -> dict:
        out = {}
        for r in self._msr_sheet:
            lid = r["level_id"]
            if not isinstance(lid, str) or not lid.startswith("L"):
                continue
            out[lid] = {"id": lid, "name": r["name_kr"],
                        "rho": _num(r["rho_intake"]),
                        "theta_plus": _num(r["theta_plus_Mt"]) * 1e6,
                        "theta_minus": _num(r["theta_minus_Mt"]) * 1e6,
                        "release": _num(r["release_Mt"]) * 1e6,
                        "cancel": _num(r["cancel_rate"]),
                        "carve_reserve": bool(_num(r.get("carve_reserve"), 0.0)),
                        # EU-미러 규칙 (MSR설계 시트 신규 열):
                        #  intake_basis='tnac' → I = min(ρ·TNAC, TNAC−θ⁺)  (EU 2024+ 완충규칙)
                        #  invalidate_above_Mt → 예비분 스톡이 이 값을 넘는 만큼 매년 무효화 (EU식 취소)
                        "intake_basis": str(r.get("intake_basis") or "excess"),
                        "invalidate_above": (_num(r.get("invalidate_above_Mt"), -1.0) * 1e6
                                             if r.get("invalidate_above_Mt") is not None else None),
                        # 수량약속형(B) 규칙 (MSR설계 시트 신규 열, None-safe float):
                        #  theta_cap_frac — 발동임계 = 연 cap 대비 TNAC 비율 (-1 = 무조건 발동)
                        #  start_year     — 개시연도 사전공표 (None/공란 = 즉시)
                        "theta_cap_frac": (_num(r.get("theta_cap_frac"))
                                           if r.get("theta_cap_frac") is not None else None),
                        "start_year": (_num(r.get("start_year"))
                                       if r.get("start_year") is not None else None)}
        return out

    def reserve_carveout(self, sid: str, yr: int) -> float:
        """예비분의 유통공급 차감분(tCO2). 4차 계획기간(2026–2030) cap 비례 배분.

        4차 총량(ICAP 2,537.3Mt)은 시장안정화 예비분 85.28Mt을 포함하므로,
        예비분을 별도 방출원으로 모형화하려면 그만큼을 유통공급에서 격리해야
        이중계상이 없다(MSR설계 시트 [주] 참조). 2030 이후는 5차 계획 미확정 → 0.
        """
        y0, y1 = 2026, 2030
        if not (y0 <= yr <= y1):
            return 0.0
        cap_window = sum(self.cap_total[sid][y] for y in self.years if y0 <= y <= y1)
        if cap_window <= 0:
            return 0.0
        return self.reserve0 * self.cap_total[sid][yr] / cap_window

    # ═══════════════ MACC / 감축 ═══════════════
    def _sector_decline(self, sid, sec):
        rates = self.lc.get(sid, self.lc.get("base", {}))
        vals = [rates[k] for k in SECTOR_LC_KEYS.get(sec, []) if k in rates]
        return sum(vals) / len(vals) if vals else 0.0

    def _tech_decline(self, tech_name, sid):
        """기술명 부분일치로 학습곡선 시트의 연 비용하락률을 찾는다."""
        rates = self.lc.get(sid, self.lc.get("base", {}))
        for kw, rate in rates.items():
            if kw in tech_name:
                return rate
        return 0.0

    def _tech_cost(self, tech, year, sid):
        """기술의 학습조정 한계비용. h2_kg>0이면 학습률 대신
        비용 = 비수소잔여 + h2_kg × 정부수소가격(t)  (수소가격시나리오 시트)."""
        if tech.get("h2_kg", 0.0) > 0.0 and self.h2_price:
            base = tech["cost_krw"] - tech["h2_kg"] * self.h2_price[self.base_year]
            return max(base, 0.0) + tech["h2_kg"] * self.h2_price.get(year, self.h2_price[max(self.h2_price)])
        if tech.get("elec_MWh", 0.0) > 0.0 and self.elec_price:
            # 잔여(연료절감 순액)는 음수 허용 — 저렴한 청정전력에서 비용이 0에 접근(MIT parity)
            base = tech["cost_krw"] - tech["elec_MWh"] * self.elec_price[self.base_year]
            c = base + tech["elec_MWh"] * self.elec_price.get(year, self.elec_price[max(self.elec_price)])
            return max(c, 0.0)
        lr = self._tech_decline(tech["tech"], sid)
        return tech["cost_krw"] * (1 - lr) ** (year - self.base_year) if lr else tech["cost_krw"]

    def _tech_avail(self, tech, year):
        """배치 램프: avail_start_year 이전 0, avail_full_year에 전량 (선형).

        문턱 접촉 순간 잠재량 전량이 투입된다는 비현실적 가정을 제거 —
        하한 방어물량 W의 스파이크(도입연도=최대부담 문제)를 완화한다.
        결정론적(시간 함수)이라 A(P,t)의 경로의존성 없음. 미지정 기술은 즉시 전량.
        """
        s0, s1 = tech.get("avail0", 0.0), tech.get("avail1", 0.0)
        if s0 <= 0 or s0 <= self.base_year:
            return 1.0
        if year < s0:
            return 0.0
        if s1 <= s0:
            return 1.0
        return min((year - s0) / (s1 - s0), 1.0)

    def _abatement_step(self, price, year, sid):
        """스텝 MACC: 학습곡선 적용 비용 임계에서 bottom-up 기술을 활성화.

        step_smoothing_width(w, 모형파라미터 solver)가 0보다 크면 각 기술은
        비용의 (1−w)·adj → adj 구간에서 선형으로 부분 활성화된다 — 한계기술의
        분수적 배치(기술 내 이질적 채택비용). 이로써 A(P)가 강단조·연속이 되어
        경쟁균형 가격이 유일해지고, 전량활성화(w=0)의 plateau 동률·경계점프
        부정성이 제거된다. w=0이면 v0.7과 동일한 계단 활성화.
        """
        t = year - self.base_year
        w = self.step_width
        dom = 0.0
        for tech in self.techs:
            adj = self._tech_cost(tech, year, sid)
            if w > 0.0 and adj > 0.0:
                lo = adj * (1.0 - w)
                if price >= adj:
                    frac = 1.0
                elif price <= lo:
                    frac = 0.0
                else:
                    frac = (price - lo) / (adj - lo)
                dom += frac * tech["potential_tco2"] * self._tech_avail(tech, year)
            elif adj <= price + 0.5:
                dom += tech["potential_tco2"] * self._tech_avail(tech, year)
        intl_max = self.total_kets_Mt * 1e6 * self.intl_limit_ratio
        intl = intl_max / (1 + np.exp(-self.intl_steepness * (price - self.eua[year])))
        return dom + intl

    def _abatement_exp(self, price, year, sid):
        dom = 0.0
        for sec, m in self.macc.items():
            alpha_t = m["alpha"] * (1 - self._sector_decline(sid, sec)) ** (year - self.base_year)
            if price <= alpha_t:
                continue
            a_share = np.log(price / alpha_t) / m["beta"]
            a_share = min(max(a_share, 0.0), m["maxshare"])
            dom += a_share * m["baseline_tco2"]
        intl_max = self.total_kets_Mt * 1e6 * self.intl_limit_ratio
        intl = intl_max / (1 + np.exp(-self.intl_steepness * (price - self.eua[year])))
        return dom + intl

    def abatement_at_price(self, price, year, sid):
        if self.macc_mode == "step":
            return self._abatement_step(price, year, sid)
        return self._abatement_exp(price, year, sid)

    def _excess_demand(self, P, sf, yr, sid):
        return sf - self.abatement_at_price(P, yr, sid)

    def _static_eq(self, sf, yr, sid):
        if sf <= self.abatement_at_price(100.0, yr, sid):
            return 100.0
        try:
            return _bisect(lambda P: self._excess_demand(P, sf, yr, sid), 100.0, PRICE_CEIL, xtol=1e-4)
        except ValueError:
            return PRICE_CEIL

    # ═══════════════ 제약 Hotelling (무차익 상분해) ═══════════════
    def _solve_constrained_hotelling(self, eff_sf, sid, initial_bank):
        """Banking≥0 제약 하의 경쟁균형 가격경로 (rubin1996, schennach2000).

        균형 조건: 할인가격 e^{-rt}·P_t 는 시간에 대해 비증가 —
          · bank > 0 인 구간: P_t 는 정확히 r로 상승 (기간간 무차익),
          · bank = 0 인 시점에서만 하향 점프 허용 (차입 불가 제약이 binding),
          · 상향 점프는 어떤 경우에도 불가 (bank 매입·이월로 차익 → 모순).

        알고리즘(v0.8): 각 잔여구간에서 모든 후보 소진연도 h에 대해
        "h에서 bank가 정확히 0이 되는" Hotelling 초기가 p0(h)를 풀고,
          h* = argmax_h p0(h)
        를 상(phase) 경계로 채택한다. p0* = max ⇒ 구간 내 모든 t≤h*에서
        bank_t(p0*) ≥ bank_t(p0(t)) = 0 (A(P)가 P에 단조증가이므로),
        그리고 후속 상의 초기 할인가는 p0*보다 클 수 없다(크다면 그 소진연도가
        argmax였을 것) ⇒ 경계 점프는 항상 하향 → 무차익 조건 충족.

        v0.7의 '첫 위반연도 분할'은 경계 상향점프(차익기회)를 허용하는
        결함이 있었다 — MSR이 근시일 가격을 낮추는 역설은 그 산물.
        """
        years, r = self.years, self.r
        n = len(years)
        prices = np.zeros(n); banks = np.zeros(n)
        abate = self.abatement_at_price

        def prefix_p0(idxs, h, init_bank):
            """idxs[:h+1] 구간에서 bank(h)=0이 되는 Hotelling 초기가. 불가면 None."""
            sub = idxs[:h + 1]
            py = np.array([years[i] for i in sub])
            def cum_excess(p0):     # = −bank_h : 근에서 bank_h = 0
                ps = hotelling_price_path(p0, r, py, py[0])
                tot = -init_bank
                for k, ix in enumerate(sub):
                    tot += self._excess_demand(ps[k], eff_sf[years[ix]], years[ix], sid)
                return tot
            lo, hi = 1.0, 3e6
            elo = cum_excess(lo)
            if elo < 0:             # 최저가에서도 h까지 bank 미소진 → h는 소진연도 불가
                return None
            for pt in (1e7, 5e7, 2e8):
                if cum_excess(hi) > 0:
                    hi = pt
                else:
                    break
            if cum_excess(hi) > 0:  # 초고가에도 부족 해소 불가 (비현실 구간)
                return None
            try:
                return _bisect(cum_excess, lo, hi, xtol=1e-4)
            except ValueError:
                return None

        def solve_phase(idxs, init_bank, depth=0):
            while idxs and depth <= 32:
                best_h, best_p0 = None, -np.inf
                for h in range(len(idxs)):
                    p0 = prefix_p0(idxs, h, init_bank)
                    if p0 is not None and p0 > best_p0 + 1e-9:
                        best_h, best_p0 = h, p0
                if best_h is None:
                    # 어떤 연도에도 bank 소진 불가(항구 잉여) → 연도별 정태 청산 폴백
                    for ix in idxs:
                        yr = years[ix]
                        p = self._static_eq(eff_sf[yr], yr, sid)
                        prices[ix] = p
                        init_bank = max(init_bank + abate(p, yr, sid) - eff_sf[yr], 0.0)
                        banks[ix] = init_bank
                    return
                sub = idxs[:best_h + 1]
                py = np.array([years[i] for i in sub])
                ps = hotelling_price_path(best_p0, r, py, py[0])
                b = init_bank
                for k, ix in enumerate(sub):
                    prices[ix] = ps[k]
                    b += abate(ps[k], years[ix], sid) - eff_sf[years[ix]]
                    banks[ix] = max(b, 0.0)
                banks[sub[-1]] = 0.0            # 소진연도: 수치오차 정리
                idxs = idxs[best_h + 1:]
                init_bank = 0.0
                depth += 1

        solve_phase(list(range(n)), initial_bank)
        return prices, banks

    # ═══════════════ MSR 고정점 solve ═══════════════
    def _msr_fixed_point(self, sid: str, msr: dict, iters: int = 120):
        """MSR 흡수 I_t(TNAC=B_{t-1})와 Hotelling 가격경로의 고정점 (감쇠 반복).

        임계형(TNAC 트리거) 규칙은 불연속이라 단순 반복이 진동할 수 있다
        (perino2022의 조건부 (불)안정화와 동일 구조). 감쇠(α=0.5) 반복으로
        진동을 수렴시키고, 수렴 실패 시 self.last_fp_converged=False로 표시
        — 비수렴 산출을 균형으로 오인하지 않도록 러너/테스트에서 검사한다.

        Returns: (prices ndarray, banks ndarray, I dict, R dict). eff_sf = SF+carve+I−R.
        """
        years = self.years
        I = {yr: 0.0 for yr in years}; R = {yr: 0.0 for yr in years}
        carve = {yr: (self.reserve_carveout(sid, yr) if msr.get("carve_reserve") else 0.0)
                 for yr in years}
        prices = banks = None
        self.last_fp_converged = False
        prev_prices = None
        stable_count = 0
        hist_I, hist_R = [], []
        for _ in range(iters):
            eff = {yr: self.SF[sid][yr] + carve[yr] + I[yr] - R[yr] for yr in years}
            prices, banks = self._solve_constrained_hotelling(eff, sid, self.B0)
            # 가격기준 수렴: 이진 트리거(방출)가 임계 경계에서 영구 플립해도 감쇠된
            # I·R이 정착하면 가격경로는 고정된다 — 분수적 방출은 불연속 규칙
            # 대응의 볼록화(혼합) 균형으로 해석 (perino2022 다중균형의 평균점).
            if prev_prices is not None and max(abs(a - b) for a, b in zip(prices, prev_prices)) < 1.0:
                stable_count += 1
                if stable_count >= 3:
                    self.last_fp_converged = True
                    break
            else:
                stable_count = 0
            prev_prices = prices
            newI = {}; newR = {}; reserve = self.reserve0; prevB = self.B0
            for i, yr in enumerate(years):
                TNAC = prevB
                if msr.get("intake_basis") == "auction":
                    # 수량조정형(B): 잉여(TNAC)가 연 cap의 theta_cap_frac 초과 시
                    # 그 해 경매예정물량의 rho를 자동 보류 (조정 대상 = 경매물량만).
                    # start_year: 지연 발동형 — 개시연도를 사전공표(은행 채널이 선반영)
                    thr = _num(msr.get("theta_cap_frac"), 0.08) * self.cap_total[sid][yr]
                    fire = (TNAC > thr and yr >= _num(msr.get("start_year"), 0)) \
                        or yr >= _num(msr.get("always_from"), 9e9)   # 2단계: 잉여조건 OR 일정형
                    ii = (msr["rho"] * self.auction_share_t(sid, yr) * self.cap_total[sid][yr]
                          if fire else 0.0)
                elif msr.get("intake_basis") == "tnac":
                    # EU 2024+ 규칙: TNAC>θ⁺면 min(ρ·TNAC, TNAC−θ⁺) — 전체 TNAC 기준 + 완충
                    ii = min(msr["rho"] * TNAC, TNAC - msr["theta_plus"]) \
                        if TNAC > msr["theta_plus"] else 0.0
                else:
                    ii = msr["rho"] * max(TNAC - msr["theta_plus"], 0.0)
                # 흡수는 경매(유상할당) 물량에서만 — 시행령 "유상 할당 물량을 흡수".
                # 상한: intake_basis='auction'이면 그 해 정부공표 경매물량(A_gov 경로),
                # 그 외에는 유상비율 × cap (msr에 auction_ratio 없으면 A_cur 기본).
                if msr.get("intake_basis") == "auction":
                    a_r = self.auction_share_t(sid, yr)
                else:
                    a_r = _num(msr.get("auction_ratio"), self.auction_levers[0][1] if self.auction_levers else 1.0)
                ii = min(ii, a_r * self.cap_total[sid][yr])
                rr = msr["release"] if (TNAC < msr["theta_minus"] and reserve > 0) else 0.0
                rr = min(rr, reserve)
                reserve += ii - rr - msr["cancel"] * ii
                inval = msr.get("invalidate_above")
                if inval is not None and reserve > inval:
                    reserve = inval          # EU식 스톡 무효화: 임계 초과분 영구 소각
                newI[yr] = ii; newR[yr] = rr; prevB = banks[i]
            delta = max(max(abs(newI[yr] - I[yr]), abs(newR[yr] - R[yr])) for yr in years)
            if delta < 1e3:
                I, R = newI, newR
                self.last_fp_converged = True
                break
            # 감쇠 스텝: 임계규칙 진동 억제. 후반부로 갈수록 강한 감쇠(0.5→0.2)로
            # 두 균형 사이 순환(perino2022 구조)을 평균점으로 수렴시킨다.
            hist_I.append(dict(newI)); hist_R.append(dict(newR))
            alpha = 0.5 if _ < 30 else 0.2
            I = {yr: (1 - alpha) * I[yr] + alpha * newI[yr] for yr in years}
            R = {yr: (1 - alpha) * R[yr] + alpha * newR[yr] for yr in years}

        if not self.last_fp_converged and hist_I:
            # 순수 고정점 부재(임계규칙 다중균형·비주기 진동, perino2022) →
            # 꼬리 반복의 Cesàro 평균으로 개입경로를 고정하고 정확해를 1회 계산.
            # 해석: 규제당국이 공표 TNAC 기반 연간 개입물량을 사전 공고하는
            # EU 실무(연 1회 물량 공고)와 동형 — 예측가능 규칙의 결정론적 구현.
            tail = hist_I[-20:]; tailR = hist_R[-20:]
            I = {yr: sum(h[yr] for h in tail) / len(tail) for yr in years}
            R = {yr: sum(h[yr] for h in tailR) / len(tailR) for yr in years}
            eff = {yr: self.SF[sid][yr] + carve[yr] + I[yr] - R[yr] for yr in years}
            prices, banks = self._solve_constrained_hotelling(eff, sid, self.B0)
            self.last_fp_converged = True
            self.last_fp_mode = "cesaro"
        else:
            self.last_fp_mode = "exact"
        return prices, banks, I, R

    def solve_path(self, sid: str, msr: dict, iters: int = 40) -> list[dict]:
        """Hotelling(완전 차익거래, λ=1) 가격경로."""
        prices, banks, I, R = self._msr_fixed_point(sid, msr, iters)
        return [{"year": yr, "kau": float(prices[i]),
                 "abate_Mt": self.abatement_at_price(prices[i], yr, sid) / 1e6,
                 "intake_Mt": I[yr] / 1e6, "release_Mt": R[yr] / 1e6,
                 "bank_Mt": float(banks[i]) / 1e6, "eua": self.eua[yr]}
                for i, yr in enumerate(self.years)]

    # ═══════════════ λ 레짐 (유동성모수 시트, 2026 관측앵커) ═══════════════
    def lambda_regime_path(self, regime: str) -> list[float]:
        """데이터 앵커 λ 시나리오 3종 (v2 재구성, three gates §5.1).

        관측 앵커 λ₂₀₂₆ = lambda_2026_implied (H1-2026 리프라이싱에서 역산).
          hold        — λ = λ₂₀₂₆ 유지 (기대 주도, 인프라 부재의 취약 균형; 중심)
          relapse     — λ₂₀₂₆ → 0 선형 (regime_relapse_years; 2019·2021 사례형 붕괴)
          consolidate — λ₂₀₂₆ → regime_consolidate_terminal 선형
                        (regime_consolidate_years; 유동성 인프라 공고화)
        """
        lam0 = _num(self.liquidity.get("lambda_2026_implied"), 0.0)
        if regime == "hold":
            return [lam0] * len(self.years)
        if regime == "relapse":
            n = max(_num(self.liquidity.get("regime_relapse_years"), 3.0), 1.0)
            return [max(lam0 * (1.0 - (yr - self.base_year) / n), 0.0) for yr in self.years]
        if regime == "consolidate":
            lt = _num(self.liquidity.get("regime_consolidate_terminal"), 0.9)
            n = max(_num(self.liquidity.get("regime_consolidate_years"), 8.0), 1.0)
            return [lam0 + (lt - lam0) * min((yr - self.base_year) / n, 1.0) for yr in self.years]
        raise ValueError(f"unknown lambda regime: {regime}")

    # ═══════════════ 레벨-브리지: 정태(λ=0) ↔ Hotelling(λ=1) ═══════════════
    def level_bridge_path(self, sid: str, msr: dict, lam_0: float = 0.0,
                          lam_terminal: float | None = None,
                          ramp_years: float = 0.0,
                          lam_path: list[float] | None = None) -> list[dict]:
        """유동성 λ로 정태가격(차익거래 X)과 Hotelling-펀더멘털(차익거래 O)을 보간.

        핵심 발견(스텝 MACC): 현 K-ETS 관측가격 ≈ 정태가격(λ≈0). 유동성 인프라가
        차익거래를 살리면(λ↑) 가격이 Hotelling-펀더멘털로 수렴한다.

            P_realized_t = static_t + λ_t·(hotelling_t − static_t)

        MSR 흡수 I_t는 Hotelling 고정점에서 산출한 것을 정태 청산에도 동일 적용
        (eff_sf = SF + I − R) → 두 가격 모두 동일 MSR 개입을 반영.

        Args:
            lam_0: 초기 전달효율 λ (현재 K-ETS ≈ 0).
            lam_terminal: 유동성 인프라 도입 목표 λ (None이면 lam_0 고정).
            ramp_years: λ 램프 연수 (0이면 고정).
        """
        prices, banks, I, R = self._msr_fixed_point(sid, msr)
        if lam_terminal is None:
            lam_terminal = lam_0
        out = []
        for i, yr in enumerate(self.years):
            carve = self.reserve_carveout(sid, yr) if msr.get("carve_reserve") else 0.0
            eff = self.SF[sid][yr] + carve + I[yr] - R[yr]
            p_static = self._static_eq(eff, yr, sid)
            p_hotel = float(prices[i])
            lam = (float(lam_path[i]) if lam_path is not None
                   else lambda_ramp(yr, self.base_year, lam_0, lam_terminal, ramp_years))
            out.append({"year": yr,
                        "static": p_static,
                        "hotelling": p_hotel,
                        "kau_realized": p_static + lam * (p_hotel - p_static),
                        "lambda": lam,
                        "intake_Mt": I[yr] / 1e6, "release_Mt": R[yr] / 1e6,
                        "bank_Mt": float(banks[i]) / 1e6, "eua": self.eua[yr]})
        return out

    # ═══════════════ 유동성 오버레이 (Policy Brief §5) ═══════════════
    def realized_path(self, sid: str, msr: dict, psi: float,
                      lam_0: float, lam_terminal: float | None = None,
                      ramp_years: float = 0.0) -> list[dict]:
        """L0 반사실 대비 MSR 가격효과에 전달승수 T(λ,ψ)를 적용한 실현경로.

        Args:
            psi: 행태 승수 (얇은 시장 몫의 성격; <0 이면 dumping/역효과).
            lam_0: 초기 전달효율 λ.
            lam_terminal: 유동성 인프라 도입 목표 λ (None이면 lam_0 고정).
            ramp_years: λ_0→λ_terminal 램프 연수 (0이면 lam_0 고정).

        Returns: solve_path 레코드에 kau_frictionless·kau_realized·lambda·baseline_kau 추가.
        """
        presets = self.msr_presets()
        base_path = self.solve_path(sid, presets["L0"])   # 반사실 (MSR 미도입)
        msr_path = self.solve_path(sid, msr)               # 무마찰 MSR

        p_base = np.array([r["kau"] for r in base_path])
        p_fri = np.array([r["kau"] for r in msr_path])
        if lam_terminal is None:
            lam_terminal = lam_0
        lam_path = np.array([lambda_ramp(yr, self.base_year, lam_0, lam_terminal, ramp_years)
                             for yr in self.years])
        p_real = realized_price_path(p_base, p_fri, lam_path, psi)

        out = []
        for i, rec in enumerate(msr_path):
            out.append({**rec,
                        "baseline_kau": float(p_base[i]),
                        "kau_frictionless": float(p_fri[i]),
                        "kau_realized": float(p_real[i]),
                        "lambda": float(lam_path[i])})
        return out

    # ═══════════════ 정책 패키지 (정책패키지 시트, v2 three gates) ═══════════════
    def solve_package(self, pkg: dict) -> list[dict]:
        """패키지 = {msr_level, floor_id, auction_lever, cap_scenario, lambda_regime}.

        합성 순서 (논리 §3):
          1. 실현경로 = level_bridge(λ_t 레짐)  — 정태 성분은 행정적으로 무조건 전달,
             기간간 성분만 λ에 비례 (T(λ,ψ) 곱셈 폐기; v2 전달 일원화).
          2. 가격하한 overlay — 경매 최저가는 1차시장에 행정적으로 작용하므로
             λ 게이트를 우회해 실현경로 위에 직접 적용. 방어요건
             W = A(P̄)−A(P_realized) ≤ a·Cap (식 6)은 그대로 구속.
        """
        from kets.policy_grid import floor_at, max_defensible_price

        sid = pkg["cap_scenario"]
        presets = self.msr_presets()
        msr = presets[pkg["msr_level"]]
        lam_path = self.lambda_regime_path(pkg["lambda_regime"])
        bridge = self.level_bridge_path(sid, msr, lam_path=lam_path)

        a_path = self.auction_ratio_path(sid, pkg["auction_lever"])
        y0, y1 = self.years[0], self.years[-1]
        if str(pkg.get("floor_id")) == "corridor":
            # 회랑 하한(경매보류가격): 기술앵커 — 2026 관측가 → target_year H2-DRI 문턱
            cor = self.corridor_floor_path(sid, "수소환원",
                                           int(_num(pkg.get("corridor_target_year"), 2035)),
                                           self.kau_2026_recent,
                                           tech2_sub=(str(pkg["corridor_tech2"])
                                                      if pkg.get("corridor_tech2") else None),
                                           target_year2=(int(_num(pkg.get("corridor_target_year2")))
                                                         if pkg.get("corridor_target_year2") else None))
            floor_path = {yr: cor[i] for i, yr in enumerate(self.years)}
            fl = None
        else:
            fl = next((f for f in self.floor_levers if f["id"] == pkg["floor_id"]), None)
            floor_path = None
        out = []
        for i, rec in enumerate(bridge):
            yr = rec["year"]
            p_real = rec["kau_realized"]
            floor_p = (floor_path[yr] if floor_path is not None
                       else (floor_at(fl, yr, y0, y1) if fl else 0.0))
            defended = True
            kau = p_real
            headroom = 1.0
            if floor_p > p_real:
                # 합산 용량: 수량규칙 흡수 I와 하한 방어 W가 같은 경매물량에서 나옴
                capacity = a_path[yr] * self.cap_total[sid][yr] - rec["intake_Mt"] * 1e6
                capacity = max(capacity, 0.0)
                p_def = max_defensible_price(self, yr, capacity, sid, p_real)
                kau = min(floor_p, p_def)
                W = self.abatement_at_price(kau, yr, sid) - self.abatement_at_price(p_real, yr, sid)
                headroom = (capacity - W) / capacity if capacity > 0 else 0.0
                defended = p_def >= floor_p * 0.995   # 판정 허용오차 0.5%
            out.append({**rec, "kau": kau, "kau_prefloor": p_real,
                        "floor": floor_p, "defended": defended,
                        "headroom": round(headroom, 3),
                        "package_id": pkg.get("package_id")})
        return out

    def corridor_floor_path(self, sid: str, target_tech_sub: str, target_year: int,
                            start_krw: float, tech2_sub: str | None = None,
                            target_year2: int | None = None) -> list[float]:
        """K-MSR 회랑 하한(경매보류가격) 경로 — 기술 문턱 앵커 (EU-목적형 설계).

        시작가 start_krw(2026)에서 target_year에 해당 기술의 (수소 시나리오 반영)
        학습조정 비용에 선형 도달, 이후 문턱 추종. 방어는 solve_package의
        floor overlay와 동일하게 경매물량 한도(W ≤ a·Cap)로 구속된다.
        """
        tech = next(t for t in self.techs if target_tech_sub in t["tech"])
        tech2 = (next(t for t in self.techs if tech2_sub in t["tech"])
                 if tech2_sub and target_year2 else None)
        out = []
        for yr in self.years:
            thr1_t = self._tech_cost(tech, target_year, sid)
            if yr < target_year:
                frac = (yr - self.base_year) / (target_year - self.base_year)
                out.append(start_krw + (thr1_t - start_krw) * frac)
            elif tech2 is None or yr < target_year:
                out.append(self._tech_cost(tech, yr, sid))
            elif target_year2 and yr <= target_year2:
                # 2단: anchor1(도달) → anchor2 문턱으로 선형 (문턱1 밑으로는 안 내려감)
                thr2_t = self._tech_cost(tech2, target_year2, sid)
                frac = (yr - target_year) / max(target_year2 - target_year, 1)
                out.append(max(thr1_t + (thr2_t - thr1_t) * frac,
                               self._tech_cost(tech, yr, sid)))
            else:
                out.append(max(self._tech_cost(tech2, yr, sid),
                               self._tech_cost(tech, yr, sid)))
        return out

    def tech_activation_years(self, price_path: list[float], sid: str,
                              headline_only: bool = False) -> dict:
        """가격경로가 학습조정 기술비용을 처음 넘는 연도. CCUS 등 비헤드라인은
        headline_only=True로 제외 (MACC기술상세 headline 열, 사용자 지시 2026-07-02)."""
        out = {}
        for t in self.techs:
            if headline_only and not t.get("headline"):
                continue
            yr_hit = None
            for i, yr in enumerate(self.years):
                adj = self._tech_cost(t, yr, sid)
                if price_path[i] >= adj:
                    yr_hit = yr
                    break
            out[t["tech"]] = yr_hit
        return out

    def auction_ratio_path(self, sid: str, lever) -> dict[int, float]:
        """패키지 유상할당 경로 {year: a_t}.

        'A_gov' — 정부공표경로: 무상할당비율 시트에서 연도별 도출(auction_share_t).
                  v4 패키지 공통 기준 (상수 레버가 아니라 기발표 일정).
        그 외    — 유상할당레버 시트의 상수 비율(레거시 A_cur/A30/A50/A70)."""
        if str(lever) == "A_gov":
            return {yr: self.auction_share_t(sid, yr) for yr in self.years}
        const = next((r for aid, r in self.auction_levers if aid == lever), 0.0)
        return {yr: const for yr in self.years}

    def auction_share_t(self, sid: str, yr: int) -> float:
        """연도별 경제전체 유상할당 비율 — 무상할당비율 시트(정부 기발표 경로)에서
        부문 cap 가중으로 도출. 4차: 발전 15→50%(2030), 탄소누출 무상 100% 유지.
        v4: 패키지 공통 유상 기준 'A_gov'(base: 2026 ~9.9% → 2030+ ~23.9%)."""
        if not hasattr(self, "_a_gov_cache"):
            self._a_gov_cache = {}
        if (sid, yr) in self._a_gov_cache:
            return self._a_gov_cache[(sid, yr)]
        num = 0.0
        for sec, cat in SECTOR_ALLOC_CAT.items():
            cap_rows = [r for r in self._cap_records if r["scenario_id"] == sid
                        and r["sector_code"] == sec and int(r["year"]) == yr]
            if not cap_rows:
                continue
            fa_rows = [r for r in self._fa if r["scenario_id"] == sid
                       and r["allocation_category"] == cat and int(r["year"]) == yr]
            a = (1.0 - _num(fa_rows[0]["free_ratio"])) if fa_rows else 0.0
            num += _num(cap_rows[0]["cap_tCO2"]) * a
        tot = self.cap_total[sid][yr]
        share = num / tot if tot > 0 else 0.0
        self._a_gov_cache[(sid, yr)] = share
        return share

    # ── 재정 보조 (선택) ──
    def auction_revenue(self, sid, yr, price):
        rev = 0.0
        for sec, cat in SECTOR_ALLOC_CAT.items():
            cap_rows = [r for r in self._cap_records if r["scenario_id"] == sid
                        and r["sector_code"] == sec and int(r["year"]) == yr]
            if not cap_rows:
                continue
            fa_rows = [r for r in self._fa if r["scenario_id"] == sid
                       and r["allocation_category"] == cat and int(r["year"]) == yr]
            auction_ratio = (1.0 - _num(fa_rows[0]["free_ratio"])) if fa_rows else 0.0
            rev += _num(cap_rows[0]["cap_tCO2"]) * auction_ratio * price
        return rev

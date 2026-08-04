// results.ts — 논문 v4 정적 결과 데이터 레이어.
//
// 입력: public/model/results_v1.json — outputs/runs/msr_results_v1.0.json(러너 v1.0,
// 논문 v4 SSOT)의 빌드타임 슬림 추출 (scripts/export_web_data.py). 하드코딩 없음.
//
// 내용: K-MSR(법제화 제도)의 운영규칙 4종 비교 —
//   P0 무정책 반사실 · P1 시행령 초안대로 · A 가격약속형(경매보류가격 운영경로) ·
//   B 수량약속형(흡수·무효화 기능의 일정형 운영).

import resultsV1 from '../../public/model/results_v1.json';

// ─── 타입 ───────────────────────────────────────────────────
export type PackageId = 'P0' | 'P1' | 'A' | 'B';

export type PackagePathRow = {
  year: number;
  kau: number;
  floor: number;
  defended: boolean;
  headroom: number;
  bank_Mt: number;
  auction_share: number;
  /** 정태(λ=0) 균형가격 — 그 해 수급만으로 청산 */
  static: number;
  /** 제약 Hotelling(λ=1) 가격 — 미래 희소성 완전 반영 */
  hotelling: number;
  /** 유동성 전달계수 λ ∈ [0,1] */
  lambda: number;
};

export type PackageRecord = {
  meta: {
    package_id: string; name_en: string; name_kr: string;
    msr_level: string; floor_id: string; auction_lever: string;
    cap_scenario: string; lambda_regime: string;
  };
  path: PackagePathRow[];
  activation_headline: Record<string, number | null>;
  defended_all: boolean;
  min_headroom: number;
  max_drawdown: number;
  cum_intake_Mt: number;
  cum_auction_rev_trillion: number;
};

type SensitivityCell = {
  A: { h2_dri: number | null; e_ncc: number | null; defended_all: boolean; min_headroom: number };
  B: { h2_dri: number | null; e_ncc: number | null };
};

const results = resultsV1 as unknown as {
  _meta: { source: string; model_version: number; note: string };
  packages: Record<PackageId, PackageRecord>;
  sensitivity_h2_elec: Record<string, SensitivityCell>;
  gate_waterfall: unknown[];
  escalator_floor: EscalatorFloor | null;
};

/** 경매 최저가격 격자 (outputs/runs/escalator_floor_cce_v2.0.json 슬림 추출) */
export type EscalatorFloor = {
  meta: { version: string; baseline_package: string; initial_bank_Mt: number; interpretation: string };
  cases: Record<string, {
    floor_2040: number;
    steel_threshold_year: number | null;
    ncc_threshold_year: number | null;
    cum_required_withholding_Mt: number;
    max_annual_required_withholding_Mt: number;
    min_headroom: number;
    defended_all: boolean;
  }>;
  /** 기술비용 ±20% 격자 — 출발가격별 실현가능성 */
  cost_sensitivity_pm20: {
    f0: number; cost_scale: number; cum_required_withholding_Mt: number; defended_all: boolean;
  }[];
};

// ─── 결과 export ────────────────────────────────────────────
export const RESULTS_META = results._meta;
export const PACKAGES = results.packages;
export const SENSITIVITY = results.sensitivity_h2_elec;
export const FLOOR = results.escalator_floor;

/** 패키지 표시 순서·라벨·색 (디자인 상수 — 수치 아님) */
export const PKG = {
  P0: { id: 'P0' as const, ko: '무정책',      en: 'No policy',           color: '#9CA3AF', soft: '#F3F4F6', dash: '4 3' },
  P1: { id: 'P1' as const, ko: '시행령 초안', en: 'Decree as drafted',   color: '#5B7BAA', soft: '#E3EAF4', dash: '6 3' },
  A:  { id: 'A'  as const, ko: '가격약속형 A', en: 'Price commitment',    color: '#10A574', soft: '#D5EFE3', dash: undefined },
  B:  { id: 'B'  as const, ko: '수량약속형 B', en: 'Quantity commitment', color: '#E8A33D', soft: '#FBEFD7', dash: undefined },
} as const;

export const PKG_LIST = [PKG.P0, PKG.P1, PKG.A, PKG.B] as const;

/** 헤드라인 기술 표시명 (activation_headline 키를 부분일치로 매핑) */
export const TECH_LABELS = [
  { key: 'H₂-DRI', ko: '수소환원제철', short: 'H₂-DRI' },
  { key: 'e-cracker', ko: 'NCC 전기분해', short: 'e-NCC' },
] as const;

/** activation_headline에서 기술(부분일치 key)의 활성화 연도 조회 */
export function activationYear(pid: PackageId, techKey: string): number | null {
  const act = PACKAGES[pid].activation_headline;
  const hit = Object.entries(act).find(([name]) => name.includes(techKey));
  return hit ? hit[1] : null;
}

export function pkgRowAt(pid: PackageId, year: number): PackagePathRow | undefined {
  return PACKAGES[pid].path.find(r => r.year === year);
}

/** 패키지 가격비교 차트 데이터 (fig4 형식) — 연도 × {P0,P1,A,B, floorA} */
export const PACKAGE_PRICE_PATH = PACKAGES.P0.path.map((r, i) => ({
  year: r.year,
  P0: r.kau,
  P1: PACKAGES.P1.path[i].kau,
  A: PACKAGES.A.path[i].kau,
  B: PACKAGES.B.path[i].kau,
  floorA: PACKAGES.A.path[i].floor,
}));

/** P1 시행령 초안의 2031 가격붕락(waterbed) — 2030→2031 낙폭 비율 */
export const P1_WATERBED = (() => {
  const p30 = pkgRowAt('P1', 2030);
  const p31 = pkgRowAt('P1', 2031);
  if (!p30 || !p31) return null;
  return { from: p30.kau, to: p31.kau, dropPct: (p30.kau - p31.kau) / p30.kau };
})();

/** 유상할당(정부 기발표 경로 A_gov): 2026 → 2030+ 비율 (모든 패키지 공통) */
export const AUCTION_SHARE_GOV = (() => {
  const p26 = pkgRowAt('P0', 2026);
  const p30 = pkgRowAt('P0', 2030);
  return { y2026: p26?.auction_share ?? 0, y2030: p30?.auction_share ?? 0 };
})();

/** 민감도(수소×전력 2×2) — 결정적 분기 표시용 행 배열 */
export const SENSITIVITY_ROWS = Object.entries(SENSITIVITY).map(([key, cell]) => {
  const [h2, elec] = key.split('|');
  return {
    key,
    h2Conservative: h2 === 'h2_conservative',
    elecConservative: elec === 'elec_conservative',
    h2Label: h2 === 'h2_gov' ? '정부경로' : '보수적',
    elecLabel: elec === 'elec_gov_invest' ? '정부경로' : '보수적',
    A: cell.A,
    B: cell.B,
  };
});

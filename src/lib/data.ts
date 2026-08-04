// data.ts — 대시보드 공통 데이터 레이어.
//
// 입력 데이터(SSOT): public/model/kets_data.json — 마스터 엑셀 export. 하드코딩 없음.
// 논문 v4 정적 결과(P0/P1/A/B 패키지)는 src/lib/results.ts (results_v1.json) 참조.
// 라이브 계산은 /api/solve (web/api/solve.py → src/model/engine.py).

import ketsData from '../../public/model/kets_data.json';

// ─── 시나리오 메타 (커스텀 시뮬레이터 Cap 레버 표시용 디자인 상수) ─────
export const SCEN = {
  base:   { id: 'base'   as const, ko: '기준',  en: 'Base',   color: '#5B7BAA', soft: '#E3EAF4', desc: '현행 4차 계획 cap · 패키지 분석 공통 기준' },
  middle: { id: 'middle' as const, ko: '중간',  en: 'Middle', color: '#E8A33D', soft: '#FBEFD7', desc: 'NDC 연동 중간 강도 cap' },
  ideal:  { id: 'ideal'  as const, ko: '이상',  en: 'Ideal',  color: '#10A574', soft: '#D5EFE3', desc: 'EU 정합 고강도 cap' },
} as const;

export const SCEN_LIST = [SCEN.base, SCEN.middle, SCEN.ideal] as const;
export type ScenarioId = 'base' | 'middle' | 'ideal';
export const EUA_COLOR = '#94A3B8';

// ─── kets_data.json (마스터 엑셀 export) 타입 ───────────────
type QuoteRow = { date: string | null; kau_krw: number | null; source: string | null };

const kets = ketsData as unknown as {
  msr_reserve_Mt: number;
  sheets: {
    'KAU2026시세': QuoteRow[];
  };
};

// ─── KAU 시세 (sheets["KAU2026시세"], 출처 포함) ─────────────
export type KauQuote = { date: string; kau_krw: number; source: string };

export const KAU_2026_QUOTES: KauQuote[] = kets.sheets['KAU2026시세']
  .filter((r): r is { date: string; kau_krw: number; source: string | null } =>
    typeof r.kau_krw === 'number' && typeof r.date === 'string' && !r.date.startsWith('['))
  .map(r => ({ date: r.date, kau_krw: r.kau_krw, source: r.source ?? '' }));

/** 가장 최근 KAU 시세 (시트는 날짜 오름차순) */
export const LATEST_KAU_QUOTE: KauQuote = KAU_2026_QUOTES[KAU_2026_QUOTES.length - 1];

// ─── 포맷터 · 내비게이션 ────────────────────────────────────
export const fmtWon = (n: number) => n.toLocaleString('ko-KR');
export const fmtWonK = (n: number) => {
  if (n >= 1e6) return (n / 1e6).toFixed(0) + 'M';
  return (n / 1000).toFixed(0) + 'k';
};

export const NAV_ITEMS = [
  { id: 'overview',   ko: '대시보드 홈',        en: 'Overview',  icon: 'home' },
  { id: 'mechanism',  ko: '가격 결정 메커니즘',  en: 'Mechanism', icon: 'gauge' },
  { id: 'simulator',  ko: '시나리오 시뮬레이터', en: 'Simulator', icon: 'bars' },
  { id: 'report',     ko: '보고서 요약',         en: 'Report',    icon: 'gap' },
];

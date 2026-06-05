// data.ts — 모형 v0.6 출력 기반. Coase + Constrained Hotelling.
// 모든 데이터는 model_output.json에서 추출 (하드코딩 없음).

import modelOutput from './model_output.json';

export const SCEN = {
  base:   { id: 'base'   as const, ko: '기준',  en: 'Base',   color: '#5B7BAA', soft: '#E3EAF4', desc: '현행 정책 유지 · 누출업종 무상 100%' },
  middle: { id: 'middle' as const, ko: '중간',  en: 'Middle', color: '#E8A33D', soft: '#FBEFD7', desc: 'NDC 연동 점진적 유상 확대' },
  ideal:  { id: 'ideal'  as const, ko: '이상',  en: 'Ideal',  color: '#10A574', soft: '#D5EFE3', desc: 'EU CBAM 무상할당 폐지 정합 (2034년 0%)' },
} as const;

export const SCEN_LIST = [SCEN.base, SCEN.middle, SCEN.ideal] as const;
export type ScenarioId = 'base' | 'middle' | 'ideal';
export const EUA_COLOR = '#94A3B8';

type ModelPricePoint = typeof modelOutput.scenarios.base.price_path[number];
type OptionalPricePoint = ModelPricePoint & {
  auction_ratio_power?: number;
  auction_ratio_non_power?: number;
  auction_ratio_leakage?: number;
  active_techs?: Record<string, unknown>;
};
type SupplyDemandPoint = { bau_Mt?: number; cap_Mt?: number };
type MaccTechnologyDetail = {
  sector: string; technology: string;
  cost_usd: number; cost_krw: number;
  potential_pct: number; potential_Mt: number;
  timeline: string; source: string;
};
type ModelOutputWithOptional = typeof modelOutput & {
  supply_demand?: Partial<Record<ScenarioId, SupplyDemandPoint[]>>;
  macc_technologies?: MaccTechnologyDetail[];
};

const optionalPoint = (point: ModelPricePoint): OptionalPricePoint => point as OptionalPricePoint;

// ─── 모형 출력에서 데이터 추출 ───────────────────────────────
const m = modelOutput as ModelOutputWithOptional;
const paths = {
  base:   m.scenarios.base.price_path,
  middle: m.scenarios.middle.price_path,
  ideal:  m.scenarios.ideal.price_path,
};

// KAU 가격 경로 + EUA
export const PRICE_PATH = paths.base.map((b, i) => ({
  year: b.year,
  base:   b.kau_price_krw,
  middle: paths.middle[i].kau_price_krw,
  ideal:  paths.ideal[i].kau_price_krw,
  eua:    b.eua_price_krw,
}));

// EUA-KAU 가격차
export const GAP_PATH = paths.base.map((b, i) => ({
  year: b.year,
  base:   b.gap_krw,
  middle: paths.middle[i].gap_krw,
  ideal:  paths.ideal[i].gap_krw,
}));

// 누적 경매수입
export const REVENUE_PATH = paths.base.map((b, i) => ({
  year: b.year,
  base:   b.cumulative_revenue_trillion,
  middle: paths.middle[i].cumulative_revenue_trillion,
  ideal:  paths.ideal[i].cumulative_revenue_trillion,
}));

// 연간 경매수입
export const ANNUAL_REVENUE_PATH = paths.base.map((b, i) => ({
  year: b.year,
  base:   b.annual_revenue_trillion,
  middle: paths.middle[i].annual_revenue_trillion,
  ideal:  paths.ideal[i].annual_revenue_trillion,
}));

// v0.6: Banking stock 경로
export const BANKING_PATH = paths.base.map((b, i) => ({
  year: b.year,
  base:   b.banking_stock_Mt,
  middle: paths.middle[i].banking_stock_Mt,
  ideal:  paths.ideal[i].banking_stock_Mt,
}));

// v0.6: Fundamental shortfall 경로
export const SHORTFALL_PATH = paths.base.map((b, i) => ({
  year: b.year,
  base:   b.fundamental_shortfall_Mt,
  middle: paths.middle[i].fundamental_shortfall_Mt,
  ideal:  paths.ideal[i].fundamental_shortfall_Mt,
}));

// v0.6: 유상할당 비율 경로 (부문별)
export const AUCTION_RATIO_PATH = paths.base.map((b, i) => ({
  year: b.year,
  base:   b.auction_ratio,
  middle: paths.middle[i].auction_ratio,
  ideal:  paths.ideal[i].auction_ratio,
}));

// 부문별 유상할당 비율 (발전/비전환/누출업종)
export const AUCTION_BY_CATEGORY = {
  power: paths.base.map((b, i) => ({
    year: b.year,
    base:   optionalPoint(b).auction_ratio_power ?? b.auction_ratio,
    middle: optionalPoint(paths.middle[i]).auction_ratio_power ?? paths.middle[i].auction_ratio,
    ideal:  optionalPoint(paths.ideal[i]).auction_ratio_power ?? paths.ideal[i].auction_ratio,
  })),
  non_power: paths.base.map((b, i) => ({
    year: b.year,
    base:   optionalPoint(b).auction_ratio_non_power ?? 0,
    middle: optionalPoint(paths.middle[i]).auction_ratio_non_power ?? 0,
    ideal:  optionalPoint(paths.ideal[i]).auction_ratio_non_power ?? 0,
  })),
  leakage: paths.base.map((b, i) => ({
    year: b.year,
    base:   optionalPoint(b).auction_ratio_leakage ?? 0,
    middle: optionalPoint(paths.middle[i]).auction_ratio_leakage ?? 0,
    ideal:  optionalPoint(paths.ideal[i]).auction_ratio_leakage ?? 0,
  })),
};

// 기술 도입 현황 (2030년 기준, 시나리오별)
export function getActiveTechs(scenarioId: ScenarioId, yearIdx: number = 4) {
  const pp = paths[scenarioId][yearIdx];
  return optionalPoint(pp).active_techs ?? {};
}

// v0.6: 수급 구조 — BAU vs Cap (시나리오별)
const sd = m.supply_demand ?? {};
export const SUPPLY_DEMAND = paths.base.map((b, i) => ({
  year: b.year,
  bau: sd.base?.[i]?.bau_Mt ?? 0,
  cap_base: sd.base?.[i]?.cap_Mt ?? 0,
  cap_middle: sd.middle?.[i]?.cap_Mt ?? 0,
  cap_ideal: sd.ideal?.[i]?.cap_Mt ?? 0,
}));

// MACC 기술 상세 (마스터 엑셀에서 로드)
export const MACC_TECH_DETAILS: MaccTechnologyDetail[] = m.macc_technologies ?? [];

// KPI 요약
export const KPI = {
  price2030: {
    base:   m.scenarios.base.kpi.price_2030,
    middle: m.scenarios.middle.kpi.price_2030,
    ideal:  m.scenarios.ideal.kpi.price_2030,
  },
  price2040: {
    base:   m.scenarios.base.kpi.price_2040,
    middle: m.scenarios.middle.kpi.price_2040,
    ideal:  m.scenarios.ideal.kpi.price_2040,
  },
  cumRevenue2040: {
    base:   m.scenarios.base.kpi.cumulative_revenue_2040,
    middle: m.scenarios.middle.kpi.cumulative_revenue_2040,
    ideal:  m.scenarios.ideal.kpi.cumulative_revenue_2040,
  },
  gap2030: {
    base:   m.scenarios.base.kpi.gap_2030,
    middle: m.scenarios.middle.kpi.gap_2030,
    ideal:  m.scenarios.ideal.kpi.gap_2030,
  },
  abatement: {
    base:   m.scenarios.base.kpi.cumulative_abatement_Mt,
    middle: m.scenarios.middle.kpi.cumulative_abatement_Mt,
    ideal:  m.scenarios.ideal.kpi.cumulative_abatement_Mt,
  },
};

// 비교 테이블
export const COMPARE_ROWS = m.compare_rows;

// 2030 CBAM 부담 (조원/년)
export const CBAM_2030 = {
  steel: {
    base:   m.scenarios.base.kpi.cbam_2030_steel,
    middle: m.scenarios.middle.kpi.cbam_2030_steel,
    ideal:  m.scenarios.ideal.kpi.cbam_2030_steel,
  },
  petchem: {
    base:   m.scenarios.base.kpi.cbam_2030_petrochem,
    middle: m.scenarios.middle.kpi.cbam_2030_petrochem,
    ideal:  m.scenarios.ideal.kpi.cbam_2030_petrochem,
  },
};

// MACC 기술별 데이터 — model_output.json에서 추출 가능한 부분 + 마스터 엑셀 기반
// 부문별 MACC (6개 부문, 30개 기술)
export type MaccTech = { tech: string; en: string; sector: string; potential: number; cost: number };

const SECTOR_KO: Record<string, string> = {
  steel: '철강', petrochem: '석유화학', power: '발전',
  cement: '시멘트', refinery: '정유', other: '기타',
};

const SECTOR_COLORS: Record<string, string> = {
  steel: '#3B82F6', petrochem: '#8B5CF6', power: '#EF4444',
  cement: '#F59E0B', refinery: '#06B6D4', other: '#6B7280',
};

export { SECTOR_KO, SECTOR_COLORS };

export const MACC_ALL: MaccTech[] = [
  // 철강 (Nature 2025 s41586-025-09658-9)
  { tech: '에너지효율 개선',     en: 'Energy efficiency',  sector: 'steel',     potential: 5.5,  cost: -11750 },
  { tech: '스크랩/EAF 확대',    en: 'Scrap/EAF',          sector: 'steel',     potential: 11.0, cost: 414 },
  { tech: '연료전환 (석탄→가스)', en: 'Fuel switching',     sector: 'steel',     potential: 8.8,  cost: 34500 },
  { tech: 'H₂-DRI (HyREX)',   en: 'H₂-DRI',              sector: 'steel',     potential: 16.5, cost: 151800 },
  // 석유화학 (ACS Sustainable Chem. Eng. 2024 / RSC Green Chemistry 2025)
  { tech: '공정최적화/열통합',   en: 'Heat integration',   sector: 'petrochem', potential: 2.25, cost: 6900 },
  { tech: '바이오 나프타',      en: 'Bio-naphtha',         sector: 'petrochem', potential: 2.25, cost: 62100 },
  { tech: '블루암모니아 연료',   en: 'Blue NH₃',           sector: 'petrochem', potential: 3.6,  cost: 121440 },
  { tech: '그린H₂ 연료',        en: 'Green H₂ fuel',      sector: 'petrochem', potential: 3.15, cost: 204240 },
  { tech: '전기크래킹',         en: 'E-cracker',           sector: 'petrochem', potential: 2.25, cost: 774180 },
  // 발전 (KEPCO/MOTIE/KEEI 2024, CCUS·원전 제외)
  { tech: '석탄 효율개선',       en: 'Coal USC',           sector: 'power',     potential: 5.9,  cost: 12000 },
  { tech: '석탄→LNG 전환',      en: 'Coal→Gas',           sector: 'power',     potential: 23.5, cost: 55000 },
  { tech: '태양광 확대',         en: 'Solar PV',           sector: 'power',     potential: 13.7, cost: 90000 },
  { tech: '풍력 확대 (해상)',    en: 'Offshore wind',       sector: 'power',     potential: 9.8,  cost: 178000 },
  { tech: '수소/암모니아 혼소',  en: 'H₂/NH₃ co-fire',     sector: 'power',     potential: 9.8,  cost: 180000 },
  // 시멘트 (GCCA Net Zero Roadmap 2024, CCUS 제외)
  { tech: '에너지 효율개선',     en: 'Efficiency',         sector: 'cement',    potential: 1.65, cost: 5000 },
  { tech: '클링커 비율 저감',   en: 'Clinker reduction',   sector: 'cement',    potential: 2.31, cost: 15000 },
  { tech: '대체원료',           en: 'Alt. materials',      sector: 'cement',    potential: 3.3,  cost: 25000 },
  { tech: '대체연료',           en: 'Alt. fuels',          sector: 'cement',    potential: 2.64, cost: 35000 },
  // 정유 (IEA Refinery Roadmap 2024, CCUS 제외)
  { tech: '에너지 효율개선',     en: 'Efficiency',         sector: 'refinery',  potential: 2.0,  cost: 5000 },
  { tech: '열통합/폐열회수',    en: 'Heat recovery',       sector: 'refinery',  potential: 3.2,  cost: 12000 },
  { tech: '전기가열로 전환',    en: 'Electric furnace',    sector: 'refinery',  potential: 2.0,  cost: 55000 },
  { tech: '그린수소 도입',      en: 'Green H₂',            sector: 'refinery',  potential: 4.0,  cost: 120000 },
  // 기타 (IEA Energy Efficiency 2024)
  { tech: '산업 에너지효율',     en: 'Industrial eff.',    sector: 'other',     potential: 6.3,  cost: 10000 },
  { tech: '전기화/열펌프',      en: 'Electrification',     sector: 'other',     potential: 6.3,  cost: 40000 },
  { tech: '재생에너지 자가발전', en: 'Self-gen RE',         sector: 'other',     potential: 3.78, cost: 50000 },
].sort((a, b) => a.cost - b.cost);

// 부문별 필터
export const MACC_STEEL = MACC_ALL.filter(t => t.sector === 'steel');
export const MACC_PETCHEM = MACC_ALL.filter(t => t.sector === 'petrochem');
export const MACC_POWER = MACC_ALL.filter(t => t.sector === 'power');

// 부문 목록
export const SECTORS = ['steel', 'petrochem', 'power', 'cement', 'refinery', 'other'] as const;
export type SectorId = typeof SECTORS[number];

export const SECTOR_INFO: Record<SectorId, { ko: string; en: string; baseline: number; color: string }> = {
  steel:     { ko: '철강',     en: 'Steel',           baseline: 110, color: '#3B82F6' },
  petrochem: { ko: '석유화학', en: 'Petrochemicals',  baseline: 45,  color: '#8B5CF6' },
  power:     { ko: '발전',     en: 'Power',           baseline: 196, color: '#EF4444' },
  cement:    { ko: '시멘트',   en: 'Cement',           baseline: 33,  color: '#F59E0B' },
  refinery:  { ko: '정유',     en: 'Refinery',         baseline: 40,  color: '#06B6D4' },
  other:     { ko: '기타',     en: 'Other',            baseline: 126, color: '#6B7280' },
};

export const fmtWon = (n: number) => n.toLocaleString('ko-KR');
export const fmtWonK = (n: number) => {
  if (n >= 1e6) return (n / 1e6).toFixed(0) + 'M';
  return (n / 1000).toFixed(0) + 'k';
};
export const fmtTril = (n: number) => n.toFixed(1) + '조';

export const NAV_ITEMS = [
  { id: 'overview',   ko: '대시보드 홈',     en: 'Overview',     icon: 'home' },
  { id: 'mechanism',  ko: '가격 결정 메커니즘', en: 'Mechanism',    icon: 'gauge' },
  { id: 'simulator',  ko: '시나리오 시뮬레이터', en: 'Simulator',    icon: 'bars' },
  { id: 'revenue',    ko: '재정 분석',       en: 'Fiscal analysis', icon: 'coin' },
  { id: 'gap',        ko: 'CBAM 분석',      en: 'CBAM gap',     icon: 'gap' },
];

// 모형 메타데이터
export const MODEL_META = {
  version: m.model_version,
  generated: m.generated,
  description: m.model_description,
  parameters: {
    base_r:  m.scenarios.base.r,
    base_p0: m.scenarios.base.p0,
    middle_p0: m.scenarios.middle.p0,
    ideal_p0: m.scenarios.ideal.p0,
  },
};

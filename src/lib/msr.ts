// msr.ts — K-MSR(시장안정화예비분) 제도 파라미터.
//
// 확정 수치는 public/model/kets_data.json(마스터 엑셀 export, SSOT)에서 로드한다.
// 이전 버전의 클라이언트 사이드 수동/규칙 MSR 시뮬레이터(calculateMsrAction 등)는
// 라이브 파이썬 엔진(POST /api/solve, web/api/solve.py)으로 대체되어 삭제되었다.

import ketsData from '../../public/model/kets_data.json';

const kets = ketsData as unknown as { msr_reserve_Mt: number };

/**
 * 4차 계획기간(2026–2030) 시장안정화 용도 예비분 (Mt).
 * 출처: kets_data.json `msr_reserve_Mt` (ICAP 2025.10, 4차 할당계획).
 */
export const MSR_RESERVE_MT = kets.msr_reserve_Mt;

/**
 * DRAFT 가정 — 시행령 2026-04-29 시행, 가격범위는 2026-08 공고 예정 — draft 가정.
 *
 * 아래 감시선(가격밴드)과 잉여비율 기준은 공식 공고 전의 작업 가정(draft)이며
 * 확정 제도 수치가 아니다. 2026년 8월 공고 후 kets_data.json(SSOT)으로 이관하고
 * 이 객체는 삭제할 것.
 */
export const KMSR_DRAFT_ASSUMPTIONS = {
  isDraft: true,
  announcementDue: '2026-08',
  /** draft 하단 감시선 (원/tCO₂) */
  lowPriceKrw: 15000,
  /** draft 상단 감시선 (원/tCO₂) */
  highPriceKrw: 25000,
  /** draft 잉여비율 하단 (release 신호) */
  lowerSurplusRatio: 0.05,
  /** draft 잉여비율 상단 (intake 신호) */
  upperSurplusRatio: 0.18,
} as const;

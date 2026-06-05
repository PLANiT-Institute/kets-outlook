export type MsrMode = 'manual' | 'price_band' | 'surplus_rule' | 'hybrid';

export const MSR_MODE_LABELS: Record<MsrMode, { ko: string; en: string }> = {
  manual: { ko: '수동', en: 'Manual' },
  price_band: { ko: '가격밴드', en: 'Price band' },
  surplus_rule: { ko: '잉여비율', en: 'Surplus rule' },
  hybrid: { ko: '하이브리드', en: 'Hybrid' },
};

export const KETS_MSR_POLICY = {
  phase4ReserveMt: 85.277328,
  phase4ReserveKau: 85277328,
  highPriceKrw: 25000,
  lowPriceKrw: 15000,
  upperSurplusRatio: 0.18,
  lowerSurplusRatio: 0.05,
  maxReleaseMt: 20,
  maxIntakeMt: 20,
  recentKau25Krw: 24550,
  mayAuctionClearingKrw: 19600,
  budgetAuctionPriceKrw: 19894,
  ruleFinalization: '2026.08',
} as const;

export type MsrAction = {
  adjustmentMt: number;
  intakeMt: number;
  releaseMt: number;
  reserveStockEndMt: number;
  triggerLabel: string;
};

type MsrSignal = 'release' | 'intake' | 'neutral';

type MsrActionInput = {
  mode: MsrMode;
  manualAdjustmentMt: number;
  previousPriceKrw: number;
  previousSurplusRatio: number;
  reserveStockStartMt: number;
};

export const clampManualMsrAdjustment = (value: number) =>
  Math.max(-30, Math.min(30, Math.round(value)));

function round1(value: number) {
  return Math.round(value * 10) / 10;
}

function priceSignal(previousPriceKrw: number): MsrSignal {
  if (previousPriceKrw >= KETS_MSR_POLICY.highPriceKrw) return 'release';
  if (previousPriceKrw <= KETS_MSR_POLICY.lowPriceKrw) return 'intake';
  return 'neutral';
}

function surplusSignal(previousSurplusRatio: number): MsrSignal {
  if (previousSurplusRatio <= KETS_MSR_POLICY.lowerSurplusRatio) return 'release';
  if (previousSurplusRatio >= KETS_MSR_POLICY.upperSurplusRatio) return 'intake';
  return 'neutral';
}

function signalToAction(signal: MsrSignal, reserveStockStartMt: number): MsrAction {
  if (signal === 'release') {
    const releaseMt = Math.min(KETS_MSR_POLICY.maxReleaseMt, reserveStockStartMt);
    return {
      adjustmentMt: round1(releaseMt),
      intakeMt: 0,
      releaseMt: round1(releaseMt),
      reserveStockEndMt: round1(reserveStockStartMt - releaseMt),
      triggerLabel: releaseMt > 0 ? '공급 방출' : '예비분 소진',
    };
  }

  if (signal === 'intake') {
    const intakeMt = KETS_MSR_POLICY.maxIntakeMt;
    return {
      adjustmentMt: -round1(intakeMt),
      intakeMt: round1(intakeMt),
      releaseMt: 0,
      reserveStockEndMt: round1(reserveStockStartMt + intakeMt),
      triggerLabel: '경매 흡수',
    };
  }

  return {
    adjustmentMt: 0,
    intakeMt: 0,
    releaseMt: 0,
    reserveStockEndMt: round1(reserveStockStartMt),
    triggerLabel: '중립',
  };
}

export function calculateMsrAction({
  mode,
  manualAdjustmentMt,
  previousPriceKrw,
  previousSurplusRatio,
  reserveStockStartMt,
}: MsrActionInput): MsrAction {
  if (mode === 'manual') {
    const adjustmentMt = clampManualMsrAdjustment(manualAdjustmentMt);
    if (adjustmentMt > 0) {
      const releaseMt = Math.min(adjustmentMt, reserveStockStartMt);
      return {
        adjustmentMt: round1(releaseMt),
        intakeMt: 0,
        releaseMt: round1(releaseMt),
        reserveStockEndMt: round1(reserveStockStartMt - releaseMt),
        triggerLabel: releaseMt > 0 ? '수동 방출' : '예비분 소진',
      };
    }

    if (adjustmentMt < 0) {
      const intakeMt = Math.abs(adjustmentMt);
      return {
        adjustmentMt: -round1(intakeMt),
        intakeMt: round1(intakeMt),
        releaseMt: 0,
        reserveStockEndMt: round1(reserveStockStartMt + intakeMt),
        triggerLabel: '수동 흡수',
      };
    }

    return signalToAction('neutral', reserveStockStartMt);
  }

  const byPrice = priceSignal(previousPriceKrw);
  const bySurplus = surplusSignal(previousSurplusRatio);

  if (mode === 'price_band') {
    return {
      ...signalToAction(byPrice, reserveStockStartMt),
      triggerLabel: byPrice === 'release'
        ? '전년 가격 상단'
        : byPrice === 'intake'
          ? '전년 가격 하단'
          : '가격밴드 내부',
    };
  }

  if (mode === 'surplus_rule') {
    return {
      ...signalToAction(bySurplus, reserveStockStartMt),
      triggerLabel: bySurplus === 'release'
        ? '잉여 부족'
        : bySurplus === 'intake'
          ? '잉여 과다'
          : '잉여 정상',
    };
  }

  const releaseScore = Number(byPrice === 'release') + Number(bySurplus === 'release');
  const intakeScore = Number(byPrice === 'intake') + Number(bySurplus === 'intake');
  const hybridSignal: MsrSignal = releaseScore > intakeScore
    ? 'release'
    : intakeScore > releaseScore
      ? 'intake'
      : 'neutral';

  return {
    ...signalToAction(hybridSignal, reserveStockStartMt),
    triggerLabel: hybridSignal === 'release'
      ? '가격/수량 긴축'
      : hybridSignal === 'intake'
        ? '가격/수량 완화'
        : '혼합 신호 중립',
  };
}

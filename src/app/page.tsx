'use client';

import { Sidebar, PageHeader, ChartCard, ChartLegend, PageFooter } from '@/components/Shell';
import { KpiCards } from '@/components/KpiCards';
import {
  KAUPriceChart, GapAreaChart, IndustryCBAMBarChart, MACCChartFull,
  BankingChart, RevenueChart, CumRevenueChart, AllocationChart, ShortfallChart,
  SupplyDemandChart, TechActivationTable,
} from '@/components/Charts';
import { CompareTable } from '@/components/CompareTable';
import { SCEN, SCEN_LIST, EUA_COLOR, KPI, MACC_ALL, SECTOR_INFO } from '@/lib/data';

export default function OverviewPage() {
  // MACC 요약 통계
  const totalPotential = MACC_ALL.reduce((s, d) => s + d.potential, 0);
  const sectorCoverage = Object.entries(SECTOR_INFO)
    .filter(([id]) => id !== 'other')
    .reduce((s, [, info]) => s + info.baseline, 0);
  const coveragePct = (sectorCoverage / 550 * 100).toFixed(0);

  return (
    <div className="flex min-h-screen bg-[#F9FAFB]" style={{ fontFamily: "'Pretendard', 'Inter', sans-serif", color: '#111827' }}>
      <Sidebar active="overview" />

      <div className="flex-1 flex flex-col min-w-0">
        <div className="px-9 pt-6 flex-1">
          <PageHeader />

          {/* KPI row — 4열 */}
          <KpiCards />

          {/* ── 1. KAU 가격 경로 (메인 차트) ── */}
          <ChartCard
            title="KAU 가격 경로 (2026–2040)"
            en="KAU price path under 3 policy scenarios · Coase equilibrium (BAU−Cap)"
          >
            <KAUPriceChart height={340} />
            <div className="mt-[14px] pt-[14px] border-t border-[#F3F4F6]">
              <ChartLegend />
            </div>
          </ChartCard>

          {/* ── 2. 수급 구조: BAU vs Cap ── */}
          <ChartCard
            title="배출허용총량(Cap) 경로 vs BAU 배출량"
            en="Supply (Cap) vs Demand (BAU) · the scissors that drive price"
            hint="검정선(BAU)과 색상선(Cap)의 차이 = 시장이 감축해야 할 총량(shortfall). Cap이 빨리 줄어들수록 감축 수요가 커지고 가격이 상승. 2030년까지 Cap 경로는 3개 시나리오 모두 동일(3차 할당계획), 이후 시나리오별 차별화."
          >
            <SupplyDemandChart height={300} />
            <div className="mt-3 pt-3 border-t border-[#F3F4F6] flex items-center gap-6 text-[11px] text-[#6B7280]">
              <span className="flex items-center gap-1.5">
                <span className="w-5 border-t-2 border-[#111827]" /> BAU 배출량 (자연감소만)
              </span>
              {SCEN_LIST.map(s => (
                <span key={s.id} className="flex items-center gap-1.5">
                  <span className="w-5 border-t-2" style={{ borderColor: s.color }} />
                  Cap ({s.ko})
                </span>
              ))}
            </div>
          </ChartCard>

          {/* ── 3. 시장 메커니즘: Shortfall + Banking ── */}
          <div className="mt-5 grid grid-cols-2 gap-4">
            <ChartCard
              title="감축 수요 (BAU − Cap)"
              en="Fundamental shortfall · drives equilibrium price"
              hint="BAU와 Cap의 차이. 이 shortfall이 커질수록 균형가격 상승. Coase 정리: 무상할당 비율과 무관하게 BAU−Cap만이 가격을 결정."
              accent={SCEN.base.color}
            >
              <ShortfallChart height={230} />
            </ChartCard>

            <ChartCard
              title="Banking Stock 추이"
              en="Banked allowance inventory · Constrained Hotelling"
              hint="Banking stock ≥ 0 제약. 잔고가 0에 도달하면 Hotelling 경로 종료 → 정태균형 전환."
              accent={SCEN.ideal.color}
            >
              <BankingChart height={230} />
            </ChartCard>
          </div>

          {/* ── 4. 재정 분석: 유상할당 + 경매수입 ── */}
          <div className="mt-5 grid grid-cols-2 gap-4">
            <ChartCard
              title="부문별 유상할당 비율"
              en="Auction ratio by allocation category · free allocation phase-out"
              hint="누출업종: base(0%유상) vs ideal(2034년 100%유상). 발전부문과 비전환부문도 시나리오별로 상이."
              accent={SCEN.ideal.color}
            >
              <AllocationChart height={310} />
            </ChartCard>

            <ChartCard
              title="연간 경매수입"
              en="Annual auction revenue · allocation method drives revenue, not price"
              hint="가격은 Cap으로 결정되지만, 경매수입은 유상할당 비율에 비례. Ideal 시나리오: 100% 유상 → 수입 극대화."
              accent={SCEN.middle.color}
            >
              <RevenueChart height={310} />
            </ChartCard>
          </div>

          {/* ── 4. CBAM 영향 ── */}
          <div className="mt-5 grid gap-4" style={{ gridTemplateColumns: '1.45fr 1fr' }}>
            <ChartCard
              title="EUA−KAU 가격차 추이"
              en="Price gap as CBAM exposure · 2026–2040"
              hint="격차가 클수록 CBAM 부담 증가. Ideal 시나리오가 2040년 경 가장 빠르게 수렴."
              accent={EUA_COLOR}
            >
              <GapAreaChart height={250} />
            </ChartCard>

            <ChartCard
              title="2030년 산업별 CBAM 부담 추정"
              en="= EU export × embedded CO₂ × (EUA − KAU)"
              accent={SCEN.middle.color}
            >
              <IndustryCBAMBarChart height={220} />
            </ChartCard>
          </div>

          {/* ── 5. 전체 MACC (6개 부문, 30개 기술) ── */}
          <div className="mt-5">
            <ChartCard
              title="전체 K-ETS 감축기술 MACC"
              en={`Marginal Abatement Cost Curve · 6 sectors, ${MACC_ALL.length} technologies · ${coveragePct}% of emissions individually modeled`}
              hint="각 막대는 개별 감축기술(부문별 색상). 가로=누적 잠재량, 세로=한계비용. 점선은 시나리오별 2030 KAU 균형가격 — 선 아래 기술이 경제성 확보."
              accent={SCEN.ideal.color}
            >
              <MACCChartFull height={340} />

              {/* MACC 경제성 요약 */}
              <div className="mt-4 pt-4 border-t border-[#F3F4F6] grid grid-cols-3 gap-4">
                {SCEN_LIST.map(s => {
                  const p = KPI.price2030[s.id];
                  const viable = MACC_ALL.filter(t => t.cost <= p);
                  const viableMt = viable.reduce((sum, t) => sum + t.potential, 0);
                  const viableSectors = new Set(viable.map(t => t.sector)).size;
                  return (
                    <div key={s.id} className="flex items-start gap-[10px]">
                      <span className="w-[3px] self-stretch rounded-sm" style={{ background: s.color }} />
                      <div className="flex-1">
                        <div className="text-[11.5px] flex items-baseline gap-[6px]">
                          <span className="font-semibold text-[#111827]">{s.ko}</span>
                          <span className="text-[#9CA3AF] text-[10px]" style={{ fontFamily: 'Inter' }}>{s.en}</span>
                          <span className="ml-auto text-[#6B7280]" style={{ fontFamily: 'Inter' }}>
                            KAU {(p/1000).toFixed(0)}k
                          </span>
                        </div>
                        <div className="text-[11px] text-[#6B7280] mt-1 leading-[1.5]">
                          경제성 확보: <strong className="text-[#111827]" style={{ fontFamily: 'Inter' }}>
                            {viable.length}/{MACC_ALL.length}
                          </strong> 기술 ({viableSectors}개 부문)
                        </div>
                        <div className="text-[10.5px] text-[#9CA3AF] mt-[2px]" style={{ fontFamily: 'Inter' }}>
                          감축잠재량 {viableMt.toFixed(1)} / {totalPotential.toFixed(1)} MtCO₂/년
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </ChartCard>
          </div>

          {/* ── 6. 기술 도입 현황 (시나리오별 활성화 매트릭스) ── */}
          <div className="mt-5">
            <ChartCard
              title="시나리오별 감축기술 도입 현황 (2030년)"
              en="Technology activation matrix at 2030 equilibrium price · ✓ = economically viable"
              hint="각 시나리오의 2030 균형가격에서 비용이 낮은 기술부터 순서대로 활성화. 활성화된 기술(✓)의 누적 감축잠재량이 시장 수요(BAU−Cap)를 충족하는 수준에서 균형."
              accent={SCEN.base.color}
              noPad
            >
              <div className="px-2 py-1">
                <TechActivationTable />
              </div>
            </ChartCard>
          </div>

          {/* ── 7. 비교 테이블 ── */}
          <div className="mt-5">
            <ChartCard title="시나리오 간 핵심 지표 비교" en="Cross-scenario comparison · v0.6 Coase + Constrained Hotelling" noPad>
              <div className="py-1">
                <CompareTable />
              </div>
            </ChartCard>
          </div>

          <div className="h-6" />
        </div>

        <PageFooter />
      </div>
    </div>
  );
}

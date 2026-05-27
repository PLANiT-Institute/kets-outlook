'use client';

import { useState } from 'react';
import { Sidebar, PageHeader, ChartCard, ChartLegend, PageFooter } from '@/components/Shell';
import { KpiCards } from '@/components/KpiCards';
import {
  KAUPriceChart, GapAreaChart, IndustryCBAMBarChart, MACCChartFull,
  BankingChart, RevenueChart, CumRevenueChart, AllocationChart, ShortfallChart,
  SupplyDemandChart, TechActivationTable,
} from '@/components/Charts';
import { CompareTable } from '@/components/CompareTable';
import { MechanismPanel } from '@/components/Mechanism';
import { SimulatorPanel } from '@/components/Simulator';
import { SCEN, SCEN_LIST, EUA_COLOR, KPI, MACC_ALL, SECTOR_INFO } from '@/lib/data';

// ─── 탭별 콘텐츠 ────────────────────────────────────────────

function OverviewTab() {
  const totalPotential = MACC_ALL.reduce((s, d) => s + d.potential, 0);
  const sectorCoverage = Object.entries(SECTOR_INFO)
    .filter(([id]) => id !== 'other')
    .reduce((s, [, info]) => s + info.baseline, 0);
  const coveragePct = (sectorCoverage / 550 * 100).toFixed(0);

  return (
    <>
      <KpiCards />

      <ChartCard title="KAU 가격 경로 (2026–2040)"
        en="KAU price path under 3 policy scenarios · Coase equilibrium (BAU−Cap)">
        <KAUPriceChart height={380} />
        <div className="mt-[14px] pt-[14px] border-t border-[#F3F4F6]"><ChartLegend /></div>
      </ChartCard>

      <ChartCard title="배출허용총량(Cap) 경로 vs BAU 배출량"
        en="Supply (Cap) vs Demand (BAU) · the scissors that drive price"
        hint="검정선(BAU)과 색상선(Cap)의 차이 = shortfall. Cap이 빨리 줄어들수록 가격 상승. 2030년까지 시나리오별 차별화.">
        <SupplyDemandChart height={300} />
        <div className="mt-3 pt-3 border-t border-[#F3F4F6] flex items-center gap-6 text-[11px] text-[#6B7280]">
          <span className="flex items-center gap-1.5">
            <span className="w-5 border-t-2 border-[#111827]" /> BAU
          </span>
          {SCEN_LIST.map(s => (
            <span key={s.id} className="flex items-center gap-1.5">
              <span className="w-5 border-t-2" style={{ borderColor: s.color }} /> Cap ({s.ko})
            </span>
          ))}
        </div>
      </ChartCard>

      <div className="mt-5 grid grid-cols-2 gap-4">
        <ChartCard title="감축 수요 (BAU − Cap)" en="Fundamental shortfall" accent={SCEN.base.color}>
          <ShortfallChart height={230} />
        </ChartCard>
        <ChartCard title="Banking Stock 추이" en="Constrained Hotelling" accent={SCEN.ideal.color}>
          <BankingChart height={230} />
        </ChartCard>
      </div>

      <div className="mt-5">
        <ChartCard title="전체 K-ETS 감축기술 MACC"
          en={`6 sectors, ${MACC_ALL.length} technologies · ${coveragePct}% individually modeled`}
          accent={SCEN.ideal.color}>
          <MACCChartFull height={340} />
          <div className="mt-4 pt-4 border-t border-[#F3F4F6] grid grid-cols-3 gap-4">
            {SCEN_LIST.map(s => {
              const p = KPI.price2030[s.id];
              const viable = MACC_ALL.filter(t => t.cost <= p);
              const viableMt = viable.reduce((sum, t) => sum + t.potential, 0);
              return (
                <div key={s.id} className="flex items-start gap-[10px]">
                  <span className="w-[3px] self-stretch rounded-sm" style={{ background: s.color }} />
                  <div className="flex-1">
                    <div className="text-[11.5px] flex items-baseline gap-[6px]">
                      <span className="font-semibold text-[#111827]">{s.ko}</span>
                      <span className="ml-auto text-[#6B7280]" style={{ fontFamily: 'Inter' }}>KAU {(p/1000).toFixed(0)}k</span>
                    </div>
                    <div className="text-[11px] text-[#6B7280] mt-1">
                      경제성 확보: <strong className="text-[#111827]">{viable.length}/{MACC_ALL.length}</strong> 기술
                    </div>
                    <div className="text-[10.5px] text-[#9CA3AF] mt-[2px]" style={{ fontFamily: 'Inter' }}>
                      {viableMt.toFixed(1)} / {totalPotential.toFixed(1)} Mt/yr
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </ChartCard>
      </div>

      <div className="mt-5">
        <ChartCard title="시나리오 간 핵심 지표 비교" en="Cross-scenario comparison" noPad>
          <div className="py-1"><CompareTable /></div>
        </ChartCard>
      </div>
    </>
  );
}

function RevenueTab() {
  return (
    <>
      <div className="grid grid-cols-2 gap-4">
        <ChartCard title="부문별 유상할당 비율"
          en="Auction ratio by allocation category"
          hint="누출업종: base(0%유상) vs ideal(2034년 100%유상)"
          accent={SCEN.ideal.color}>
          <AllocationChart height={310} />
        </ChartCard>
        <ChartCard title="연간 경매수입"
          en="Annual auction revenue"
          hint="가격은 Cap으로 결정, 경매수입은 유상비율에 비례"
          accent={SCEN.middle.color}>
          <RevenueChart height={310} />
        </ChartCard>
      </div>
      <div className="mt-5">
        <ChartCard title="누적 경매수입 추이" en="Cumulative auction revenue" accent={SCEN.ideal.color}>
          <CumRevenueChart height={250} />
        </ChartCard>
      </div>
    </>
  );
}

function CbamTab() {
  return (
    <>
      <div className="grid gap-4" style={{ gridTemplateColumns: '1.45fr 1fr' }}>
        <ChartCard title="EUA−KAU 가격차 추이" en="Price gap as CBAM exposure" accent={EUA_COLOR}>
          <GapAreaChart height={280} />
        </ChartCard>
        <ChartCard title="2030년 산업별 CBAM 부담" en="= EU export × CO₂ × (EUA − KAU)" accent={SCEN.middle.color}>
          <IndustryCBAMBarChart height={250} />
        </ChartCard>
      </div>
      <div className="mt-5">
        <ChartCard title="기술 도입 현황 (2030년)" en="Technology activation at equilibrium price" noPad>
          <div className="px-2 py-1"><TechActivationTable /></div>
        </ChartCard>
      </div>
    </>
  );
}

// ─── 탭 제목 ────────────────────────────────────────────────
const TAB_HEADERS: Record<string, { title: string; subtitle: string }> = {
  overview:  { title: 'K-ETS 가격전망 및 정책 시나리오 분석', subtitle: 'Coase + Staircase MACC + Constrained Hotelling 모형으로 도출한 KAU 가격 경로와 핵심 지표.' },
  mechanism: { title: '가격 결정 메커니즘', subtitle: '배출권 가격이 어떻게 결정되는지, 각 변수가 어떤 역할을 하는지 단계별로 설명합니다.' },
  simulator: { title: '시나리오 시뮬레이터', subtitle: '감축기술을 선택/해제하고, Cap 경로와 학습곡선을 조절하여 가격 변화를 실시간으로 확인합니다.' },
  revenue:   { title: '재정 분석', subtitle: '무상할당 비율에 따른 경매수입 추이와 부문별 유상할당 경로.' },
  gap:       { title: 'CBAM 분석', subtitle: 'EUA−KAU 가격차와 한국 수출기업의 CBAM 부담 추정.' },
};

// ─── 메인 페이지 ────────────────────────────────────────────
export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState('overview');
  const header = TAB_HEADERS[activeTab] ?? TAB_HEADERS.overview;

  return (
    <div className="flex min-h-screen bg-[#F9FAFB]" style={{ fontFamily: "'Pretendard', 'Inter', sans-serif", color: '#111827' }}>
      <Sidebar active={activeTab} onNavigate={setActiveTab} />

      <div className="flex-1 flex flex-col min-w-0">
        <div className="px-9 pt-6 flex-1">
          {/* 동적 헤더 */}
          <div className="flex items-end justify-between gap-6 pb-[22px]">
            <div>
              <div className="text-[10.5px] tracking-[.16em] text-[#9CA3AF] uppercase mb-[6px]" style={{ fontFamily: 'Inter' }}>
                K-ETS Price Outlook · {activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}
              </div>
              <h1 className="text-[26px] font-bold text-[#111827] tracking-tight m-0">{header.title}</h1>
              <div className="mt-2 text-[13px] text-[#6B7280] max-w-[720px] leading-[1.55]">{header.subtitle}</div>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center px-[11px] py-[6px] border border-[#E5E7EB] rounded-full text-[11.5px] text-[#4B5563] bg-white" style={{ fontFamily: 'Inter' }}>2026–2040</span>
            </div>
          </div>

          {/* 탭 콘텐츠 */}
          {activeTab === 'overview' && <OverviewTab />}
          {activeTab === 'mechanism' && <MechanismPanel />}
          {activeTab === 'simulator' && <SimulatorPanel />}
          {activeTab === 'revenue' && <RevenueTab />}
          {activeTab === 'gap' && <CbamTab />}

          <div className="h-6" />
        </div>

        <PageFooter />
      </div>
    </div>
  );
}

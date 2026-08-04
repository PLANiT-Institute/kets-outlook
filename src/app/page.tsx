'use client';

import { useState } from 'react';
import { Topbar, ChartCard, PageFooter } from '@/components/Shell';
import {
  PackageKpiCards, PackagePriceChart, HeadlineTable, DecisiveBranchTable,
} from '@/components/PackageResults';
import { MechanismPanel } from '@/components/Mechanism';
import { SimulatorPanel } from '@/components/Simulator';
import { ReportPanel } from '@/components/ReportPanel';
import { PKG, RESULTS_META, AUCTION_SHARE_GOV } from '@/lib/results';
import { LATEST_KAU_QUOTE, fmtWon } from '@/lib/data';
import { MSR_RESERVE_MT, KMSR_DRAFT_ASSUMPTIONS } from '@/lib/msr';

// ─── 탭별 콘텐츠 ────────────────────────────────────────────

function OverviewTab() {
  return (
    <>
      <PackageKpiCards />

      <ChartCard title="K-MSR 운영규칙 4종의 KAU 가격경로 (2026–2040)"
        en="Realized price paths under four operating rules of the legislated K-MSR"
        hint="P0 무정책 · P1 시행령 초안대로 · A 가격약속형(경매보류가격 회랑) · B 수량약속형(2035 일정형 흡수·무효화). 유상할당은 모두 정부 기발표 경로(A_gov) 공통.">
        <PackagePriceChart height={380} />
      </ChartCard>

      <div className="mt-5">
        <ChartCard title="운영규칙별 핵심 지표" en="Headline comparison across operating rules" noPad
          accent={PKG.A.color}>
          <div className="py-1 px-2"><HeadlineTable /></div>
        </ChartCard>
      </div>

      <div className="mt-5">
        <ChartCard title="결정적 분기 — 수소×전력 투입가격 민감도"
          en="The decisive branch: cost-side uncertainty separates the twins"
          hint="중심 시나리오에서 근사쌍둥이인 A·B는 수소가격이 보수적으로 어긋나는 순간 갈라진다."
          accent="#F59E0B" noPad>
          <div className="py-1 px-5 pb-4"><DecisiveBranchTable /></div>
        </ChartCard>
      </div>

      <AssumptionsPanel />
    </>
  );
}

function AssumptionsPanel() {
  const assumptions = [
    { name: '분석 대상', value: 'K-MSR 운영규칙', src: '제도는 법제화 완료(시행령 2026-04-29 시행) — 비교 대상은 P0/P1/A/B 운영규칙' },
    { name: 'A 가격약속형', value: '경매보류가격 회랑', src: '기술앵커: 2026 관측가 → 2035 수소환원(H₂-DRI) 문턱 · 미유찰 물량 무효화 (신규 제도 아님)' },
    { name: 'B 수량약속형', value: '2035 일정형', src: '흡수·무효화 기능의 일정형 운영: 경매물량 50% 무조건 흡수·전량 무효화' },
    { name: '유상할당', value: `${(AUCTION_SHARE_GOV.y2026 * 100).toFixed(1)}% → ${(AUCTION_SHARE_GOV.y2030 * 100).toFixed(1)}%`, src: '정부 기발표 경로(A_gov, 무상할당비율 시트) — 신규 경매물량 요구 없음' },
    { name: '기술 문턱', value: '수소·전력 경로 연동', src: '정부 수소경제기본계획·전력 가격 시나리오로 구동되는 학습조정 비용경로' },
    { name: '가격 전달 λ', value: 'H1-2026 앵커', src: '레벨-브리지: 정태(λ=0)↔Hotelling(λ=1), λ는 2026 리프라이싱에서 역산' },
    { name: 'K-MSR 예비분', value: `${MSR_RESERVE_MT.toFixed(1)} Mt`, src: '4차 할당계획 시장안정화 용도 예비분 (cap 내 버퍼)' },
    { name: '가격범위 공고', value: KMSR_DRAFT_ASSUMPTIONS.announcementDue, src: `감시선 ${fmtWon(KMSR_DRAFT_ASSUMPTIONS.lowPriceKrw)}~${fmtWon(KMSR_DRAFT_ASSUMPTIONS.highPriceKrw)}원은 공고 전 draft 가정` },
  ];

  return (
    <>
      <div className="ta-section-gap"><span className="eyebrow">Assumptions & traceability</span></div>
      <section className="ta-panel mt-0">
        <div className="ta-panel-head">
          <div>
            <h2 className="ta-panel-title">모든 핵심 수치는 아래 가정에서 계산됩니다</h2>
            <div className="ta-panel-sub">
              Source: {RESULTS_META.source} (v{RESULTS_META.model_version}) · 최근 KAU 시세 {fmtWon(LATEST_KAU_QUOTE.kau_krw)}원 ({LATEST_KAU_QUOTE.date})
            </div>
          </div>
        </div>
        <div className="px-[22px]">
          <div className="ta-assump-grid">
            {assumptions.map((item) => (
              <div key={item.name} className="ta-assump">
                <div>
                  <div className="ta-assump-name">{item.name}</div>
                  <div className="ta-assump-src">{item.src}</div>
                </div>
                <div className="ta-assump-value">{item.value}</div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}

// ─── 탭 제목 ────────────────────────────────────────────────
const TAB_HEADERS: Record<string, { title: string; subtitle: string }> = {
  overview:  { title: 'K-MSR 운영규칙 비교 — 가격약속형 vs 수량약속형', subtitle: '법제화된 K-MSR을 어떻게 운영할 것인가. 무정책(P0)·시행령 초안(P1)·가격약속형(A)·수량약속형(B)의 KAU 가격경로와 기술 활성화·방어여유·재정 비교 (논문 v4).' },
  mechanism: { title: '가격 결정 메커니즘', subtitle: '배출권 가격이 어떻게 결정되고, K-MSR 운영규칙이 어느 지점에 작용하는지 단계별로 설명합니다.' },
  report:    { title: '보고서 요약 — 진단·원인·처방', subtitle: '전체 논증 사슬을 한 화면에. 모든 수치는 문서·MCP와 같은 산출물(results_v1.json)에서 읽습니다. 전문은 docs/report.md.' },
  simulator: { title: '시나리오 시뮬레이터', subtitle: '운영규칙 패키지(P0/P1/A/B) 또는 커스텀 레버를 선택하면 파이썬 모형 엔진(/api/solve)이 실시간으로 가격경로를 재계산합니다.' },
};

// ─── 메인 페이지 ────────────────────────────────────────────
export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState('overview');
  const header = TAB_HEADERS[activeTab] ?? TAB_HEADERS.overview;

  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--text-primary)]">
      <Topbar active={activeTab} onNavigate={setActiveTab} />

      <div className="flex min-h-[calc(100vh-56px)] flex-col">
        <main className="ta-page flex-1">
          {/* 동적 헤더 */}
          <div className="ta-page-head">
            <div>
              <div className="eyebrow mb-[6px]">
                K-MSR Operating Rules · {activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}
              </div>
              <h1>{header.title}</h1>
              <p>{header.subtitle}</p>
            </div>
            <div className="ta-tags">
              <span className="ta-tag num">2026–2040</span>
              <span className="ta-tag">KAU price</span>
              <span className="ta-tag num">results v{RESULTS_META.model_version}</span>
            </div>
          </div>

          {/* 탭 콘텐츠 */}
          {activeTab === 'overview' && <OverviewTab />}
          {activeTab === 'mechanism' && <MechanismPanel />}
          {activeTab === 'simulator' && <SimulatorPanel />}
          {activeTab === 'report' && <ReportPanel />}

          <div className="h-6" />
        </main>

        <PageFooter />
      </div>
    </div>
  );
}

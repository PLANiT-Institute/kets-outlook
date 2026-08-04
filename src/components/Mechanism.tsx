'use client';

import { SCEN_LIST, fmtWon, LATEST_KAU_QUOTE } from '@/lib/data';
import { MSR_RESERVE_MT, KMSR_DRAFT_ASSUMPTIONS } from '@/lib/msr';
import { PKG, PACKAGES, AUCTION_SHARE_GOV } from '@/lib/results';
import { FlowDiagram, LambdaBridge } from '@/components/MechanismDiagram';

function Step({ num, title, children }: { num: number; title: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center">
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-[#111827] text-white flex items-center justify-center text-[13px] font-bold" style={{ fontFamily: 'Inter' }}>
          {num}
        </div>
        <div className="w-px flex-1 bg-[#E5E7EB] mt-2" />
      </div>
      <div className="flex-1 pb-8">
        <h4 className="text-[15px] font-semibold text-[#111827] m-0 mb-3">{title}</h4>
        <div className="text-[13px] text-[#4B5563] leading-[1.75] space-y-3">{children}</div>
      </div>
    </div>
  );
}

function FormulaBox({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-[#F9FAFB] border border-[#E5E7EB] rounded-lg px-4 py-3 my-3 text-[12.5px] text-[#111827]" style={{ fontFamily: 'Inter' }}>
      {children}
    </div>
  );
}

function Callout({ type, title, children }: { type: 'info' | 'key' | 'theorem'; title?: string; children: React.ReactNode }) {
  const colors = {
    key:     { bg: '#FEF3C7', border: '#F59E0B', text: '#92400E', title: '#78350F' },
    info:    { bg: '#EFF6FF', border: '#3B82F6', text: '#1E40AF', title: '#1E3A8A' },
    theorem: { bg: '#F0FDF4', border: '#10A574', text: '#065F46', title: '#064E3B' },
  }[type];
  return (
    <div className="rounded-lg px-4 py-3 my-3 text-[12.5px] leading-[1.65]"
         style={{ background: colors.bg, borderLeft: `3px solid ${colors.border}`, color: colors.text }}>
      {title && <div className="font-bold text-[13px] mb-1" style={{ color: colors.title }}>{title}</div>}
      {children}
    </div>
  );
}

function Diagram({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-[#FAFAFA] border border-[#E5E7EB] rounded-lg px-5 py-4 my-3 text-[12px] leading-[1.8] font-mono whitespace-pre" style={{ fontFamily: 'Inter, monospace' }}>
      {children}
    </div>
  );
}

export function MechanismPanel() {
  return (
    <div className="space-y-5">
      {/* ── 전체 개요 ── */}
      <div className="bg-white border border-[#E5E7EB] rounded-[10px] p-6">
        <h2 className="text-[22px] font-bold text-[#111827] m-0 mb-2">K-ETS 배출권 가격 결정 메커니즘</h2>
        <p className="text-[13.5px] text-[#6B7280] m-0 mb-5 leading-[1.65] max-w-[800px]">
          배출권 가격은 법정 총량(Legal cap), 실제 시장 공급량(Effective supply), 기업의 배출 수요(BAU) 사이의 갭을
          감축기술(MACC)이 해소하는 과정에서 결정됩니다.
          아래 도형이 전체 흐름이고, 이어지는 6단계가 각 지점을 풀어 설명합니다.
        </p>

        <FlowDiagram />

        <LambdaBridge year={2026} />

        <div className="space-y-0">

          {/* Step 1 */}
          <Step num={1} title="Legal cap(배출허용총량) — 제도의 총량 기준">
            <p className="m-0">
              정부는 K-ETS 대상 기업들이 배출할 수 있는 <strong>법정 총량(Legal cap)</strong>을 설정합니다.
              이 총량은 배출권거래제의 감축 강도를 나타내는 기준선입니다.
              무상으로 나눠주든, 경매로 팔든, <strong>법정 총량 자체는 동일</strong>합니다.
            </p>
            <FormulaBox>
              Legal cap<sub>t</sub> = 무상할당 대상 물량 + 유상할당 대상 물량 + 예비분
            </FormulaBox>
            <p className="m-0">
              Cap은 5년 단위 할당계획에 따라 매년 줄어듭니다. 이 감소가 배출권의 장기 <strong>희소성</strong>을 만들고,
              가격 상승의 구조적 원인입니다.
            </p>
            <div className="flex gap-3 mt-3">
              {SCEN_LIST.map(s => (
                <div key={s.id} className="flex-1 rounded-lg px-3 py-2.5 text-[11.5px]" style={{ background: s.soft, borderLeft: `3px solid ${s.color}` }}>
                  <div className="font-semibold" style={{ color: s.color }}>{s.ko} ({s.en})</div>
                  <div className="text-[#4B5563] mt-1">{s.desc}</div>
                </div>
              ))}
            </div>
            <p className="m-0 mt-2 text-[11.5px] text-[#6B7280]">
              ※ 논문 v4의 운영규칙 비교(P0/P1/A/B)는 <strong>현행 base cap 공통</strong>으로 수행 —
              cap을 바꾸지 않고 운영규칙만으로 무엇이 달라지는가가 질문입니다.
              중간·이상 cap은 시뮬레이터의 커스텀 레버로 탐색할 수 있습니다.
            </p>
          </Step>

          {/* Step 2 */}
          <Step num={2} title="Effective supply — 가격 형성에 실제 작동하는 공급">
            <p className="m-0">
              가격은 법정 총량보다 한 단계 아래의 <strong>실제 시장 공급량</strong>에 반응합니다.
              K-MSR은 경매 물량을 줄여 예비분으로 이전하거나, 예비분을 방출해 추가 경매를 하는 방식으로 이 공급량을 조정합니다.
            </p>
            <FormulaBox>
              Effective supply<sub>t</sub> = Legal cap<sub>t</sub> + K-MSR 방출<sub>t</sub> − K-MSR 흡수<sub>t</sub><br/>
              Shortfall<sub>t</sub> = BAU<sub>t</sub> − Effective supply<sub>t</sub>
            </FormulaBox>
            <Callout type="key" title="2026년 제도 업데이트 — K-MSR은 법제화 완료, 남은 것은 운영규칙">
              K-MSR 시행령은 2026-04-29 시행되었고, 제4차 할당계획은 시장안정화 용도 예비분을{' '}
              <strong>{MSR_RESERVE_MT.toFixed(1)} Mt</strong>로 설정했습니다.
              이 물량은 배출허용총량 안에 있는 버퍼이며, 가격 또는 수량 기준이 벗어나면 유상할당 계정과 예비분 계정 사이에서 이동합니다.
              최근 KAU 시세는 <strong>{fmtWon(LATEST_KAU_QUOTE.kau_krw)}원</strong>({LATEST_KAU_QUOTE.date})이며,
              감시선 <strong>{fmtWon(KMSR_DRAFT_ASSUMPTIONS.lowPriceKrw)}~{fmtWon(KMSR_DRAFT_ASSUMPTIONS.highPriceKrw)}원</strong>은
              가격범위 공고({KMSR_DRAFT_ASSUMPTIONS.announcementDue}) 전까지의 <strong>draft 가정</strong>입니다.
              본 분석의 <strong style={{ color: PKG.A.color }}>A(가격약속형)</strong>와{' '}
              <strong style={{ color: PKG.B.color }}>B(수량약속형)</strong>는 새로운 제도가 아니라,
              이미 법제화된 K-MSR의 <strong>운영규칙</strong>입니다 —
              A는 <strong>K-MSR 경매보류가격의 운영경로</strong>(기술앵커 회랑, 미유찰 물량 무효화),
              B는 <strong>흡수·무효화 기능의 일정형 운영</strong>(2035 개시 사전공표)입니다.
            </Callout>
            <p className="m-0">
              Effective supply가 줄어들수록 → Shortfall 증가 → 더 많은 감축 필요 → <strong>더 비싼 기술까지 동원</strong> → 가격 상승.
              그래서 K-MSR은 cap을 바꾸지 않고도 단기 가격 신호를 보정할 수 있습니다.
            </p>
          </Step>

          {/* Step 3: 단일시장 정리 */}
          <Step num={3} title="단일시장 정리 — 유상할당과 K-MSR의 역할 분리">
            <Callout type="theorem" title="단일시장 정리 (Single Market Theorem)">
              K-ETS에서 경매시장과 2차시장(거래소)은 <strong>하나의 시장</strong>입니다.
              모든 참여자가 두 시장에 접근 가능하므로, 차익거래에 의해 가격은 수렴합니다.
              따라서 같은 물량이 실제 시장에 공급된다면 배출권이 어떤 경로(무상/경매)로 배분되든,
              <strong>균형가격은 동일</strong>합니다.
            </Callout>

            <p className="m-0"><strong>직관적 설명:</strong></p>

            <Diagram>{
`"무상할당은 공급을 줄이는 것 아닌가?" → 아닙니다.

무상할당 100%일 때:
  ┌ 정부 ─(무상)──→ 기업 A (잉여 50Mt) ─(판매)──→ 시장 ┐
  │                 기업 B (부족 20Mt) ←(구매)──── 시장 ┘│
  │                                                     │
  │  시장 공급 = Cap 전량 (경로: 정부→기업→시장)          │
  └─────────────────────────────────────────────────────┘

유상할당 100%일 때:
  ┌ 정부 ─(경매)──→ 시장 ──→ 기업 A (필요한 만큼 구매) ┐
  │                          기업 B (필요한 만큼 구매)  │
  │                                                    │
  │  시장 공급 = Cap 전량 (경로: 정부→시장→기업)         │
  └────────────────────────────────────────────────────┘

두 경우 모두: 시장의 배출권 총량 = Cap (동일)
             → 가격 = 동일`
            }</Diagram>

            <p className="m-0"><strong>경제학적 근거:</strong></p>
            <ul className="mt-1 space-y-1 ml-4" style={{ listStyleType: 'disc' }}>
              <li>
                <strong>기회비용 원리</strong> — 무상으로 받은 배출권도 시장가격에 팔 수 있으므로,
                보유하는 것의 비용 = 시장가격. 할당방식과 무관하게 기업의 한계의사결정은 동일.
              </li>
              <li>
                <strong>차익거래</strong> — 경매가 ≠ 거래소가이면 차익거래 기회 발생 → 가격 수렴.
                시장이 하나이므로, 가격도 하나.
              </li>
              <li>
                <strong>Coase 정리</strong> — 재산권(배출권)의 초기 배분이 달라도,
                거래비용이 충분히 낮으면 자원의 최종 배분(= 감축량)과 가격은 동일.
              </li>
            </ul>

            <Callout type="key" title="그러면 유상할당 비율과 K-MSR은 무엇을 결정하는가?">
              유상할당 비율은 <strong>경매수입</strong>(정부 세수)과 <strong>비용 분배</strong>(기업 부담)를 결정합니다.
              K-MSR은 실제 경매 공급량을 조정하므로 <strong>effective supply와 가격</strong>에도 영향을 줄 수 있습니다.
              <div className="mt-2 grid grid-cols-2 gap-3">
                <div className="bg-white/60 rounded px-3 py-2">
                  <div className="font-semibold text-[#065F46]">가격을 결정하는 변수</div>
                  <div className="mt-1 text-[#065F46]/80">Legal cap (배출허용총량)</div>
                  <div className="text-[#065F46]/80">K-MSR 경매 공급 조정</div>
                  <div className="text-[#065F46]/80">Effective supply</div>
                  <div className="text-[#065F46]/80">BAU (배출 수요)</div>
                  <div className="text-[#065F46]/80">MACC (감축기술 비용)</div>
                </div>
                <div className="bg-white/60 rounded px-3 py-2">
                  <div className="font-semibold text-[#065F46]">가격에 직접 영향 없는 변수</div>
                  <div className="mt-1 text-[#065F46]/80">무상할당 비율</div>
                  <div className="text-[#065F46]/80">유상/무상 배분 방식</div>
                  <div className="text-[#065F46]/80">경매수입의 사용처</div>
                  <div className="text-[#065F46]/80">경매 수입</div>
                </div>
              </div>
            </Callout>

            <Callout type="info" title="현실 시장에서의 마찰">
              완벽한 시장에서는 위 정리가 정확히 성립합니다. 그러나 현실의 K-ETS에서는:
              (1) 중소기업의 거래 비참여, (2) 유동성 부족, (3) 정보 비대칭, (4) 경매 보류와 예비분 운용 등으로
              effective supply가 달라질 수 있습니다.
              본 모형은 이론적 기준선(frictionless)을 제시하며,
              마찰 효과는 향후 실증 분석으로 보정할 수 있습니다.
            </Callout>
          </Step>

          {/* Step 4 */}
          <Step num={4} title="MACC 곡선 — 어떤 기술이, 어떤 가격에서 도입되는가">
            <p className="m-0">
              각 감축기술은 고유한 비용(원/tCO₂)과 잠재량(MtCO₂/년)을 가집니다.
              시장 가격 P에서 <strong>비용 ≤ P인 기술만 활성화</strong>됩니다.
            </p>
            <FormulaBox>
              균형가격 P*: Σ abatement<sub>i</sub>(P*) = Shortfall<sub>t</sub><br/>
              → MAC<sub>i</sub> ≤ P* 인 모든 기술 i 의 잠재량 합 = BAU<sub>t</sub> − Effective supply<sub>t</sub>
            </FormulaBox>

            <Diagram>{
`비용(원/tCO₂)
  │
  │ ┌─ NCC 전기분해 (e-NCC)          ← 두 번째 헤드라인 문턱 (전력가격 연동)
  │ │
  │ ├─ 수소환원제철 (H₂-DRI)         ← 첫 번째 헤드라인 문턱 (수소가격 연동)
  │ │                                   A의 회랑 앵커 = 이 문턱의 2035 학습조정 비용
  │ ├─ 연료전환·전기화 기술군
  │ │
  │ ├─ 에너지효율                    ← 낮은 가격에서 즉시 도입
  0 ├─
  │ ├─ 음(−)의 비용 기술              ← 하면 돈이 절약됨
  │
  └──────────────────────── 누적 감축량 (Mt)`
            }</Diagram>

            <Callout type="info" title="기술 문턱은 상수가 아니라 경로 (Learning + 투입가격)">
              헤드라인 기술의 문턱은 정적 공학 상수가 아니라 <strong>정부 수소·전력 가격 시나리오</strong>로
              구동되는 학습조정 비용경로입니다. A(가격약속형)의 회랑 앵커는 이 문턱 자체이므로,
              투입가격 시나리오가 어긋나면 <strong>앵커가 문턱과 함께 움직여 자기교정</strong>합니다 —
              이것이 Overview의 &lsquo;결정적 분기&rsquo;가 보여주는 메커니즘입니다.
            </Callout>
          </Step>

          {/* Step 5 */}
          <Step num={5} title="Banking — 미래의 희소성이 오늘의 가격을 결정 (Hotelling)">
            <p className="m-0">
              K-ETS는 배출권 이월(banking)을 허용합니다.
              합리적 기업은 &ldquo;오늘 팔까, 내년에 팔까?&rdquo;를 비교합니다.
            </p>
            <FormulaBox>
              Banking 활성 구간에서: P<sub>t+1</sub> / P<sub>t</sub> = exp(r)<br/>
              r = 무위험금리(3.5%) + 리스크프리미엄(2.0%) = 5.5%/년<br/>
              → 가격이 연 5.5%보다 빨리 오를 것으로 예상 → 저축 (banking)<br/>
              → 현재 공급 감소 → 현재 가격 상승 → 미래 가격과 평탄화
            </FormulaBox>
            <p className="m-0">
              미래에 Cap이 급격히 줄어들 것으로 예상되면, 기업들은 현재 배출권을 저축 →
              현재 시장 공급 감소 → <strong>현재 가격도 상승</strong>.
              이것이 Hotelling 규칙이며, 미래의 정책 신호가 현재 가격에 즉시 반영되는 메커니즘입니다.
            </p>
            <Callout type="key" title="Banking stock ≥ 0 제약">
              차입(미래 배출권 당겨쓰기)은 K-ETS 규정상 불허됩니다.
              Banking 잔고가 0에 도달하면 Hotelling 경로가 종료되고,
              해당 연도부터 매년 독립적 정태균형 가격이 결정됩니다.
              이 전환점에서 가격이 급등할 수 있습니다.
            </Callout>
          </Step>

          {/* Step 6 */}
          <Step num={6} title="재정 흐름 — 유상할당은 정부 기발표 경로 (신규 요구 없음)">
            <p className="m-0">
              가격은 effective supply(Step 2)와 MACC(Step 4)로 결정되었습니다.
              유상할당 비율은 가격을 직접 바꾸지 않지만, <strong>돈이 어떻게 흐르는가</strong>를 결정합니다.
              본 분석의 유상할당은 4개 운영규칙 모두 <strong>정부 기발표 경로(A_gov)</strong> —
              경제전체 유상 비율 <strong>{(AUCTION_SHARE_GOV.y2026 * 100).toFixed(1)}%(2026) →
              {(AUCTION_SHARE_GOV.y2030 * 100).toFixed(1)}%(2030+)</strong> — 를 그대로 사용합니다.
              어떤 운영규칙도 <strong>새로운 경매물량을 요구하지 않습니다</strong>.
            </p>
            <FormulaBox>
              실제 경매 판매량 = Legal cap<sub>t</sub> × a<sub>t</sub>(정부 기발표) − K-MSR 흡수·보류<sub>t</sub><br/>
              경매수입 = 실제 경매 판매량<sub>t</sub> × P*<sub>t</sub><br/>
              하한 방어요건 (A): W = A(P̄) − A(P<sub>realized</sub>) ≤ a<sub>t</sub>·Cap<sub>t</sub> — 기발표 경매물량 한도 내 방어
            </FormulaBox>
            <div className="grid grid-cols-3 gap-3 mt-3">
              <div className="rounded-lg px-3 py-2.5 text-[11.5px]" style={{ background: PKG.P0.soft, borderLeft: `3px solid ${PKG.P0.color}` }}>
                <div className="font-semibold" style={{ color: '#6B7280' }}>P0 무정책</div>
                <div className="text-[#4B5563] mt-1">누적 경매수입<br/><strong>{PACKAGES.P0.cum_auction_rev_trillion.toFixed(1)}조원</strong> (2026–2040)</div>
              </div>
              <div className="rounded-lg px-3 py-2.5 text-[11.5px]" style={{ background: PKG.A.soft, borderLeft: `3px solid ${PKG.A.color}` }}>
                <div className="font-semibold" style={{ color: PKG.A.color }}>A 가격약속형</div>
                <div className="text-[#4B5563] mt-1">누적 경매수입<br/><strong>{PACKAGES.A.cum_auction_rev_trillion.toFixed(1)}조원</strong> · 무효화 없음, 가격이 수입을 늘림</div>
              </div>
              <div className="rounded-lg px-3 py-2.5 text-[11.5px]" style={{ background: PKG.B.soft, borderLeft: `3px solid ${PKG.B.color}` }}>
                <div className="font-semibold" style={{ color: PKG.B.color }}>B 수량약속형</div>
                <div className="text-[#4B5563] mt-1">누적 경매수입<br/><strong>{PACKAGES.B.cum_auction_rev_trillion.toFixed(1)}조원</strong> · 물량 {PACKAGES.B.cum_intake_Mt.toFixed(0)}Mt 무효화의 대가</div>
              </div>
            </div>
          </Step>
        </div>
      </div>

      {/* ── 모형 사양 ── */}
      <div className="bg-white border border-[#E5E7EB] rounded-[10px] p-6">
        <h3 className="text-[15px] font-semibold text-[#111827] m-0 mb-4">모형 사양</h3>
        <div className="grid grid-cols-2 gap-6 text-[12px]">
          <div className="space-y-2.5">
            <div className="text-[#6B7280]"><strong className="text-[#111827]">모형 유형:</strong> 부분균형 (Partial Equilibrium)</div>
            <div className="text-[#6B7280]"><strong className="text-[#111827]">MACC:</strong> Staircase (기술별 이산 비용곡선, bottom-up)</div>
            <div className="text-[#6B7280]"><strong className="text-[#111827]">동학:</strong> Hotelling banking + 비음(non-negativity) 제약</div>
            <div className="text-[#6B7280]"><strong className="text-[#111827]">가격 전달:</strong> λ 레벨-브리지 (정태 ↔ Hotelling, H1-2026 리프라이싱 역산 앵커)</div>
            <div className="text-[#6B7280]"><strong className="text-[#111827]">기술 문턱:</strong> 정부 수소·전력 가격 시나리오 연동 학습조정 비용경로 (H₂-DRI · e-NCC)</div>
          </div>
          <div className="space-y-2.5">
            <div className="text-[#6B7280]"><strong className="text-[#111827]">부문:</strong> 6개 (발전·철강·석유화학·시멘트·정유·기타)</div>
            <div className="text-[#6B7280]"><strong className="text-[#111827]">기간:</strong> 2026–2040 (4차~6차 할당계획 기간)</div>
            <div className="text-[#6B7280]"><strong className="text-[#111827]">비교 대상:</strong> K-MSR 운영규칙 4종 (P0 무정책 · P1 시행령 초안 · A 가격약속형 · B 수량약속형)</div>
            <div className="text-[#6B7280]"><strong className="text-[#111827]">유상할당:</strong> 정부 기발표 경로(A_gov) 공통 — 신규 경매물량 요구 없음</div>
            <div className="text-[#6B7280]"><strong className="text-[#111827]">공급 보정:</strong> K-MSR 흡수·보류·무효화 → effective supply 반영, 하한은 1차시장 overlay</div>
            <div className="text-[#6B7280]"><strong className="text-[#111827]">가격 결정:</strong> 단일시장 정리 — 유상할당 비율은 가격에 직접 무관, K-MSR은 공급을 통해 가격에 영향</div>
          </div>
        </div>
      </div>
    </div>
  );
}

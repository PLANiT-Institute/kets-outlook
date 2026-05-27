'use client';

import { SCEN, SCEN_LIST } from '@/lib/data';

function Step({ num, title, children }: { num: number; title: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-4">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-[#111827] text-white flex items-center justify-center text-[13px] font-bold" style={{ fontFamily: 'Inter' }}>
        {num}
      </div>
      <div className="flex-1 pb-6 border-b border-[#F3F4F6]">
        <h4 className="text-[14px] font-semibold text-[#111827] m-0 mb-2">{title}</h4>
        <div className="text-[12.5px] text-[#4B5563] leading-[1.7] space-y-2">{children}</div>
      </div>
    </div>
  );
}

function FormulaBox({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-[#F9FAFB] border border-[#E5E7EB] rounded-lg px-4 py-3 my-2 font-mono text-[12px] text-[#111827]" style={{ fontFamily: 'Inter' }}>
      {children}
    </div>
  );
}

function Callout({ type, children }: { type: 'info' | 'key'; children: React.ReactNode }) {
  const colors = type === 'key'
    ? { bg: '#FEF3C7', border: '#F59E0B', text: '#92400E' }
    : { bg: '#EFF6FF', border: '#3B82F6', text: '#1E40AF' };
  return (
    <div className="rounded-lg px-4 py-3 my-3 text-[12px] leading-[1.6]"
         style={{ background: colors.bg, borderLeft: `3px solid ${colors.border}`, color: colors.text }}>
      {children}
    </div>
  );
}

export function MechanismPanel() {
  return (
    <div className="space-y-5">
      {/* 개요 */}
      <div className="bg-white border border-[#E5E7EB] rounded-[10px] p-6">
        <h2 className="text-[20px] font-bold text-[#111827] m-0 mb-1">K-ETS 가격 결정 메커니즘</h2>
        <p className="text-[13px] text-[#6B7280] m-0 mb-4">
          배출권 가격은 수요(BAU 배출량)와 공급(Cap)의 차이를 감축기술(MACC)이 해소하는 과정에서 결정됩니다.
        </p>

        <div className="space-y-5">
          <Step num={1} title="정부가 Cap(배출허용총량)을 설정">
            <p className="m-0">
              K-ETS는 5년 단위 할당계획에 따라 연간 배출허용총량(Cap)을 설정합니다.
              Cap은 시간이 지날수록 줄어들며, 이것이 <strong>배출권의 희소성</strong>을 만듭니다.
            </p>
            <FormulaBox>
              공급(Supply) = Cap<sub>t</sub> (연도별 배출허용총량)
            </FormulaBox>
            <p className="m-0">
              현재 모형에서 3개 시나리오는 각각 다른 Cap 감축 속도를 가정합니다:
            </p>
            <div className="flex gap-3 mt-2">
              {SCEN_LIST.map(s => (
                <div key={s.id} className="flex-1 rounded-md px-3 py-2 text-[11px]" style={{ background: s.soft, borderLeft: `3px solid ${s.color}` }}>
                  <div className="font-semibold" style={{ color: s.color }}>{s.ko} ({s.en})</div>
                  <div className="text-[#4B5563] mt-0.5">{s.desc}</div>
                </div>
              ))}
            </div>
          </Step>

          <Step num={2} title="기업은 BAU 배출을 줄이거나 배출권을 구매">
            <p className="m-0">
              기업의 BAU(Business-As-Usual) 배출량이 Cap을 초과하면, 그 차이만큼
              <strong> 감축하거나(abate)</strong> <strong>배출권을 시장에서 구매</strong>해야 합니다.
            </p>
            <FormulaBox>
              Shortfall(감축수요) = BAU<sub>t</sub> − Cap<sub>t</sub>
            </FormulaBox>
            <Callout type="key">
              <strong>Coase 정리:</strong> 무상할당 비율(유상/무상)은 균형가격에 영향을 주지 않습니다.
              무상으로 받은 배출권도 기회비용(= 시장가격)이 있으므로, 총 공급량(Cap)만이 가격을 결정합니다.
              무상할당은 &ldquo;누가 돈을 내는가&rdquo;(경매수입)에만 영향.
            </Callout>
          </Step>

          <Step num={3} title="MACC 곡선이 균형가격을 결정">
            <p className="m-0">
              각 감축기술은 고유한 비용(원/tCO₂)과 잠재량(Mt)을 가집니다.
              가격 P에서 비용이 P 이하인 기술만 활성화됩니다.
            </p>
            <FormulaBox>
              균형가격 P*: Σ abatement(P*) = Shortfall<br/>
              → 비용 ≤ P*인 기술의 잠재량 합 = BAU − Cap
            </FormulaBox>
            <p className="m-0">
              Shortfall이 클수록(Cap이 빡빡할수록) → 더 비싼 기술까지 활성화해야 하므로 → <strong>가격 상승</strong>.
            </p>
            <Callout type="info">
              <strong>학습곡선:</strong> 재생에너지·수소 등의 비용은 시간이 지나면서 하락합니다.
              적극적 정책(ideal) 시나리오에서는 대규모 보급으로 학습곡선이 가속 → 같은 가격에서 더 많은 감축 가능 → 가격 상승 억제.
            </Callout>
          </Step>

          <Step num={4} title="Banking이 미래 가격을 현재로 전파 (Hotelling)">
            <p className="m-0">
              K-ETS는 배출권 이월(banking)을 허용합니다. 합리적 기업은 현재 가격과 미래 기대가격을 비교하여 최적 시점에 거래합니다.
            </p>
            <FormulaBox>
              Banking 구간에서: P<sub>t</sub> = P<sub>0</sub> × exp(r × t)<br/>
              r = 무위험금리(3.5%) + 리스크프리미엄(2.0%) = 5.5%
            </FormulaBox>
            <p className="m-0">
              미래에 Cap이 빡빡해질 것으로 예상되면, 기업들은 현재 배출권을 저축 → 현재 공급 감소 → <strong>현재 가격도 상승</strong>.
              이것이 Hotelling 규칙이며, 미래의 희소성이 현재 가격에 반영되는 메커니즘입니다.
            </p>
            <Callout type="key">
              <strong>Banking stock ≥ 0 제약:</strong> 차입(미래 배출권 당겨쓰기)은 불허.
              Banking 잔고가 0에 도달하면 Hotelling 경로가 종료되고, 해당 연도부터 매년 독립적 균형가격이 결정됩니다.
            </Callout>
          </Step>

          <Step num={5} title="재정 분석: 무상할당이 결정하는 것들">
            <p className="m-0">
              가격은 Cap으로 결정되지만, <strong>경매수입</strong>과 <strong>기업 비용 분배</strong>는 무상할당 비율에 따라 달라집니다.
            </p>
            <FormulaBox>
              경매수입 = Cap<sub>t</sub> × 유상비율 × 가격<sub>t</sub><br/>
              기업 부담 = (BAU − 자체감축 − 무상할당) × 가격
            </FormulaBox>
            <div className="flex gap-3 mt-2">
              <div className="flex-1 bg-[#F9FAFB] rounded px-3 py-2 text-[11px]">
                <div className="font-semibold text-[#111827]">가격에 영향</div>
                <div className="text-[#6B7280] mt-0.5">BAU, Cap, MACC 기술</div>
              </div>
              <div className="flex-1 bg-[#F9FAFB] rounded px-3 py-2 text-[11px]">
                <div className="font-semibold text-[#111827]">가격에 무관</div>
                <div className="text-[#6B7280] mt-0.5">무상할당 비율, 유상/무상 배분</div>
              </div>
            </div>
          </Step>
        </div>
      </div>

      {/* 모형 사양 */}
      <div className="bg-white border border-[#E5E7EB] rounded-[10px] p-6">
        <h3 className="text-[14px] font-semibold text-[#111827] m-0 mb-3">모형 사양</h3>
        <div className="grid grid-cols-2 gap-4 text-[11.5px]">
          <div className="space-y-2">
            <div className="text-[#6B7280]"><strong className="text-[#111827]">모형 유형:</strong> 부분균형 (Partial Equilibrium)</div>
            <div className="text-[#6B7280]"><strong className="text-[#111827]">MACC:</strong> Staircase (기술별 이산 비용곡선)</div>
            <div className="text-[#6B7280]"><strong className="text-[#111827]">동학:</strong> Hotelling banking + 비음 제약</div>
            <div className="text-[#6B7280]"><strong className="text-[#111827]">할인율:</strong> r = 5.5% (무위험 3.5% + 리스크 2.0%)</div>
          </div>
          <div className="space-y-2">
            <div className="text-[#6B7280]"><strong className="text-[#111827]">부문:</strong> 6개 (발전·철강·석유화학·시멘트·정유·기타)</div>
            <div className="text-[#6B7280]"><strong className="text-[#111827]">기술:</strong> 25개 (CCUS·원전 제외)</div>
            <div className="text-[#6B7280]"><strong className="text-[#111827]">기간:</strong> 2026–2040 (3개 할당계획 기간)</div>
            <div className="text-[#6B7280]"><strong className="text-[#111827]">국제감축:</strong> Smoothed step (P &gt; EUA → 10% 상한)</div>
          </div>
        </div>
      </div>
    </div>
  );
}

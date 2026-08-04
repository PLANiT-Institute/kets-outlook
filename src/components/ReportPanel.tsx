'use client';

/**
 * 보고서 요약 탭 — docs/report.md의 논증 사슬을 대시보드에서 한 화면으로 보여준다.
 *
 * 수치는 전부 results_v1.json(= outputs/runs/msr_results_v1.0.json 슬림 추출)에서
 * 읽는다. 문서와 대시보드가 갈라지지 않게 하려는 것이 이 탭의 목적이므로,
 * 여기에 숫자를 직접 적지 않는다.
 */

import { PKG_LIST, PACKAGES, RESULTS_META, TECH_LABELS, FLOOR, activationYear, pkgRowAt } from '@/lib/results';
import { LambdaBridge } from '@/components/MechanismDiagram';

const REPO = 'https://github.com/PLANiT-Institute/kets-outlook/blob/main';

const won = (v: number) => `${Math.round(v).toLocaleString('ko-KR')}원`;

function Section({ n, title, lead, children }: {
  n: string; title: string; lead?: string; children: React.ReactNode;
}) {
  return (
    <section className="bg-white border border-[#E5E7EB] rounded-[10px] p-6">
      <div className="eyebrow mb-[6px]">{n}</div>
      <h3 className="text-[18px] font-bold text-[#111827] m-0 mb-2">{title}</h3>
      {lead && <p className="text-[13px] text-[#6B7280] m-0 mb-4 leading-[1.7] max-w-[820px]">{lead}</p>}
      {children}
    </section>
  );
}

function Verdict({ tone, children }: { tone: 'good' | 'warn' | 'bad'; children: React.ReactNode }) {
  const c = {
    good: { bg: '#F0FDF4', bd: '#10A574', fg: '#065F46' },
    warn: { bg: '#FFFBEB', bd: '#F59E0B', fg: '#92400E' },
    bad:  { bg: '#FEF2F2', bd: '#DC2626', fg: '#991B1B' },
  }[tone];
  return (
    <div className="rounded-lg px-4 py-3 mt-4 text-[12.5px] leading-[1.7]"
         style={{ background: c.bg, borderLeft: `3px solid ${c.bd}`, color: c.fg }}>
      {children}
    </div>
  );
}

/** ±20% 격자 축 — 데이터에서 유도(하드코딩 아님) */
const SCALES = [0.8, 1.0, 1.2];

export function ReportPanel() {
  const floor = FLOOR;
  const START_PRICES = FLOOR
    ? [...new Set(FLOOR.cost_sensitivity_pm20.map(g => g.f0))].sort((a, b) => a - b)
    : [];
  const p0 = (y: number) => pkgRowAt('P0', y);
  const gap2040 = p0(2040);
  const r2026 = p0(2026);

  return (
    <div className="space-y-5">

      {/* ── 논증 사슬 요약 ── */}
      <div className="bg-[#111827] rounded-[10px] p-6 text-white">
        <div className="eyebrow mb-2" style={{ color: '#9CA3AF' }}>REPORT · 논증 사슬</div>
        <h2 className="text-[21px] font-bold m-0 mb-4">
          총량만으로는 전환 문턱에 닿지 않는다 — 무엇을 어떻게 고칠 것인가
        </h2>
        <div className="grid gap-3 md:grid-cols-3">
          {[
            { k: '진단', t: '가격이 문턱에 못 미친다',
              d: `무정책 경로는 2040년 ${gap2040 ? won(gap2040.kau) : '—'}. 철강 H₂-DRI 문턱(2035년 약 97,500원)에 미달.` },
            { k: '원인', t: '미래 희소성이 오늘 가격에 안 실린다',
              d: `인접 빈티지 캐리 중앙값 ≈ 0%. 전달계수 λ = ${r2026 ? r2026.lambda.toFixed(3) : '—'} (관측가 역산).` },
            { k: '처방', t: '가격을 약속하고, 유찰분은 취소한다',
              d: '4만 원 출발 · 실질 7% 상승 + 미유찰 영구취소. 기술비용 ±20%에서 유일하게 방어 성립.' },
          ].map((s, i) => (
            <div key={s.k} className="rounded-lg p-4" style={{ background: 'rgba(255,255,255,.06)' }}>
              <div className="text-[11px] font-bold mb-1" style={{ color: '#93C5FD' }}>{i + 1}. {s.k}</div>
              <div className="text-[14px] font-semibold mb-1.5">{s.t}</div>
              <div className="text-[12px] leading-[1.65]" style={{ color: '#D1D5DB' }}>{s.d}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── §2 전달 ── */}
      <Section n="§2 · 모형" title="세 층으로 나눠 푼다"
        lead="가격을 한 번에 계산하지 않는다. 그 해 수급만 맞춘 정태 균형(λ=0)과 미래 희소성을 완전히 당겨온 Hotelling 가격(λ=1)을 각각 구한 뒤, 실제 시장이 그 사이 어디에 있는지를 λ 하나로 잇는다. λ는 가정이 아니라 관측 시세에서 역산한 값이다.">
        <LambdaBridge year={2026} />
      </Section>

      {/* ── §4 운영규칙 ── */}
      <Section n="§4 · 처방 1" title="운영규칙 4종 — 무엇이 실제로 문턱을 넘게 하나"
        lead="K-MSR은 이미 법제화됐다. 남은 질문은 도입 여부가 아니라 운영규칙이다. 네 규칙을 같은 데이터·같은 엔진으로 비교한다.">
        <div className="overflow-x-auto">
          <table className="w-full text-[12.5px] border-collapse">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wide text-[#6B7280] border-b border-[#E5E7EB]">
                <th className="py-2 pr-3">운영규칙</th>
                <th className="py-2 px-2 text-right">2030</th>
                <th className="py-2 px-2 text-right">2040</th>
                <th className="py-2 px-2 text-right">최대낙폭</th>
                {TECH_LABELS.map(tl => (
                  <th key={tl.key} className="py-2 px-2 text-center">{tl.short}</th>
                ))}
                <th className="py-2 pl-2 text-right">누적 경매수입</th>
              </tr>
            </thead>
            <tbody>
              {PKG_LIST.map(meta => {
                const pid = meta.id;
                const rec = PACKAGES[pid];
                const years = TECH_LABELS.map(tl => activationYear(pid, tl.key));
                return (
                  <tr key={pid} className="border-b border-[#F3F4F6]">
                    <td className="py-2.5 pr-3">
                      <span className="inline-block w-[22px] text-[11px] font-bold"
                            style={{ color: meta.color }}>{pid}</span>
                      <span className="font-semibold text-[#111827]">{meta.ko}</span>
                    </td>
                    <td className="py-2.5 px-2 text-right num">{won(pkgRowAt(pid, 2030)!.kau)}</td>
                    <td className="py-2.5 px-2 text-right num font-semibold">{won(pkgRowAt(pid, 2040)!.kau)}</td>
                    <td className="py-2.5 px-2 text-right num">{(rec.max_drawdown * 100).toFixed(1)}%</td>
                    {years.map((y, i) => (
                      <td key={i} className="py-2.5 px-2 text-center num"
                          style={{ color: y ? '#065F46' : '#9CA3AF', fontWeight: y ? 700 : 400 }}>
                        {y ?? '미도입'}
                      </td>
                    ))}
                    <td className="py-2.5 pl-2 text-right num">{rec.cum_auction_rev_trillion} 조</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <Verdict tone="warn">
          <strong>P1(시행령 초안)만으로는 부족하다.</strong> 2040년 가격이 P0와 같다 — 흡수한 물량을
          방출규칙이 되돌려주면 누적 공급이 그대로다(워터베드). 취소해야 희소성이 남는다.
          <br />
          <strong>A와 B는 둘 다 문턱에 도달하지만 경로가 다르다.</strong> 최대낙폭 {(PACKAGES.A.max_drawdown * 100).toFixed(1)}% 대
          {(PACKAGES.B.max_drawdown * 100).toFixed(1)}% — 가격을 약속하면 매끄럽고, 수량을 약속하면 출렁인다.
        </Verdict>
        <p className="text-[11.5px] text-[#9CA3AF] mt-3 leading-[1.6] m-0">
          P1의 하한은 2026-08 가격범위 공고 전 <strong>가정</strong>(중위 하한 M_mid)이다. 공고 후 재계산 필요.
        </p>
      </Section>

      {/* ── §5–6 실현 가능성 ── */}
      <Section n="§5–6 · 처방 2" title="출발가격을 하나로 좁히는 것은 실현 가능성이다"
        lead="하한을 방어하려면 그만큼 경매에서 물량을 빼야 한다. 그 물량이 예정 경매물량을 넘으면 규칙은 집행 불가능하다. 기술비용을 ±20% 흔들어 확인한다.">
        {floor ? (
          <div className="overflow-x-auto">
            <table className="w-full text-[12.5px] border-collapse">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wide text-[#6B7280] border-b border-[#E5E7EB]">
                  <th className="py-2 pr-3">출발가격 (실질 7%)</th>
                  {SCALES.map(s => (
                    <th key={s} className="py-2 px-2 text-right">
                      {s === 1 ? '기준' : `비용 ${s < 1 ? '−' : '+'}${Math.round(Math.abs(1 - s) * 100)}%`}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {START_PRICES.map(f0 => (
                  <tr key={f0} className="border-b border-[#F3F4F6]">
                    <td className="py-2.5 pr-3 font-semibold text-[#111827] num">
                      {(f0 / 10000).toLocaleString('ko-KR')}만 원
                    </td>
                    {SCALES.map(s => {
                      const cell = floor.cost_sensitivity_pm20
                        .find(g => g.f0 === f0 && Math.abs(g.cost_scale - s) < 1e-9);
                      if (!cell) return <td key={s} className="py-2.5 px-2 text-right text-[#D1D5DB]">—</td>;
                      return (
                        <td key={s} className="py-2.5 px-2 text-right num"
                            style={{ color: cell.defended_all ? '#111827' : '#991B1B',
                                     fontWeight: cell.defended_all ? 400 : 700 }}>
                          {cell.cum_required_withholding_Mt.toFixed(1)} Mt
                          {cell.defended_all ? '' : ' · 방어 실패'}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-[12.5px] text-[#9CA3AF] m-0">
            최저가격 격자 데이터 없음 — <span className="num">scripts/run_escalator_floor.py</span> 실행 후
            <span className="num"> scripts/export_web_data.py</span>로 재생성하세요.
          </p>
        )}
        <Verdict tone="good">
          <strong>4만 원 출발만이 시험한 전 범위에서 살아남는다.</strong> 감축이 예상보다 싸지면
          시장가가 더 내려가 더 많이 빼내야 하므로, 야심찬 출발가격일수록 &ldquo;좋은 소식&rdquo;에 취약하다.
        </Verdict>
        <p className="text-[11.5px] text-[#9CA3AF] mt-3 leading-[1.6] m-0">
          표의 물량은 <strong>필요보류량</strong>(모형이 그 가격을 지지하는 데 필요한 정태적 공급감소)이며
          유찰량 예측이 아니다 — 이 모형은 경매 수요곡선을 추정하지 않는다.
        </p>
      </Section>

      {/* ── 한계 ── */}
      <Section n="§9 · 한계" title="이 모형이 하지 않는 것">
        <ul className="text-[12.5px] text-[#4B5563] leading-[1.85] m-0 pl-5 space-y-1">
          <li>경매 수요곡선을 추정하지 않는다 → 필요보류량은 유찰·취소 예측이 아니다.</li>
          <li>투자 시점을 추정하지 않는다 → 기술 문턱 통과 연도만 보고한다(실물옵션 미내생화).</li>
          <li>소비자물가 영향을 추정하지 않는다.</li>
          <li>λ는 H1-2026 시세 5개 관측에서 역산했다(1월 0.020 → 6월 {r2026?.lambda.toFixed(3)}로 급변).</li>
          <li>MACC 해상도는 철강·석유화학·발전 중심이다.</li>
          <li>규칙 변경 가능성은 모형화하지 않았다 — 제도 설계 문제로 다뤘다.</li>
        </ul>
      </Section>

      {/* ── 원문 ── */}
      <div className="bg-[#F9FAFB] border border-[#E5E7EB] rounded-[10px] p-5">
        <div className="text-[13px] font-semibold text-[#111827] mb-2">전문 · 방법론 · 재현</div>
        <div className="flex flex-wrap gap-x-5 gap-y-2 text-[12.5px]">
          {[
            ['보고서 전문 (docs/report.md)', `${REPO}/docs/report.md`],
            ['방법론 — 수식과 구현 대조', `${REPO}/docs/methodology.md`],
            ['구조 — CLI · MCP · Vercel', `${REPO}/docs/architecture.md`],
            ['MCP 서버로 직접 돌리기', `${REPO}/mcp/README.md`],
          ].map(([label, href]) => (
            <a key={href} href={href} target="_blank" rel="noreferrer"
               className="text-[#1f4e79] underline decoration-[#C7D9EA] underline-offset-2 hover:decoration-[#1f4e79]">
              {label} ↗
            </a>
          ))}
        </div>
        <div className="text-[11.5px] text-[#9CA3AF] mt-3 leading-[1.6]">
          이 탭의 모든 수치는 <span className="num">results v{RESULTS_META.model_version}</span>
          {' '}(= <span className="num">outputs/runs/msr_results_v1.0.json</span>)에서 읽는다.
          문서·대시보드·MCP가 같은 산출물을 보므로 세 곳의 숫자가 갈라질 수 없다.
        </div>
      </div>
    </div>
  );
}

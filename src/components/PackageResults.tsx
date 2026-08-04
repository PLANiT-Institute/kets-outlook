'use client';

/**
 * 논문 v4 정적 결과(Overview) 컴포넌트 — results_v1.json 기반.
 *
 * K-MSR(법제화 제도)의 운영규칙 4종 비교:
 *   P0 무정책 · P1 시행령 초안대로 · A 가격약속형(경매보류가격 운영경로) ·
 *   B 수량약속형(흡수·무효화 기능의 일정형 운영).
 * 모든 수치는 outputs/runs/msr_results_v1.0.json의 빌드타임 추출본에서 로드.
 */

import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, ReferenceLine,
} from 'recharts';
import {
  PACKAGES, PKG, PKG_LIST, PACKAGE_PRICE_PATH, SENSITIVITY_ROWS,
  P1_WATERBED, activationYear, pkgRowAt, type PackageId,
} from '@/lib/results';
import { fmtWon, fmtWonK } from '@/lib/data';

const GRID = '#EEF0F2';
const AXIS = '#9CA3AF';
const TICK = { fontSize: 10.5, fontFamily: 'Inter', fill: AXIS };
const TOOLTIP_STYLE = {
  fontSize: 11, borderRadius: 8,
  border: '1px solid #E5E7EB',
  boxShadow: '0 4px 16px rgba(0,0,0,.06)',
  fontFamily: "'Pretendard', 'Inter', sans-serif",
};

const h2Year = (pid: PackageId) => activationYear(pid, 'H₂-DRI');
const enccYear = (pid: PackageId) => activationYear(pid, 'e-cracker');
const pct = (v: number) => (v * 100).toFixed(1) + '%';

// ─── 1. 패키지 가격 비교 차트 (논문 fig4 형식, EUA 없음) ─────
export function PackagePriceChart({ height = 380 }: { height?: number }) {
  const aTarget = h2Year('A');
  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={PACKAGE_PRICE_PATH} margin={{ top: 12, right: 16, left: 4, bottom: 4 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="year" stroke={AXIS} tick={TICK} tickLine={false} />
          <YAxis stroke={AXIS} tick={TICK} tickLine={false} axisLine={false} tickFormatter={fmtWonK} />
          <Tooltip contentStyle={TOOLTIP_STYLE}
                   formatter={(v: unknown) => fmtWon(Math.round(Number(v ?? 0))) + ' 원'}
                   labelFormatter={(l) => l + '년'} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {aTarget && (
            <ReferenceLine x={aTarget} stroke="#D1D5DB" strokeDasharray="2 4"
              label={{ value: `H₂-DRI 문턱 (${aTarget})`, fontSize: 9.5, fill: '#9CA3AF', position: 'insideTopLeft' }} />
          )}
          <Line dataKey="floorA" name="A 경매보류가격 회랑" stroke={PKG.A.color}
                strokeWidth={1.2} strokeDasharray="3 3" dot={false} />
          <Line dataKey="P0" name={`P0 ${PKG.P0.ko}`} stroke={PKG.P0.color}
                strokeWidth={1.8} strokeDasharray={PKG.P0.dash} dot={false} />
          <Line dataKey="P1" name={`P1 ${PKG.P1.ko}`} stroke={PKG.P1.color}
                strokeWidth={1.8} strokeDasharray={PKG.P1.dash} dot={false} />
          <Line dataKey="B" name={`B ${PKG.B.ko}`} stroke={PKG.B.color} strokeWidth={2.2} dot={false} />
          <Line dataKey="A" name={`A ${PKG.A.ko}`} stroke={PKG.A.color} strokeWidth={2.6} dot={false} />
        </LineChart>
      </ResponsiveContainer>
      <p className="text-[11px] text-[#6B7280] leading-[1.6] mt-2 mb-0">
        중심 시나리오에서 두 약속형(A·B)은 근사쌍둥이 — 2030년 가격차 {(() => {
          const a = pkgRowAt('A', 2030)?.kau ?? 0;
          const b = pkgRowAt('B', 2030)?.kau ?? 0;
          return fmtWon(Math.abs(a - b));
        })()}원.
        P1(시행령 초안)은 {P1_WATERBED && <>2031년 <strong>−{(P1_WATERBED.dropPct * 100).toFixed(0)}%</strong> 가격붕락(waterbed)</>} 후
        2040년 P0에 수렴 — 흡수한 것을 방출규칙이 되돌려준다.
      </p>
    </div>
  );
}

// ─── 2. 헤드라인 비교 테이블 ─────────────────────────────────
export function HeadlineTable() {
  const YEARS = [2030, 2035, 2040];
  return (
    <div className="overflow-x-auto">
      <table className="ta-data-table">
        <thead>
          <tr>
            <th>운영규칙 <span className="text-[var(--text-muted)] font-normal">Operating rule</span></th>
            {YEARS.map(y => <th key={y} className="text-right">{y} 가격</th>)}
            <th className="text-center">H₂-DRI</th>
            <th className="text-center">e-NCC</th>
            <th className="text-right">방어여유(최소)</th>
            <th className="text-right">최대 낙폭</th>
            <th className="text-right">무효화 물량</th>
            <th className="text-right">누적 경매수입</th>
          </tr>
        </thead>
        <tbody>
          {PKG_LIST.map(p => {
            const rec = PACKAGES[p.id];
            const h2 = h2Year(p.id);
            const encc = enccYear(p.id);
            const isCorridor = rec.meta.floor_id === 'corridor';
            return (
              <tr key={p.id} style={p.id === 'A' ? { background: 'var(--card-soft)' } : undefined}>
                <td>
                  <span className="inline-flex items-center gap-[6px]">
                    <span className="w-2 h-2 rounded-sm" style={{ background: p.color }} />
                    <strong>{p.id}</strong> {p.ko}
                    <span className="text-[var(--text-muted)] text-[0.85em]">{p.en}</span>
                  </span>
                </td>
                {YEARS.map(y => (
                  <td key={y} className="num text-right">{fmtWon(pkgRowAt(p.id, y)?.kau ?? 0)}</td>
                ))}
                <td className="num text-center">{h2 ?? '—'}</td>
                <td className="num text-center">{encc ?? '—'}</td>
                <td className="num text-right">{isCorridor ? pct(rec.min_headroom) : '해당없음'}</td>
                <td className="num text-right">{pct(rec.max_drawdown)}</td>
                <td className="num text-right">{rec.cum_intake_Mt > 0 ? `${rec.cum_intake_Mt.toFixed(0)} Mt` : '—'}</td>
                <td className="num text-right">{rec.cum_auction_rev_trillion.toFixed(1)} 조원</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="text-[10.5px] text-[#9CA3AF] leading-[1.6] mt-2 mb-0 px-1">
        가격 = 실현경로(λ hold) 원/tCO₂ · 방어여유 = 경매물량 대비 하한방어 후 잔여용량(회랑 규칙에만 해당) ·
        최대 낙폭 = peak-to-trough · 무효화 물량 = 흡수·전량취소 누계 · 유상할당은 4개 규칙 모두 정부 기발표 경로(A_gov) 공통.
      </p>
    </div>
  );
}

// ─── 3. 결정적 분기 — 수소×전력 비용 민감도 미니테이블 ────────
export function DecisiveBranchTable() {
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="ta-data-table">
          <thead>
            <tr>
              <th>수소가격</th>
              <th>전력가격</th>
              <th className="text-center" style={{ color: PKG.A.color }}>A · H₂-DRI</th>
              <th className="text-center" style={{ color: PKG.A.color }}>A · 방어여유</th>
              <th className="text-center" style={{ color: PKG.B.color }}>B · H₂-DRI</th>
            </tr>
          </thead>
          <tbody>
            {SENSITIVITY_ROWS.map(r => {
              const decisive = r.h2Conservative;
              return (
                <tr key={r.key} style={decisive ? { background: '#FEF3C7' } : undefined}>
                  <td>{decisive ? <strong>{r.h2Label}</strong> : r.h2Label}</td>
                  <td>{r.elecLabel}</td>
                  <td className="num text-center" style={{ color: PKG.A.color, fontWeight: 600 }}>
                    {r.A.h2_dri ?? '—'}{decisive && r.A.h2_dri ? ' 유지' : ''}
                  </td>
                  <td className="num text-center">{pct(r.A.min_headroom)}</td>
                  <td className="num text-center"
                      style={r.B.h2_dri == null ? { color: '#DC2626', fontWeight: 700 } : { color: PKG.B.color }}>
                    {r.B.h2_dri ?? '상실'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-[#6B7280] leading-[1.65] mt-2 mb-0">
        <strong>결정적 분기:</strong> 보수적 수소가격에서 A(가격약속형)는 앵커가 문턱 자체이므로{' '}
        <strong style={{ color: PKG.A.color }}>자기교정</strong>해 H₂-DRI {(() => {
          const c = SENSITIVITY_ROWS.find(r => r.h2Conservative && !r.elecConservative);
          return c?.A.h2_dri ?? '';
        })()}년을 유지하지만, B(수량약속형)는 비용이 어긋난 세계에 맞춰진 수량약속이라{' '}
        <strong className="text-[#DC2626]">철강 문턱을 통째로 놓친다</strong>.
        한국의 지배적 불확실성은 비용측(수소·전력 투입가격) — 가격도구가 수량도구를 지배하는 구도다
        (Weitzman 1974; Parsons–Taschini 2013).
      </p>
    </div>
  );
}

// ─── 4. KPI 카드 (v4 헤드라인) ──────────────────────────────
function KpiCard({ label, en, value, sub, color, feature }: {
  label: string; en: string; value: string; sub: string; color?: string; feature?: boolean;
}) {
  return (
    <div className={`ta-kpi-card ${feature ? 'feature' : ''}`}>
      <div className="ta-kpi-label">{label}</div>
      <div className="text-[10px] text-[var(--text-muted)] mt-[1px] num">{en}</div>
      <div className="ta-kpi-value mt-2 text-[20px]" style={color ? { color } : undefined}>{value}</div>
      <div className={`text-[10.5px] mt-1 leading-[1.5] ${feature ? 'text-[#AEB9CC]' : 'text-[var(--text-secondary)]'}`}>
        {sub}
      </div>
    </div>
  );
}

export function PackageKpiCards() {
  const a = PACKAGES.A;
  const p0 = PACKAGES.P0;
  const h2 = h2Year('A');
  const encc = enccYear('A');
  return (
    <div className="ta-kpis">
      <KpiCard feature
        label="A · 기술 활성화" en="Rule A activation"
        value={`${h2 ?? '—'} · ${encc ?? '—'}`}
        sub={`수소환원제철(H₂-DRI) ${h2 ?? '—'} · NCC 전기분해(e-NCC) ${encc ?? '—'} — 현행 cap·기발표 유상경로 그대로`} />
      <KpiCard
        label="A · 방어여유 (최소)" en="Min. defense headroom"
        value={pct(a.min_headroom)} color={PKG.A.color}
        sub="회랑 하한 방어 후 남는 경매물량 비중 — 전 연도 방어 성공" />
      <KpiCard
        label="A · 누적 경매수입" en="Cum. auction revenue"
        value={`${a.cum_auction_rev_trillion.toFixed(1)} 조원`} color={PKG.A.color}
        sub={`무정책 P0 ${p0.cum_auction_rev_trillion.toFixed(1)}조원 대비 +${(a.cum_auction_rev_trillion - p0.cum_auction_rev_trillion).toFixed(1)}조원 (2026–2040)`} />
      <KpiCard
        label="P1 · 2031 가격붕락" en="Draft decree waterbed"
        value={P1_WATERBED ? `−${(P1_WATERBED.dropPct * 100).toFixed(0)}%` : '—'} color="#DC2626"
        sub={P1_WATERBED
          ? `${fmtWon(P1_WATERBED.from)} → ${fmtWon(P1_WATERBED.to)}원 — 초안 방출규칙이 만드는 waterbed`
          : ''} />
    </div>
  );
}

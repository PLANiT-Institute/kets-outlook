'use client';

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ResponsiveContainer, BarChart, Bar, LabelList,
  AreaChart, Area, ComposedChart,
} from 'recharts';
import {
  SCEN, SCEN_LIST, EUA_COLOR,
  PRICE_PATH, GAP_PATH, CBAM_2030, KPI,
  BANKING_PATH, REVENUE_PATH, ANNUAL_REVENUE_PATH,
  SHORTFALL_PATH, AUCTION_RATIO_PATH, AUCTION_BY_CATEGORY,
  SUPPLY_DEMAND,
  MACC_ALL, SECTOR_INFO, MACC_TECH_DETAILS, type MaccTech,
  fmtWon, fmtWonK, type ScenarioId,
} from '@/lib/data';

// ─── 공통 스타일 ─────────────────────────────────────────────
const GRID = '#EEF0F2';
const AXIS = '#9CA3AF';
const AXIS_LINE = '#E5E7EB';
const TOOLTIP_STYLE = {
  fontSize: 11, borderRadius: 8,
  border: '1px solid #E5E7EB',
  boxShadow: '0 4px 16px rgba(0,0,0,.06)',
  fontFamily: "'Pretendard', 'Inter', sans-serif",
};
const TICK = { fontSize: 10.5, fontFamily: 'Inter', fill: AXIS };
const scenLines = (dot = false, width = 2.2) => (
  <>
    <Line type="monotone" dataKey="base"   stroke={SCEN.base.color}   strokeWidth={width} dot={dot} name="기준" />
    <Line type="monotone" dataKey="middle" stroke={SCEN.middle.color} strokeWidth={width} dot={dot} name="중간" />
    <Line type="monotone" dataKey="ideal"  stroke={SCEN.ideal.color}  strokeWidth={width} dot={dot} name="이상" />
  </>
);

// ─── 1. KAU 가격 경로 라인차트 (EUA 토글 + 기술 임계가격 + 계획기간) ──
import { useState, useMemo } from 'react';

// K-ETS 계획기간 (5년 단위)
const PLAN_PERIODS = [
  { start: 2026, end: 2030, label: '4차' },
  { start: 2031, end: 2035, label: '5차' },
  { start: 2036, end: 2040, label: '6차' },
  { start: 2041, end: 2045, label: '7차' },
  { start: 2046, end: 2050, label: '8차' },
];

// 주요 기술 임계가격 (가격 도달 시 활성화되는 기술)
const TECH_THRESHOLDS = MACC_ALL
  .filter(t => t.cost > 0 && t.potential >= 5)  // 잠재량 5Mt 이상만 표시
  .sort((a, b) => a.cost - b.cost)
  .reduce((acc, t) => {
    // 비용이 비슷한 기술 그룹화 (±5000원)
    const existing = acc.find(a => Math.abs(a.cost - t.cost) < 5000);
    if (existing) {
      existing.techs.push(t.tech);
      existing.potential += t.potential;
    } else {
      acc.push({ cost: t.cost, techs: [t.tech], potential: t.potential, sector: t.sector });
    }
    return acc;
  }, [] as { cost: number; techs: string[]; potential: number; sector: string }[]);

export function KAUPriceChart({ height = 380 }: { height?: number }) {
  const [showEUA, setShowEUA] = useState(false);
  const [showTechs, setShowTechs] = useState(true);

  const yMax = showEUA ? 800000 : 250000;
  const yTicks = showEUA
    ? [0, 200000, 400000, 600000, 800000]
    : [0, 50000, 100000, 150000, 200000, 250000];

  return (
    <div>
      <div className="flex justify-end gap-2 mb-2">
        <button
          onClick={() => setShowTechs(!showTechs)}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] border transition-colors"
          style={{
            borderColor: showTechs ? '#10A574' : '#E5E7EB',
            color: showTechs ? '#10A574' : '#9CA3AF',
            background: showTechs ? '#F0FDF4' : 'transparent',
          }}
        >
          <span className="text-[9px]">MACC</span>
          <span style={{ fontFamily: 'Inter' }}>기술 임계가격</span>
          <span className="text-[9px]">{showTechs ? 'ON' : 'OFF'}</span>
        </button>
        <button
          onClick={() => setShowEUA(!showEUA)}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] border transition-colors"
          style={{
            borderColor: showEUA ? EUA_COLOR : '#E5E7EB',
            color: showEUA ? EUA_COLOR : '#9CA3AF',
            background: showEUA ? '#F8FAFC' : 'transparent',
          }}
        >
          <span className="w-4 border-t-[1.5px] border-dashed" style={{ borderColor: showEUA ? EUA_COLOR : '#D1D5DB' }} />
          <span style={{ fontFamily: 'Inter' }}>EUA 참조</span>
          <span className="text-[9px]">{showEUA ? 'ON' : 'OFF'}</span>
        </button>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={PRICE_PATH} margin={{ top: 12, right: 16, left: 4, bottom: 4 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="year" stroke={AXIS} tick={TICK} tickLine={false} axisLine={{ stroke: AXIS_LINE }} />
          <YAxis stroke={AXIS} tick={TICK} tickLine={false} axisLine={false}
                 tickFormatter={fmtWonK} domain={[0, yMax]} ticks={yTicks} />
          <Tooltip contentStyle={TOOLTIP_STYLE}
                   formatter={(v) => fmtWon(Number(v)) + ' 원'} labelFormatter={(l) => l + '년'} />
          {showEUA && (
            <Line type="monotone" dataKey="eua" stroke={EUA_COLOR} strokeWidth={1.5} strokeDasharray="4 4" dot={false} name="EUA 참조" />
          )}
          {/* 기술 임계가격 참조선 */}
          {showTechs && TECH_THRESHOLDS.filter(t => t.cost <= yMax).map((t, i) => (
            <ReferenceLine key={i} y={t.cost} stroke="#D1D5DB" strokeDasharray="2 3" strokeWidth={0.8}
              label={{ value: `${t.techs[0]} ${fmtWonK(t.cost)}`, fontSize: 9, fill: '#9CA3AF', position: 'right' }} />
          ))}
          {/* 계획기간 경계 */}
          {PLAN_PERIODS.map(p => (
            <ReferenceLine key={p.start} x={p.start} stroke="#E5E7EB" strokeDasharray="3 3"
              label={{ value: p.label, fontSize: 9, fill: '#D1D5DB', position: 'insideTopLeft' }} />
          ))}
          <Line type="monotone" dataKey="base"   stroke={SCEN.base.color}   strokeWidth={2.5} dot={false} name="기준 Base" />
          <Line type="monotone" dataKey="middle" stroke={SCEN.middle.color} strokeWidth={2.5} dot={false} name="중간 Middle" />
          <Line type="monotone" dataKey="ideal"  stroke={SCEN.ideal.color}  strokeWidth={2.5} dot={false} name="이상 Ideal" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── 2. EUA−KAU 가격차 추이 ─────────────────────────────────
export function GapAreaChart({ height = 250 }: { height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={GAP_PATH} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="year" stroke={AXIS} tick={TICK} tickLine={false} axisLine={{ stroke: AXIS_LINE }} />
        <YAxis stroke={AXIS} tick={TICK} tickLine={false} axisLine={false} tickFormatter={fmtWonK} />
        <Tooltip contentStyle={TOOLTIP_STYLE}
                 formatter={(v) => fmtWon(Number(v)) + ' 원'} labelFormatter={(l) => l + '년 · EUA−KAU 격차'} />
        <ReferenceLine y={0} stroke="#D1D5DB" />
        {scenLines()}
      </LineChart>
    </ResponsiveContainer>
  );
}

// ─── 3. 산업별 CBAM 부담 막대차트 ───────────────────────────
export function IndustryCBAMBarChart({ height = 220 }: { height?: number }) {
  const data = [
    { industry: '철강',     base: CBAM_2030.steel.base,   middle: CBAM_2030.steel.middle,   ideal: CBAM_2030.steel.ideal },
    { industry: '석유화학', base: CBAM_2030.petchem.base, middle: CBAM_2030.petchem.middle, ideal: CBAM_2030.petchem.ideal },
  ];
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 18, right: 12, left: 0, bottom: 0 }} barCategoryGap="24%">
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="industry" stroke={AXIS} tick={{ ...TICK, fontFamily: 'Pretendard' }} tickLine={false} axisLine={{ stroke: AXIS_LINE }} />
        <YAxis stroke={AXIS} tick={TICK} tickLine={false} axisLine={false} unit="조" />
        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => Number(v).toFixed(2) + ' 조원/년'} />
        <Bar dataKey="base"   fill={SCEN.base.color}   radius={[3,3,0,0]} name="기준" maxBarSize={36}>
          <LabelList dataKey="base" position="top" fontSize={10} fill={SCEN.base.color} formatter={(v) => Number(v).toFixed(2)} />
        </Bar>
        <Bar dataKey="middle" fill={SCEN.middle.color} radius={[3,3,0,0]} name="중간" maxBarSize={36}>
          <LabelList dataKey="middle" position="top" fontSize={10} fill={SCEN.middle.color} formatter={(v) => Number(v).toFixed(2)} />
        </Bar>
        <Bar dataKey="ideal"  fill={SCEN.ideal.color}  radius={[3,3,0,0]} name="이상" maxBarSize={36}>
          <LabelList dataKey="ideal" position="top" fontSize={10} fill={SCEN.ideal.color} formatter={(v) => Number(v).toFixed(2)} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ─── 4. Banking Stock 추이 (v0.6 신규) ──────────────────────
export function BankingChart({ height = 220 }: { height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={BANKING_PATH} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="year" stroke={AXIS} tick={TICK} tickLine={false} axisLine={{ stroke: AXIS_LINE }} />
        <YAxis stroke={AXIS} tick={TICK} tickLine={false} axisLine={false} unit=" Mt" />
        <Tooltip contentStyle={TOOLTIP_STYLE}
                 formatter={(v) => Number(v).toFixed(1) + ' Mt'} labelFormatter={(l) => l + '년 · Banking 잔고'} />
        <ReferenceLine y={0} stroke="#D1D5DB" />
        <Area type="monotone" dataKey="base"   stroke={SCEN.base.color}   fill={SCEN.base.soft}   strokeWidth={2} name="기준" />
        <Area type="monotone" dataKey="middle" stroke={SCEN.middle.color} fill={SCEN.middle.soft} strokeWidth={2} name="중간" fillOpacity={0.4} />
        <Area type="monotone" dataKey="ideal"  stroke={SCEN.ideal.color}  fill={SCEN.ideal.soft}  strokeWidth={2} name="이상" fillOpacity={0.4} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ─── 5. 경매수입 추이 (연간 + 누적) ─────────────────────────
export function RevenueChart({ height = 250 }: { height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={ANNUAL_REVENUE_PATH} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="year" stroke={AXIS} tick={TICK} tickLine={false} axisLine={{ stroke: AXIS_LINE }} />
        <YAxis stroke={AXIS} tick={TICK} tickLine={false} axisLine={false} unit="조" />
        <Tooltip contentStyle={TOOLTIP_STYLE}
                 formatter={(v) => Number(v).toFixed(2) + ' 조원/년'} labelFormatter={(l) => l + '년 · 연간 경매수입'} />
        <Bar dataKey="base"   fill={SCEN.base.color}   fillOpacity={0.25} radius={[2,2,0,0]} name="기준" maxBarSize={24} />
        <Bar dataKey="middle" fill={SCEN.middle.color} fillOpacity={0.25} radius={[2,2,0,0]} name="중간" maxBarSize={24} />
        <Bar dataKey="ideal"  fill={SCEN.ideal.color}  fillOpacity={0.25} radius={[2,2,0,0]} name="이상" maxBarSize={24} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

// ─── 6. 누적 경매수입 ────────────────────────────────────────
export function CumRevenueChart({ height = 220 }: { height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={REVENUE_PATH} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="year" stroke={AXIS} tick={TICK} tickLine={false} axisLine={{ stroke: AXIS_LINE }} />
        <YAxis stroke={AXIS} tick={TICK} tickLine={false} axisLine={false} unit="조" />
        <Tooltip contentStyle={TOOLTIP_STYLE}
                 formatter={(v) => Number(v).toFixed(1) + ' 조원'} labelFormatter={(l) => l + '년 · 누적 경매수입'} />
        {scenLines()}
      </LineChart>
    </ResponsiveContainer>
  );
}

// ─── 7. 유상할당 비율 추이 (부문별 3-panel) ─────────────────
const ALLOC_CATEGORIES = [
  { key: 'power' as const, ko: '전환 (발전)', en: 'Power' },
  { key: 'non_power' as const, ko: '비전환', en: 'Non-power' },
  { key: 'leakage' as const, ko: '누출업종', en: 'Carbon leakage' },
];

export function AllocationChart({ height = 280 }: { height?: number }) {
  const panelH = Math.floor((height - 30) / 3);
  return (
    <div className="space-y-1">
      {ALLOC_CATEGORIES.map(cat => (
        <div key={cat.key}>
          <div className="flex items-baseline gap-2 mb-0.5 px-1">
            <span className="text-[11px] font-semibold text-[#111827]">{cat.ko}</span>
            <span className="text-[9.5px] text-[#9CA3AF]" style={{ fontFamily: 'Inter' }}>{cat.en}</span>
          </div>
          <ResponsiveContainer width="100%" height={panelH}>
            <LineChart data={AUCTION_BY_CATEGORY[cat.key]} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="year" stroke={AXIS} tick={{ fontSize: 9, fontFamily: 'Inter', fill: AXIS }}
                     tickLine={false} axisLine={{ stroke: AXIS_LINE }} />
              <YAxis stroke={AXIS} tick={{ fontSize: 9, fontFamily: 'Inter', fill: AXIS }}
                     tickLine={false} axisLine={false}
                     tickFormatter={(v: number) => (v * 100).toFixed(0) + '%'}
                     domain={[0, 1]} ticks={[0, 0.5, 1.0]} />
              <Tooltip contentStyle={{ ...TOOLTIP_STYLE, fontSize: 10 }}
                       formatter={(v) => (Number(v) * 100).toFixed(1) + '%'}
                       labelFormatter={(l) => l + '년'} />
              {scenLines(false, 2)}
            </LineChart>
          </ResponsiveContainer>
        </div>
      ))}
    </div>
  );
}

// ─── 8. Fundamental Shortfall 추이 ──────────────────────────
export function ShortfallChart({ height = 220 }: { height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={SHORTFALL_PATH} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="year" stroke={AXIS} tick={TICK} tickLine={false} axisLine={{ stroke: AXIS_LINE }} />
        <YAxis stroke={AXIS} tick={TICK} tickLine={false} axisLine={false} unit=" Mt" />
        <Tooltip contentStyle={TOOLTIP_STYLE}
                 formatter={(v) => Number(v).toFixed(1) + ' Mt'} labelFormatter={(l) => l + '년 · BAU−Cap 잔차'} />
        <Area type="monotone" dataKey="ideal"  stroke={SCEN.ideal.color}  fill={SCEN.ideal.soft}  strokeWidth={2} name="이상" fillOpacity={0.3} />
        <Area type="monotone" dataKey="middle" stroke={SCEN.middle.color} fill={SCEN.middle.soft} strokeWidth={2} name="중간" fillOpacity={0.3} />
        <Area type="monotone" dataKey="base"   stroke={SCEN.base.color}   fill={SCEN.base.soft}   strokeWidth={2} name="기준" fillOpacity={0.3} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ─── 9. BAU vs Cap 수급 구조 차트 ─────────────────────────────
export function SupplyDemandChart({ height = 280 }: { height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={SUPPLY_DEMAND} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="year" stroke={AXIS} tick={TICK} tickLine={false} axisLine={{ stroke: AXIS_LINE }} />
        <YAxis stroke={AXIS} tick={TICK} tickLine={false} axisLine={false} unit=" Mt"
               domain={[200, 550]} />
        <Tooltip contentStyle={TOOLTIP_STYLE}
                 formatter={(v) => Number(v).toFixed(1) + ' Mt'}
                 labelFormatter={(l) => l + '년'} />
        {/* BAU — 두꺼운 검정 실선 */}
        <Line type="monotone" dataKey="bau" stroke="#111827" strokeWidth={2.5} dot={false} name="BAU 배출량" />
        {/* Cap 경로 — 시나리오별 */}
        <Area type="monotone" dataKey="cap_base" stroke={SCEN.base.color} fill={SCEN.base.soft}
              strokeWidth={2} strokeDasharray="0" dot={false} name="Cap (기준)" fillOpacity={0.15} />
        <Area type="monotone" dataKey="cap_middle" stroke={SCEN.middle.color} fill={SCEN.middle.soft}
              strokeWidth={2} dot={false} name="Cap (중간)" fillOpacity={0.15} />
        <Area type="monotone" dataKey="cap_ideal" stroke={SCEN.ideal.color} fill={SCEN.ideal.soft}
              strokeWidth={2} dot={false} name="Cap (이상)" fillOpacity={0.15} />
        <ReferenceLine x={2030} stroke="#D1D5DB" strokeDasharray="2 4"
                       label={{ value: '2030 NDC', fontSize: 10, fill: '#9CA3AF', position: 'top' }} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ─── 10. 전체 MACC Staircase (Custom SVG) — 6개 부문 ────────
export function MACCChartFull({ height = 320 }: { height?: number }) {
  const data = MACC_ALL;
  const W = 800, H = height;
  const pad = { top: 34, right: 80, bottom: 56, left: 58 };
  const innerW = W - pad.left - pad.right;
  const innerH = H - pad.top - pad.bottom;

  const totalPot = data.reduce((s, d) => s + d.potential, 0);
  const maxCost  = Math.max(...data.map(d => d.cost), 50000);
  const minCost  = Math.min(...data.map(d => d.cost), 0);
  const costRange = maxCost - minCost;

  const xScale = (mt: number) => pad.left + (mt / totalPot) * innerW;
  const yScale = (cost: number) => pad.top + innerH - ((cost - minCost) / costRange) * innerH;
  const y0 = yScale(0);

  let cum = 0;
  const bars = data.map(d => {
    const x = xScale(cum);
    const w = xScale(cum + d.potential) - x;
    cum += d.potential;
    const sectorColor = SECTOR_INFO[d.sector as keyof typeof SECTOR_INFO]?.color ?? '#6B7280';
    return { ...d, x, w, y: yScale(Math.max(d.cost, 0)), h: Math.abs(yScale(d.cost) - y0), sectorColor };
  });

  // Y축 눈금
  const yTicks: number[] = [];
  const step = costRange > 500000 ? 100000 : costRange > 200000 ? 50000 : 30000;
  for (let v = 0; v <= maxCost; v += step) yTicks.push(v);
  if (minCost < 0) yTicks.unshift(Math.ceil(minCost / 10000) * 10000);

  const refLines = SCEN_LIST.map(s => ({ ...s, price: KPI.price2030[s.id] }));

  // 부문 범례 데이터
  const sectorSummary = Object.entries(SECTOR_INFO).map(([id, info]) => ({
    id, ...info,
    count: data.filter(d => d.sector === id).length,
    potential: data.filter(d => d.sector === id).reduce((s, d) => s + d.potential, 0),
  })).filter(s => s.count > 0);

  return (
    <div className="w-full">
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" className="w-full block"
           style={{ height: 'auto', fontFamily: 'Inter, Pretendard' }}>
        {/* 격자 */}
        {yTicks.map((v, i) => (
          <line key={i} x1={pad.left} x2={W - pad.right} y1={yScale(v)} y2={yScale(v)}
                stroke={v === 0 ? '#D1D5DB' : '#F1F3F5'} strokeWidth={v === 0 ? 1.2 : 0.8} />
        ))}
        {/* 막대 */}
        {bars.map((b, i) => (
          <g key={i}>
            <rect x={b.x + 0.5} y={b.cost >= 0 ? b.y : y0}
                  width={Math.max(b.w - 1, 1)} height={Math.max(b.h, 1)}
                  fill={b.sectorColor} fillOpacity={b.cost < 0 ? 0.35 : 0.7}
                  stroke={b.sectorColor} strokeWidth={0.5} strokeOpacity={0.5}>
              <title>{`${b.tech} (${SECTOR_INFO[b.sector as keyof typeof SECTOR_INFO]?.ko}) · ${b.potential.toFixed(1)} Mt · ${b.cost.toLocaleString()} 원/tCO₂`}</title>
            </rect>
            {b.w > 16 && (
              <text x={b.x + b.w / 2} y={pad.top - 5} fontSize={8.5} fill="#4B5563"
                    textAnchor="start" transform={`rotate(-40 ${b.x + b.w / 2} ${pad.top - 5})`}>
                {b.tech}
              </text>
            )}
          </g>
        ))}
        {/* 시나리오 가격 참조선 */}
        {refLines.map(r => (
          <g key={r.id}>
            <line x1={pad.left} x2={W - pad.right} y1={yScale(r.price)} y2={yScale(r.price)}
                  stroke={r.color} strokeWidth={1.3} strokeDasharray="5 3" opacity={0.85} />
            <text x={W - pad.right + 5} y={yScale(r.price) + 3} fontSize={10} fill={r.color} fontWeight={600}>
              {fmtWonK(r.price)}
            </text>
            <text x={W - pad.right + 5} y={yScale(r.price) + 14} fontSize={8.5} fill={r.color} opacity={0.8}>
              {r.ko}
            </text>
          </g>
        ))}
        {/* Y축 라벨 */}
        {yTicks.map((v, i) => (
          <text key={i} x={pad.left - 6} y={yScale(v) + 3} fontSize={9.5} fill="#9CA3AF" textAnchor="end">
            {v >= 1000 ? (v/1000) + 'k' : v <= -1000 ? '−' + (Math.abs(v)/1000) + 'k' : v}
          </text>
        ))}
        {/* X축 라벨 */}
        {[0, 50, 100, 150, 200].filter(v => v <= totalPot).map((mt, i) => (
          <text key={i} x={xScale(mt)} y={H - pad.bottom + 16} fontSize={9.5} fill="#9CA3AF" textAnchor="middle">
            {mt}
          </text>
        ))}
        <text x={pad.left - 46} y={pad.top + innerH / 2} fontSize={10} fill="#6B7280"
              transform={`rotate(-90 ${pad.left - 46} ${pad.top + innerH / 2})`} textAnchor="middle">
          원/tCO₂
        </text>
        <text x={pad.left + innerW / 2} y={H - 18} fontSize={10} fill="#6B7280" textAnchor="middle">
          누적 감축잠재량 (MtCO₂/년)
        </text>
      </svg>

      {/* 부문 범례 */}
      <div className="flex flex-wrap gap-x-5 gap-y-1 mt-2 px-2">
        {sectorSummary.map(s => (
          <div key={s.id} className="flex items-center gap-1.5 text-[11px]">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ background: s.color }} />
            <span className="text-[#4B5563]">{s.ko}</span>
            <span className="text-[#9CA3AF]" style={{ fontFamily: 'Inter' }}>{s.potential.toFixed(1)} Mt</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// 단일 부문 MACC (기존 호환)
export function MACCChart({ data, accent = '#5B7BAA', height = 260 }: { data: MaccTech[]; accent?: string; height?: number }) {
  const W = 560, H = height;
  const pad = { top: 30, right: 70, bottom: 56, left: 56 };
  const innerW = W - pad.left - pad.right;
  const innerH = H - pad.top - pad.bottom;

  const totalPot = data.reduce((s, d) => s + d.potential, 0);
  const maxCost  = Math.max(...data.map(d => d.cost), 50000);
  const minCost  = Math.min(...data.map(d => d.cost), 0);

  const xScale = (mt: number) => pad.left + (mt / totalPot) * innerW;
  const yScale = (cost: number) => pad.top + innerH - ((cost - minCost) / (maxCost - minCost)) * innerH;
  const y0 = yScale(0);

  let cum = 0;
  const bars = data.map(d => {
    const x = xScale(cum);
    const w = xScale(cum + d.potential) - x;
    cum += d.potential;
    return { ...d, x, w, y: yScale(Math.max(d.cost, 0)), h: Math.abs(yScale(d.cost) - y0) };
  });

  const yTicks: number[] = [];
  for (let v = 0; v <= maxCost; v += 30000) yTicks.push(v);
  if (minCost < 0) yTicks.unshift(Math.ceil(minCost / 10000) * 10000);

  const refLines = SCEN_LIST.map(s => ({ ...s, price: KPI.price2030[s.id] }));

  return (
    <div className="w-full">
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" className="w-full block"
           style={{ height: 'auto', fontFamily: 'Inter, Pretendard' }}>
        {yTicks.map((v, i) => (
          <line key={i} x1={pad.left} x2={W - pad.right} y1={yScale(v)} y2={yScale(v)}
                stroke={v === 0 ? '#D1D5DB' : '#F1F3F5'} strokeWidth={1} />
        ))}
        {bars.map((b, i) => (
          <g key={i}>
            <rect x={b.x + 1} y={b.cost >= 0 ? b.y : y0} width={Math.max(b.w - 2, 1)} height={b.h}
                  fill={accent} fillOpacity={b.cost < 0 ? 0.35 : 0.75} stroke={accent} strokeWidth={0.5}>
              <title>{`${b.tech} · ${b.potential.toFixed(1)} MtCO₂ · ${b.cost.toLocaleString('ko-KR')} 원/tCO₂`}</title>
            </rect>
            <text x={b.x + b.w / 2} y={pad.top - 6} fontSize={9.5} fill="#4B5563"
                  textAnchor="start" transform={`rotate(-35 ${b.x + b.w / 2} ${pad.top - 6})`}>
              {b.tech}
            </text>
          </g>
        ))}
        {refLines.map(r => (
          <g key={r.id}>
            <line x1={pad.left} x2={W - pad.right} y1={yScale(r.price)} y2={yScale(r.price)}
                  stroke={r.color} strokeWidth={1.3} strokeDasharray="5 3" opacity={0.9} />
            <text x={W - pad.right + 5} y={yScale(r.price) + 3} fontSize={10} fill={r.color} fontWeight={600}>
              {fmtWonK(r.price)}
            </text>
            <text x={W - pad.right + 5} y={yScale(r.price) + 14} fontSize={8.5} fill={r.color} opacity={0.8}>
              {r.ko}
            </text>
          </g>
        ))}
        {yTicks.map((v, i) => (
          <text key={i} x={pad.left - 6} y={yScale(v) + 3} fontSize={9.5} fill="#9CA3AF" textAnchor="end">
            {v >= 1000 ? (v/1000) + 'k' : v <= -1000 ? '−' + (Math.abs(v)/1000) + 'k' : v}
          </text>
        ))}
        {[0, totalPot * 0.25, totalPot * 0.5, totalPot * 0.75, totalPot].map((mt, i) => (
          <text key={i} x={xScale(mt)} y={H - pad.bottom + 16} fontSize={9.5} fill="#9CA3AF" textAnchor="middle">
            {mt.toFixed(1)}
          </text>
        ))}
        <text x={pad.left - 44} y={pad.top + innerH / 2} fontSize={10} fill="#6B7280"
              transform={`rotate(-90 ${pad.left - 44} ${pad.top + innerH / 2})`} textAnchor="middle">
          ₩/tCO₂
        </text>
        <text x={pad.left + innerW / 2} y={H - 18} fontSize={10} fill="#6B7280" textAnchor="middle">
          누적 감축잠재량 (MtCO₂/년)
        </text>
      </svg>
    </div>
  );
}

// ─── 10. 기술 도입 현황 테이블 (시나리오×기술 매트릭스) ──────
export function TechActivationTable() {
  const techs = MACC_TECH_DETAILS.length > 0
    ? [...MACC_TECH_DETAILS].sort((a, b) => a.cost_krw - b.cost_krw)
    : [...MACC_ALL].sort((a, b) => a.cost - b.cost).map(t => ({
        sector: t.sector, technology: t.tech,
        cost_krw: t.cost, cost_usd: Math.round(t.cost / 1380),
        potential_Mt: t.potential, potential_pct: 0,
        timeline: '', source: '',
      }));

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[11px] border-collapse" style={{ fontFamily: "'Pretendard', 'Inter', sans-serif" }}>
        <thead>
          <tr className="border-b-2 border-[#E5E7EB]">
            <th className="text-left py-2 px-2 text-[#6B7280] font-medium">부문</th>
            <th className="text-left py-2 px-2 text-[#6B7280] font-medium">감축기술</th>
            <th className="text-right py-2 px-2 text-[#6B7280] font-medium" style={{ fontFamily: 'Inter' }}>비용 (원/tCO₂)</th>
            <th className="text-right py-2 px-2 text-[#6B7280] font-medium" style={{ fontFamily: 'Inter' }}>잠재량 (Mt/yr)</th>
            <th className="text-center py-2 px-2 text-[#6B7280] font-medium">도입시기</th>
            {SCEN_LIST.map(s => (
              <th key={s.id} className="text-center py-2 px-2 font-medium" style={{ color: s.color }}>
                {s.ko}<br />
                <span className="text-[9px] font-normal" style={{ fontFamily: 'Inter' }}>{fmtWonK(KPI.price2030[s.id])}</span>
              </th>
            ))}
            <th className="text-left py-2 px-2 text-[#6B7280] font-medium text-[10px]">출처</th>
          </tr>
        </thead>
        <tbody>
          {techs.map((t, i) => {
            const sInfo = SECTOR_INFO[t.sector as keyof typeof SECTOR_INFO];
            return (
              <tr key={i} className="border-b border-[#F3F4F6] hover:bg-[#F9FAFB] transition-colors">
                <td className="py-1.5 px-2">
                  <span className="inline-flex items-center gap-1">
                    <span className="w-2 h-2 rounded-sm" style={{ background: sInfo?.color ?? '#6B7280' }} />
                    <span className="text-[#4B5563]">{sInfo?.ko ?? t.sector}</span>
                  </span>
                </td>
                <td className="py-1.5 px-2 font-medium text-[#111827]">{t.technology}</td>
                <td className="py-1.5 px-2 text-right tabular-nums" style={{ fontFamily: 'Inter', color: t.cost_krw < 0 ? '#10A574' : '#111827' }}>
                  {t.cost_krw.toLocaleString()}
                </td>
                <td className="py-1.5 px-2 text-right tabular-nums" style={{ fontFamily: 'Inter' }}>
                  {t.potential_Mt.toFixed(1)}
                </td>
                <td className="py-1.5 px-2 text-center text-[10px] text-[#6B7280]" style={{ fontFamily: 'Inter' }}>
                  {t.timeline}
                </td>
                {SCEN_LIST.map(s => {
                  const price2030 = KPI.price2030[s.id];
                  const active = t.cost_krw <= price2030 + 0.5;
                  return (
                    <td key={s.id} className="py-1.5 px-2 text-center">
                      {active ? (
                        <span className="inline-block w-5 h-5 rounded-full text-white text-[10px] leading-5 font-bold"
                              style={{ background: s.color }}>
                          ✓
                        </span>
                      ) : (
                        <span className="inline-block w-5 h-5 rounded-full bg-[#F3F4F6] text-[#D1D5DB] text-[10px] leading-5">
                          –
                        </span>
                      )}
                    </td>
                  );
                })}
                <td className="py-1.5 px-2 text-[9.5px] text-[#9CA3AF] max-w-[180px] truncate" title={t.source}>
                  {t.source}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

'use client';

import { useState, useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ResponsiveContainer, AreaChart, Area,
} from 'recharts';
import { MACC_ALL, SECTOR_INFO, SUPPLY_DEMAND, fmtWon, fmtWonK, type MaccTech } from '@/lib/data';

// ─── 브라우저 내 균형가격 솔버 ───────────────────────────────
// Staircase MACC: 비용 ≤ P인 기술의 잠재량 합 = 감축량
function solveEquilibrium(
  techs: MaccTech[],
  shortfallMt: number,
  learningAdj: (cost: number, tech: string, year: number) => number,
  year: number,
): number {
  const sfTco2 = shortfallMt * 1e6;
  // 이진탐색: 감축량 = shortfall이 되는 가격
  let lo = 0, hi = 1000000;
  for (let iter = 0; iter < 50; iter++) {
    const mid = (lo + hi) / 2;
    const abate = techs.reduce((s, t) => {
      const adjCost = learningAdj(t.cost, t.tech, year);
      return s + (adjCost <= mid ? t.potential * 1e6 : 0);
    }, 0);
    if (abate < sfTco2) lo = mid;
    else hi = mid;
  }
  return Math.round((lo + hi) / 2);
}

// ─── 학습곡선 ────────────────────────────────────────────────
const RE_KEYWORDS = ['태양광', '풍력', '수소', 'H₂', '전기크래킹', '전기가열', '열펌프', '암모니아'];

function makeLearningFn(ratePerYear: number) {
  return (baseCost: number, techName: string, year: number) => {
    const isRE = RE_KEYWORDS.some(k => techName.includes(k));
    if (!isRE || baseCost < 0) return baseCost;
    const t = year - 2026;
    return baseCost * Math.pow(1 - ratePerYear, t);
  };
}

// ─── 타입 ────────────────────────────────────────────────────
type CapPreset = 'base' | 'middle' | 'ideal';
const CAP_LABELS: Record<CapPreset, string> = { base: '기준 (-35%)', middle: '중간 (-43%)', ideal: '이상 (-58%)' };
const CAP_COLORS: Record<CapPreset, string> = { base: '#5B7BAA', middle: '#E8A33D', ideal: '#10A574' };

// ─── 메인 컴포넌트 ──────────────────────────────────────────
export function SimulatorPanel() {
  // 기술 ON/OFF 상태
  const [enabledTechs, setEnabledTechs] = useState<Set<string>>(
    () => new Set(MACC_ALL.map(t => t.tech))
  );

  // Cap 경로 선택
  const [capPreset, setCapPreset] = useState<CapPreset>('middle');

  // 학습곡선 속도 (연간 %)
  const [learningRate, setLearningRate] = useState(4);

  // 유상할당 비율 (2040 기준)
  const [auctionRate2040, setAuctionRate2040] = useState(50);

  // 활성화된 기술만 필터
  const activeTechs = useMemo(
    () => MACC_ALL.filter(t => enabledTechs.has(t.tech)),
    [enabledTechs]
  );

  const learningFn = useMemo(() => makeLearningFn(learningRate / 100), [learningRate]);

  // 연도별 균형가격 계산
  const pricePathSim = useMemo(() => {
    return SUPPLY_DEMAND.map(row => {
      const cap = row[`cap_${capPreset}` as keyof typeof row] as number;
      const shortfall = Math.max(row.bau - cap, 0);
      const price = shortfall > 0
        ? solveEquilibrium(activeTechs, shortfall, learningFn, row.year)
        : 0;
      // 경매수입 (간이 계산)
      const auctionRatio = auctionRate2040 / 100 * ((row.year - 2026) / 14); // 선형 증가
      const revenue = cap * 1e6 * Math.min(auctionRatio, auctionRate2040 / 100) * price / 1e12;
      return {
        year: row.year,
        bau: row.bau,
        cap,
        shortfall: Math.round(shortfall * 10) / 10,
        price,
        revenue: Math.round(revenue * 100) / 100,
        activeTechCount: activeTechs.filter(t => learningFn(t.cost, t.tech, row.year) <= price).length,
      };
    });
  }, [activeTechs, capPreset, learningFn, auctionRate2040]);

  const toggleTech = (tech: string) => {
    setEnabledTechs(prev => {
      const next = new Set(prev);
      if (next.has(tech)) next.delete(tech);
      else next.add(tech);
      return next;
    });
  };

  const toggleSector = (sector: string) => {
    const sectorTechs = MACC_ALL.filter(t => t.sector === sector);
    const allOn = sectorTechs.every(t => enabledTechs.has(t.tech));
    setEnabledTechs(prev => {
      const next = new Set(prev);
      sectorTechs.forEach(t => allOn ? next.delete(t.tech) : next.add(t.tech));
      return next;
    });
  };

  const p2030 = pricePathSim.find(r => r.year === 2030)?.price ?? 0;
  const p2040 = pricePathSim.find(r => r.year === 2040)?.price ?? 0;
  const cumRevenue = pricePathSim.reduce((s, r) => s + r.revenue, 0);
  const totalPotential = activeTechs.reduce((s, t) => s + t.potential, 0);

  const TOOLTIP_STYLE = { fontSize: 11, borderRadius: 8, border: '1px solid #E5E7EB', boxShadow: '0 4px 16px rgba(0,0,0,.06)' };

  return (
    <div className="space-y-5">
      {/* ── 컨트롤 패널 ── */}
      <div className="grid grid-cols-[1fr_320px] gap-5">
        {/* 왼쪽: 가격 경로 차트 */}
        <div className="bg-white border border-[#E5E7EB] rounded-[10px] p-4">
          <div className="flex items-baseline justify-between mb-3">
            <div>
              <h3 className="text-[14px] font-semibold text-[#111827] m-0">시뮬레이션 결과</h3>
              <div className="text-[10.5px] text-[#9CA3AF] mt-1" style={{ fontFamily: 'Inter' }}>
                Custom scenario · {activeTechs.length}/{MACC_ALL.length} techs · {CAP_LABELS[capPreset]} Cap
              </div>
            </div>
            <div className="flex gap-4 text-[12px]" style={{ fontFamily: 'Inter' }}>
              <div><span className="text-[#9CA3AF]">2030:</span> <strong className="text-[#111827]">{fmtWon(p2030)}</strong><span className="text-[#9CA3AF]"> 원</span></div>
              <div><span className="text-[#9CA3AF]">2040:</span> <strong className="text-[#111827]">{fmtWon(p2040)}</strong><span className="text-[#9CA3AF]"> 원</span></div>
            </div>
          </div>

          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={pricePathSim} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="#EEF0F2" vertical={false} />
              <XAxis dataKey="year" stroke="#9CA3AF" tick={{ fontSize: 10.5, fontFamily: 'Inter' }} tickLine={false} />
              <YAxis stroke="#9CA3AF" tick={{ fontSize: 10.5, fontFamily: 'Inter' }} tickLine={false} axisLine={false}
                     tickFormatter={fmtWonK} />
              <Tooltip contentStyle={TOOLTIP_STYLE}
                       formatter={(v: any) => fmtWon(Number(v)) + ' 원'} labelFormatter={(l) => l + '년'} />
              <Line type="monotone" dataKey="price" stroke={CAP_COLORS[capPreset]} strokeWidth={2.5} dot={false} name="균형가격" />
              {/* 기술 임계가격 참조선 (상위 5개) */}
              {activeTechs
                .filter(t => t.cost > 0 && t.potential >= 3)
                .sort((a, b) => a.cost - b.cost)
                .slice(0, 6)
                .map((t, i) => (
                  <ReferenceLine key={i} y={t.cost} stroke="#E5E7EB" strokeDasharray="2 3"
                    label={{ value: `${t.tech} ${fmtWonK(t.cost)}`, fontSize: 8.5, fill: '#9CA3AF', position: 'right' }} />
                ))}
            </LineChart>
          </ResponsiveContainer>

          {/* 수급 미니 차트 */}
          <div className="mt-3 pt-3 border-t border-[#F3F4F6]">
            <div className="text-[11px] text-[#6B7280] mb-1">수급 구조 (BAU vs Cap)</div>
            <ResponsiveContainer width="100%" height={120}>
              <AreaChart data={pricePathSim} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
                <XAxis dataKey="year" stroke="#9CA3AF" tick={{ fontSize: 9, fontFamily: 'Inter' }} tickLine={false} />
                <YAxis stroke="#9CA3AF" tick={{ fontSize: 9, fontFamily: 'Inter' }} tickLine={false} axisLine={false} unit=" Mt" />
                <Line type="monotone" dataKey="bau" stroke="#111827" strokeWidth={2} dot={false} name="BAU" />
                <Area type="monotone" dataKey="cap" stroke={CAP_COLORS[capPreset]} fill={CAP_COLORS[capPreset]}
                      strokeWidth={1.5} fillOpacity={0.1} dot={false} name="Cap" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 오른쪽: 설정 패널 */}
        <div className="space-y-3">
          {/* Cap 경로 */}
          <div className="bg-white border border-[#E5E7EB] rounded-[10px] p-4">
            <div className="text-[12px] font-semibold text-[#111827] mb-2">Cap 경로 (NDC 기반)</div>
            <div className="space-y-1.5">
              {(Object.keys(CAP_LABELS) as CapPreset[]).map(k => (
                <button key={k} onClick={() => setCapPreset(k)}
                  className={`w-full text-left px-3 py-2 rounded-md text-[11.5px] border transition-all ${
                    capPreset === k ? 'border-current font-semibold' : 'border-[#E5E7EB] text-[#6B7280]'
                  }`}
                  style={capPreset === k ? { color: CAP_COLORS[k], borderColor: CAP_COLORS[k], background: '#FAFAFA' } : {}}>
                  {CAP_LABELS[k]}
                </button>
              ))}
            </div>
          </div>

          {/* 학습곡선 */}
          <div className="bg-white border border-[#E5E7EB] rounded-[10px] p-4">
            <div className="text-[12px] font-semibold text-[#111827] mb-1">재생에너지 학습곡선</div>
            <div className="text-[10px] text-[#9CA3AF] mb-2">태양광·풍력·수소 연간 비용 하락률</div>
            <input type="range" min={0} max={10} step={0.5} value={learningRate}
              onChange={e => setLearningRate(Number(e.target.value))}
              className="w-full accent-[#10A574]" />
            <div className="flex justify-between text-[10px] text-[#9CA3AF] mt-1" style={{ fontFamily: 'Inter' }}>
              <span>0% (보수)</span>
              <span className="font-semibold text-[#111827]">{learningRate}%/yr</span>
              <span>10% (낙관)</span>
            </div>
          </div>

          {/* 유상할당 */}
          <div className="bg-white border border-[#E5E7EB] rounded-[10px] p-4">
            <div className="text-[12px] font-semibold text-[#111827] mb-1">유상할당 비율 (2040 목표)</div>
            <div className="text-[10px] text-[#9CA3AF] mb-2">가격에 영향 없음 · 경매수입에만 영향</div>
            <input type="range" min={0} max={100} step={5} value={auctionRate2040}
              onChange={e => setAuctionRate2040(Number(e.target.value))}
              className="w-full accent-[#E8A33D]" />
            <div className="flex justify-between text-[10px] text-[#9CA3AF] mt-1" style={{ fontFamily: 'Inter' }}>
              <span>0% (전량 무상)</span>
              <span className="font-semibold text-[#111827]">{auctionRate2040}%</span>
              <span>100% (전량 유상)</span>
            </div>
            <div className="mt-2 text-[11px] text-[#6B7280]" style={{ fontFamily: 'Inter' }}>
              추정 누적 경매수입: <strong className="text-[#111827]">{cumRevenue.toFixed(1)}조원</strong>
            </div>
          </div>

          {/* KPI 요약 */}
          <div className="bg-[#F9FAFB] border border-[#E5E7EB] rounded-[10px] p-4">
            <div className="text-[12px] font-semibold text-[#111827] mb-2">시뮬레이션 요약</div>
            <div className="space-y-1 text-[11px]" style={{ fontFamily: 'Inter' }}>
              <div className="flex justify-between"><span className="text-[#6B7280]">활성 기술</span><span className="text-[#111827] font-semibold">{activeTechs.length}/{MACC_ALL.length}</span></div>
              <div className="flex justify-between"><span className="text-[#6B7280]">감축잠재량</span><span className="text-[#111827] font-semibold">{totalPotential.toFixed(1)} Mt/yr</span></div>
              <div className="flex justify-between"><span className="text-[#6B7280]">2030 가격</span><span className="text-[#111827] font-semibold">{fmtWon(p2030)} 원</span></div>
              <div className="flex justify-between"><span className="text-[#6B7280]">2040 가격</span><span className="text-[#111827] font-semibold">{fmtWon(p2040)} 원</span></div>
              <div className="flex justify-between"><span className="text-[#6B7280]">2040 활성기술</span><span className="text-[#111827] font-semibold">{pricePathSim.find(r => r.year === 2040)?.activeTechCount ?? 0}개</span></div>
            </div>
          </div>
        </div>
      </div>

      {/* ── 기술 ON/OFF 매트릭스 ── */}
      <div className="bg-white border border-[#E5E7EB] rounded-[10px] p-4">
        <div className="flex items-baseline justify-between mb-3">
          <div>
            <h3 className="text-[14px] font-semibold text-[#111827] m-0">감축기술 선택</h3>
            <div className="text-[10.5px] text-[#9CA3AF] mt-1">기술을 클릭하여 ON/OFF. 비활성화된 기술은 시장에서 제외됩니다.</div>
          </div>
          <div className="flex gap-2">
            <button onClick={() => setEnabledTechs(new Set(MACC_ALL.map(t => t.tech)))}
              className="px-2.5 py-1 rounded text-[10.5px] border border-[#E5E7EB] text-[#6B7280] hover:bg-[#F9FAFB]">
              전체 ON
            </button>
            <button onClick={() => setEnabledTechs(new Set())}
              className="px-2.5 py-1 rounded text-[10.5px] border border-[#E5E7EB] text-[#6B7280] hover:bg-[#F9FAFB]">
              전체 OFF
            </button>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          {Object.entries(SECTOR_INFO).map(([secId, info]) => {
            const secTechs = MACC_ALL.filter(t => t.sector === secId).sort((a, b) => a.cost - b.cost);
            if (secTechs.length === 0) return null;
            const allOn = secTechs.every(t => enabledTechs.has(t.tech));
            return (
              <div key={secId}>
                <button onClick={() => toggleSector(secId)}
                  className="flex items-center gap-2 mb-2 text-[12px] font-semibold hover:opacity-80 border-0 bg-transparent cursor-pointer p-0">
                  <span className="w-2.5 h-2.5 rounded-sm" style={{ background: info.color }} />
                  <span style={{ color: info.color }}>{info.ko}</span>
                  <span className="text-[9.5px] text-[#9CA3AF] font-normal" style={{ fontFamily: 'Inter' }}>{info.en}</span>
                  <span className="text-[9px] text-[#9CA3AF]">{allOn ? '(전체 ON)' : ''}</span>
                </button>
                <div className="space-y-1">
                  {secTechs.map(t => {
                    const on = enabledTechs.has(t.tech);
                    const viable2030 = t.cost <= p2030;
                    return (
                      <button key={t.tech} onClick={() => toggleTech(t.tech)}
                        className={`w-full text-left flex items-center gap-2 px-2 py-1.5 rounded text-[11px] border transition-all ${
                          on ? 'border-[#D1D5DB] bg-white' : 'border-[#F3F4F6] bg-[#F9FAFB] opacity-50'
                        }`}>
                        <span className={`w-3.5 h-3.5 rounded border flex items-center justify-center text-[9px] font-bold ${
                          on ? 'border-current text-white' : 'border-[#D1D5DB] text-transparent'
                        }`} style={on ? { background: info.color, borderColor: info.color } : {}}>
                          ✓
                        </span>
                        <span className="flex-1 truncate">{t.tech}</span>
                        <span className="text-[9.5px] tabular-nums" style={{ fontFamily: 'Inter', color: t.cost < 0 ? '#10A574' : '#6B7280' }}>
                          {fmtWonK(t.cost)}
                        </span>
                        {on && viable2030 && (
                          <span className="w-1.5 h-1.5 rounded-full bg-[#10A574]" title="2030 경제성 확보" />
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

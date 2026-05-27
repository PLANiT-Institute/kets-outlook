'use client';

import { SCEN, SCEN_LIST, KPI, fmtWon, type ScenarioId } from '@/lib/data';

export function KpiTriCard({ title, en, unit, values, formatter }: {
  title: string; en: string; unit: string;
  values: Record<string, number>;
  formatter: (v: number) => string;
}) {
  return (
    <div className="bg-white border border-[#E5E7EB] rounded-[10px] p-[14px_16px] hover:shadow-sm transition-shadow">
      <div className="flex justify-between items-baseline mb-3">
        <div>
          <div className="text-[12.5px] font-semibold text-[#111827]">{title}</div>
          <div className="text-[10px] text-[#9CA3AF] mt-[1px]" style={{ fontFamily: 'Inter' }}>{en}</div>
        </div>
        <div className="text-[10px] text-[#9CA3AF] bg-[#F9FAFB] rounded px-1.5 py-0.5" style={{ fontFamily: 'Inter' }}>{unit}</div>
      </div>
      <div className="space-y-[8px]">
        {SCEN_LIST.map(s => (
          <div key={s.id} className="flex items-center justify-between">
            <div className="flex items-center gap-[6px]">
              <span className="w-[7px] h-[7px] rounded-full" style={{ background: s.color }} />
              <span className="text-[11px] text-[#6B7280]">{s.ko}</span>
            </div>
            <span className="text-[14px] font-semibold tabular-nums" style={{ fontFamily: 'Inter', color: s.color }}>
              {formatter(values[s.id])}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function KpiCards() {
  return (
    <div className="grid grid-cols-4 gap-3 mb-5">
      <KpiTriCard
        title="2030 KAU 가격" en="KAU price · 2030" unit="원/tCO₂"
        values={KPI.price2030}
        formatter={(v) => v.toLocaleString('ko-KR')}
      />
      <KpiTriCard
        title="2040 KAU 가격" en="KAU price · 2040" unit="원/tCO₂"
        values={KPI.price2040}
        formatter={(v) => v.toLocaleString('ko-KR')}
      />
      <KpiTriCard
        title="누적 경매수입" en="Cum. auction revenue · 2040" unit="조원"
        values={KPI.cumRevenue2040}
        formatter={(v) => v.toFixed(1)}
      />
      <KpiTriCard
        title="EUA−KAU 격차" en="CBAM gap · 2030" unit="원/tCO₂"
        values={KPI.gap2030}
        formatter={(v) => (v > 0 ? '+' : '') + v.toLocaleString('ko-KR')}
      />
    </div>
  );
}

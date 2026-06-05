'use client';

import { SCEN_LIST, KPI } from '@/lib/data';

export function KpiTriCard({ title, en, unit, values, formatter, feature }: {
  title: string; en: string; unit: string;
  values: Record<string, number>;
  formatter: (v: number) => string;
  feature?: boolean;
}) {
  return (
    <div className={`ta-kpi-card ${feature ? 'feature' : ''}`}>
      <div className="flex justify-between items-baseline mb-3">
        <div>
          <div className="ta-kpi-label">{title}</div>
          <div className="text-[10px] text-[var(--text-muted)] mt-[1px] num">{en}</div>
        </div>
        <div className="ta-kpi-unit">{unit}</div>
      </div>
      <div className="space-y-[8px]">
        {SCEN_LIST.map(s => (
          <div key={s.id} className="flex items-center justify-between">
            <div className="flex items-center gap-[6px]">
              <span className="w-[7px] h-[7px] rounded-full" style={{ background: s.color }} />
              <span className={`text-[11px] ${feature ? 'text-[#AEB9CC]' : 'text-[var(--text-secondary)]'}`}>{s.ko}</span>
            </div>
            <span className="ta-kpi-value" style={{ color: s.color }}>
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
    <div className="ta-kpis">
      <KpiTriCard
        title="2030 KAU 가격" en="KAU price · 2030" unit="원/tCO₂"
        values={KPI.price2030}
        formatter={(v) => v.toLocaleString('ko-KR')}
        feature
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

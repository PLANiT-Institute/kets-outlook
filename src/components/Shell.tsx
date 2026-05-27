'use client';

import { NAV_ITEMS } from '@/lib/data';

function NavIcon({ name, size = 16 }: { name: string; size?: number }) {
  const s = { width: size, height: size, stroke: 'currentColor', fill: 'none', strokeWidth: 1.7, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  switch (name) {
    case 'home':   return <svg viewBox="0 0 24 24" {...s}><path d="M3 11l9-7 9 7v9a2 2 0 0 1-2 2h-4v-7h-6v7H5a2 2 0 0 1-2-2z"/></svg>;
    case 'bars':   return <svg viewBox="0 0 24 24" {...s}><rect x="4" y="11" width="3.5" height="9"/><rect x="10.25" y="6" width="3.5" height="14"/><rect x="16.5" y="14" width="3.5" height="6"/></svg>;
    case 'spread': return <svg viewBox="0 0 24 24" {...s}><line x1="5" y1="6" x2="5" y2="20"/><rect x="3" y="9" width="4" height="8"/><line x1="13" y1="4" x2="13" y2="20"/><rect x="11" y="7" width="4" height="12"/><circle cx="20" cy="14" r="1.5"/></svg>;
    case 'coin':   return <svg viewBox="0 0 24 24" {...s}><circle cx="12" cy="12" r="8"/><path d="M9 14c0 1.1 1.3 2 3 2s3-.9 3-2-1.3-2-3-2-3-.9-3-2 1.3-2 3-2 3 .9 3 2M12 7v10"/></svg>;
    case 'gauge':  return <svg viewBox="0 0 24 24" {...s}><path d="M4 16a8 8 0 0 1 16 0"/><line x1="12" y1="16" x2="16" y2="9"/><circle cx="12" cy="16" r="1.2" fill="currentColor"/></svg>;
    case 'gap':    return <svg viewBox="0 0 24 24" {...s}><line x1="6" y1="4" x2="6" y2="20"/><line x1="18" y1="4" x2="18" y2="20"/><line x1="9" y1="12" x2="15" y2="12"/><polyline points="12,9 15,12 12,15"/></svg>;
    case 'download': return <svg viewBox="0 0 24 24" {...s}><path d="M12 4v12m0 0l-4-4m4 4l4-4M5 20h14"/></svg>;
    default: return null;
  }
}

export function PlanitMark() {
  return (
    <div className="flex items-center gap-[9px]">
      <div className="w-7 h-7 rounded-[6px] bg-[#111827] text-white flex items-center justify-center font-bold text-[13px] tracking-tight" style={{ fontFamily: 'Inter' }}>Pi</div>
      <div className="leading-tight">
        <div className="font-semibold text-[13px] text-[#111827] tracking-tight" style={{ fontFamily: 'Inter' }}>PLANiT</div>
        <div className="text-[9.5px] text-[#9CA3AF] tracking-[.08em] uppercase" style={{ fontFamily: 'Inter' }}>Institute</div>
      </div>
    </div>
  );
}

export function Sidebar({ active = 'overview' }: { active?: string }) {
  return (
    <aside className="w-[220px] flex-shrink-0 bg-white border-r border-[#E5E7EB] flex flex-col" style={{ padding: '20px 14px' }}>
      <div className="px-2 pb-[22px]"><PlanitMark /></div>
      <div className="text-[10px] font-semibold text-[#9CA3AF] tracking-[.12em] uppercase px-[10px] py-[6px] pb-2">분석 모듈</div>
      <nav className="flex flex-col gap-[2px]">
        {NAV_ITEMS.map((n) => {
          const on = n.id === active;
          return (
            <div key={n.id} className={`flex items-center gap-[10px] py-[9px] px-[10px] rounded-[7px] cursor-default ${on ? 'bg-[#F3F4F6] text-[#111827]' : 'text-[#4B5563]'}`}>
              <NavIcon name={n.icon} size={15} />
              <div className="flex flex-col leading-[1.15]">
                <span className={`text-[12.5px] ${on ? 'font-semibold' : 'font-medium'}`}>{n.ko}</span>
                <span className="text-[9.5px] text-[#9CA3AF] tracking-[.02em]" style={{ fontFamily: 'Inter' }}>{n.en}</span>
              </div>
            </div>
          );
        })}
      </nav>
      <div className="mt-auto pt-3 px-[10px] border-t border-[#F3F4F6] text-[10.5px] text-[#9CA3AF] leading-[1.5]">
        <div>Coase + Staircase MACC</div>
        <div style={{ fontFamily: 'Inter' }}>Constrained Hotelling</div>
        <div className="mt-1 text-[#D1D5DB]">v0.6 · 2026.05</div>
      </div>
    </aside>
  );
}

export function PageHeader() {
  return (
    <div className="flex items-end justify-between gap-6 pb-[22px]">
      <div>
        <div className="text-[10.5px] tracking-[.16em] text-[#9CA3AF] uppercase mb-[6px]" style={{ fontFamily: 'Inter' }}>K-ETS Price Outlook · Overview</div>
        <h1 className="text-[26px] font-bold text-[#111827] tracking-tight m-0">K-ETS 가격전망 및 정책 시나리오 분석</h1>
        <div className="mt-2 text-[13px] text-[#6B7280] max-w-[720px] leading-[1.55]">
          부분균형 MACC + Hotelling banking 동학 모형으로 도출한 3개 정책 시나리오의 KAU 가격 경로와 핵심 지표 비교.
        </div>
      </div>
      <div className="flex items-center gap-2">
        <PillBtn label="2026–2040" />
        <PillBtn label="원/tCO₂" />
        <PillBtn icon="download" label="CSV" />
      </div>
    </div>
  );
}

function PillBtn({ label, icon }: { label: string; icon?: string }) {
  return (
    <div className="inline-flex items-center gap-[6px] px-[11px] py-[6px] border border-[#E5E7EB] rounded-full text-[11.5px] text-[#4B5563] bg-white" style={{ fontFamily: 'Inter' }}>
      {icon && <NavIcon name={icon} size={12} />}
      {label}
    </div>
  );
}

export function ChartCard({ title, en, hint, accent, actions, children, noPad }: {
  title: string; en?: string; hint?: string; accent?: string;
  actions?: React.ReactNode; children: React.ReactNode; noPad?: boolean;
}) {
  return (
    <section className="bg-white border border-[#E5E7EB] rounded-[10px] relative" style={{ padding: noPad ? 0 : 18 }}>
      <header className="flex justify-between items-start mb-[14px] gap-4" style={noPad ? { padding: '18px 18px 0' } : undefined}>
        <div>
          <div className="flex items-center gap-2">
            {accent && <span className="w-[3px] h-[14px] rounded-sm" style={{ background: accent }} />}
            <h3 className="m-0 text-[14px] font-semibold text-[#111827]">{title}</h3>
          </div>
          {en && <div className="text-[10.5px] text-[#9CA3AF] mt-[3px]" style={{ fontFamily: 'Inter' }}>{en}</div>}
          {hint && <div className="text-[11.5px] text-[#6B7280] mt-[6px] leading-[1.5]">{hint}</div>}
        </div>
        <div className="flex items-center gap-[6px]">
          {actions}
          <button className="w-[26px] h-[26px] rounded-[6px] border border-[#E5E7EB] bg-white flex items-center justify-center">
            <NavIcon name="download" size={13} />
          </button>
        </div>
      </header>
      {children}
    </section>
  );
}

export function ChartLegend() {
  const items = [
    { color: '#5B7BAA', label: '기준', en: 'Base', dashed: false },
    { color: '#E8A33D', label: '중간', en: 'Middle', dashed: false },
    { color: '#10A574', label: '이상', en: 'Ideal', dashed: false },
    { color: '#94A3B8', label: 'EUA 참조', en: 'EU ETS reference', dashed: true },
  ];
  return (
    <div className="flex gap-[18px] text-[11.5px] text-[#4B5563] flex-wrap">
      {items.map((it, i) => (
        <div key={i} className="flex items-center gap-[7px]">
          {it.dashed
            ? <span className="w-[18px]" style={{ borderTop: `1.5px dashed ${it.color}` }} />
            : <span className="w-[18px] h-[2.5px] rounded-sm" style={{ background: it.color }} />}
          <span>{it.label}</span>
          <span className="text-[#9CA3AF] text-[10px]" style={{ fontFamily: 'Inter' }}>{it.en}</span>
        </div>
      ))}
    </div>
  );
}

export function PageFooter() {
  return (
    <footer className="px-8 py-[18px] border-t border-[#E5E7EB] flex justify-between items-center text-[11px] text-[#9CA3AF] bg-white">
      <div>PLANiT Institute · Coase + Staircase MACC + Constrained Hotelling · 2026–2040</div>
      <div style={{ fontFamily: 'Inter' }}>v0.6 · 6 sectors, 30 technologies</div>
    </footer>
  );
}

export { NavIcon };

'use client';

import { NAV_ITEMS } from '@/lib/data';

const TOPBAR_LABELS: Record<string, string> = {
  overview: '홈',
  mechanism: '메커니즘',
  simulator: '시뮬레이터',
  report: '보고서',
};

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
    <div className="ta-brand">
      <div className="w-[22px] h-[22px] text-white flex items-center justify-center" aria-hidden="true">
        <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
          <path d="M11 3L19 18H3L11 3Z" fill="#2553D6" />
          <path d="M11 9.5L15 18H7L11 9.5Z" fill="white" fillOpacity=".9" />
        </svg>
      </div>
      <div className="leading-tight">
        <div>PLANiT</div>
      </div>
    </div>
  );
}

export function Topbar({ active = 'overview', onNavigate }: { active?: string; onNavigate?: (id: string) => void }) {
  return (
    <header className="ta-topbar">
      <div className="ta-brand">
        <PlanitMark />
        <span className="ta-brand-sub">K-ETS transition analysis</span>
      </div>
      <nav className="ta-nav" aria-label="분석 모듈">
        {NAV_ITEMS.map((n) => {
          const on = n.id === active;
          return (
            <button key={n.id} type="button" onClick={() => onNavigate?.(n.id)} className={on ? 'active' : undefined} title={`${n.ko} · ${n.en}`}>
              <NavIcon name={n.icon} size={14} />
              <span>{TOPBAR_LABELS[n.id] ?? n.ko}</span>
              <span className="ta-nav-sub">{n.en}</span>
            </button>
          );
        })}
      </nav>
      <span className="ta-env-chip">Live engine · results v1.0</span>
      <div className="w-7 h-7 rounded-full bg-[#2553D6] text-white flex items-center justify-center text-[11px] font-semibold num">Pi</div>
    </header>
  );
}

export function ChartCard({ title, en, hint, accent, actions, children, noPad }: {
  title: string; en?: string; hint?: string; accent?: string;
  actions?: React.ReactNode; children: React.ReactNode; noPad?: boolean;
}) {
  return (
    <section className={`ta-panel relative ${noPad ? '' : 'ta-panel-pad'}`}>
      <header className="flex justify-between items-start mb-[14px] gap-4" style={noPad ? { padding: '16px 18px 0' } : undefined}>
        <div>
          <div className="flex items-center gap-2">
            {accent && <span className="w-[3px] h-[14px] rounded-sm" style={{ background: accent }} />}
            <h3 className="ta-panel-title">{title}</h3>
          </div>
          {en && <div className="ta-panel-sub">{en}</div>}
          {hint && <div className="text-[11.5px] text-[var(--text-secondary)] mt-[6px] leading-[1.5]">{hint}</div>}
        </div>
        <div className="flex items-center gap-[6px]">
          {actions}
          <button className="ta-icon-button" aria-label="Download chart data">
            <NavIcon name="download" size={13} />
          </button>
        </div>
      </header>
      {children}
    </section>
  );
}

export function PageFooter() {
  return (
    <footer className="px-8 py-[18px] border-t border-[var(--border)] flex justify-between items-center text-[11px] text-[var(--text-muted)] bg-white">
      <div>PLANiT Institute · Staircase MACC + Constrained Hotelling + λ 레벨-브리지 · 2026–2040</div>
      <div className="num">v1.0 · K-MSR 운영규칙 P0/P1/A/B</div>
    </footer>
  );
}

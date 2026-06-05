'use client';

import { SCEN_LIST, COMPARE_ROWS } from '@/lib/data';

export function CompareTable() {
  return (
    <table className="ta-data-table">
      <thead>
        <tr>
          <th>
            지표 <span className="text-[var(--text-muted)] font-normal">Indicator</span>
          </th>
          <th>단위</th>
          {SCEN_LIST.map(s => (
            <th key={s.id} style={{ color: s.color }}>
              <span className="inline-flex items-center gap-[6px]">
                <span className="w-2 h-2 rounded-sm" style={{ background: s.color }} /> {s.ko}
              </span>
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {COMPARE_ROWS.map((r, i) => (
          <tr key={i} style={{ background: r.cbam ? 'var(--card-soft)' : 'transparent' }}>
            <td className="text-[var(--text-primary)]">
              {r.cbam && (
                <span className="inline-block text-[9px] font-semibold text-white bg-[var(--eua)] py-[2px] px-[5px] rounded-[3px] mr-[6px] align-middle tracking-[.05em] num">CBAM</span>
              )}
              {r.metric}
              <span className="text-[var(--text-muted)] font-normal ml-[6px] text-[0.85em]">{r.en}</span>
            </td>
            <td className="text-[var(--text-secondary)]">{r.unit}</td>
            <td className="text-[var(--text-primary)] num">{r.base}</td>
            <td className="text-[var(--text-primary)] num">{r.middle}</td>
            <td className="text-[var(--text-primary)] num">{r.ideal}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

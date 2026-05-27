'use client';

import { SCEN_LIST, COMPARE_ROWS } from '@/lib/data';

export function CompareTable() {
  return (
    <table className="w-full border-collapse text-[12.5px]" style={{ fontFamily: 'Inter, Pretendard' }}>
      <thead>
        <tr className="border-b border-[#E5E7EB]">
          <th className="text-left py-[11px] px-[14px] text-[#6B7280] font-medium tracking-[.01em]">
            지표 <span className="text-[#9CA3AF] font-normal">Indicator</span>
          </th>
          <th className="text-right py-[11px] px-[14px] text-[#6B7280] font-medium">단위</th>
          {SCEN_LIST.map(s => (
            <th key={s.id} className="text-right py-[11px] px-[14px] font-semibold" style={{ color: s.color }}>
              <span className="inline-flex items-center gap-[6px]">
                <span className="w-2 h-2 rounded-sm" style={{ background: s.color }} /> {s.ko}
              </span>
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {COMPARE_ROWS.map((r, i) => (
          <tr key={i} className="border-b border-[#F3F4F6]" style={{ background: r.cbam ? '#FAFBFC' : 'transparent' }}>
            <td className="py-[11px] px-[14px] text-[#111827]">
              {r.cbam && (
                <span className="inline-block text-[9px] font-semibold text-white bg-[#94A3B8] py-[2px] px-[5px] rounded-[3px] mr-[6px] align-middle tracking-[.05em]"
                      style={{ fontFamily: 'Inter' }}>CBAM</span>
              )}
              {r.metric}
              <span className="text-[#9CA3AF] font-normal ml-[6px] text-[0.85em]">{r.en}</span>
            </td>
            <td className="py-[11px] px-[14px] text-right text-[#6B7280]">{r.unit}</td>
            <td className="py-[11px] px-[14px] text-right text-[#111827]" style={{ fontVariantNumeric: 'tabular-nums' }}>{r.base}</td>
            <td className="py-[11px] px-[14px] text-right text-[#111827]" style={{ fontVariantNumeric: 'tabular-nums' }}>{r.middle}</td>
            <td className="py-[11px] px-[14px] text-right text-[#111827]" style={{ fontVariantNumeric: 'tabular-nums' }}>{r.ideal}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

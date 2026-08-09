'use client';

/**
 * 시나리오 시뮬레이터 — 라이브 K-ETS 엔진(/api/solve) 구동.
 *
 * 두 모드:
 *   1. 패키지 모드 (기본) — 논문 v4 운영규칙 P0/P1/A/B 버튼 →
 *      POST {"package_id"} → engine.solve_package (회랑 하한·방어·헤드라인 활성화 연도).
 *   2. 커스텀 모드 — Cap 시나리오·MACC·MSR 물량규칙·유동성 λ 슬라이더 →
 *      POST 커스텀 레버 → level_bridge_path.
 *
 * 모든 계산은 파이썬 엔진(web/api/solve.py → src/model/engine.py)이 수행. 하드코딩 없음.
 * 로컬 개발: `python3 web/api/solve.py` (:8531) — next.config.ts가 /api를 프록시.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ResponsiveContainer, LineChart, ComposedChart, Line, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine,
} from 'recharts';
import { SCEN, EUA_COLOR, fmtWon, fmtWonK, LATEST_KAU_QUOTE, type ScenarioId } from '@/lib/data';
import { MSR_RESERVE_MT, KMSR_DRAFT_ASSUMPTIONS } from '@/lib/msr';
import { PKG, PKG_LIST, type PackageId } from '@/lib/results';

const API = process.env.NEXT_PUBLIC_API_BASE ?? '';
const DEBOUNCE_MS = 400;
const CUSTOM_SEED_PRESET = 'L3';   // 커스텀 슬라이더 초기값 = 시행령 draft 수량규칙 (엔진 SSOT)

// ─── API 계약 타입 ──────────────────────────────────────────
type PathRow = {
  year: number;
  static: number;          // 정태 anchor (λ=0)
  hotelling: number;       // Hotelling anchor (λ=1)
  kau_realized: number;    // 실현 가격 (레벨-브리지)
  lambda: number;
  intake_Mt: number;
  release_Mt: number;
  bank_Mt: number;
  eua: number;
};

type PkgPathRow = {
  year: number;
  kau: number;             // 실현 가격 (하한 overlay 반영)
  kau_prefloor: number;
  floor: number;
  defended: boolean;
  headroom: number;
  static: number;
  hotelling: number;
  lambda: number;
  intake_Mt: number;
  release_Mt: number;
  bank_Mt: number;
};

type PkgResponse = {
  meta: { package: { id: string; name_kr: string }; years: number[] };
  activation_headline: Record<string, number | null>;
  defended_all: boolean;
  min_headroom: number;
  max_drawdown: number;
  cum_intake_Mt: number;
  path: PkgPathRow[];
};

type MsrPreset = {
  name: string; rho: number;
  theta_plus_Mt: number; theta_minus_Mt: number;
  release_Mt: number; cancel: number;
};

// 시나리오 레버 — 값 목록은 엔진이 엑셀 시트에서 읽어 내려준다(프런트에 박지 않는다).
type LeverSpec = { values?: string[]; range?: [number, number]; default: string | number | null; desc: string };

type SolveMeta = {
  scenarios: string[];
  macc_modes: string[];
  years: number[];
  packages: { id: string; name_kr: string; name_en: string }[];
  model_levers: Record<'h2_scenario' | 'elec_scenario' | 'tech_scenario' | 'cost_multiplier', LeverSpec>;
  liquidity_defaults: {
    lambda_0: number;
    lambda_terminal_default: number;
    ramp_years_default: number;
  };
  presets: Record<string, MsrPreset>;
};

// 레버 값의 한국어 라벨 (엔진은 id만 준다 — 표시 문구는 프런트 몫)
const LEVER_LABELS: Record<string, string> = {
  gov: '정부 기본계획',
  conservative: '보수 (목표 지연)',
  gov_invest: '재생투자 가속',
  base: '기준',
  middle: '중간',
  ideal: '이상',
};

// 패키지 설명 (v4 명명 규율: A·B는 신규 제도가 아니라 법제화된 K-MSR의 운영규칙)
const PKG_DESC: Record<PackageId, string> = {
  P0: '무정책 반사실 — MSR·하한 없음. 모든 운영규칙 효과의 기준선.',
  P1: '시행령 초안대로 — draft 수량규칙(초과분 흡수·20Mt/yr 방출·무취소) + 중위 하한 가정. 방출규칙이 2031년 가격붕락(waterbed)을 만든다.',
  A: 'K-MSR 경매보류가격의 운영경로(신규 제도 아님) — 기술앵커 회랑: 2026 관측가에서 2035 수소환원(H₂-DRI) 문턱까지, 미유찰 보류물량은 무효화.',
  B: 'K-MSR 흡수·무효화 기능의 일정형 운영 — 2035년 개시 사전공표, 경매물량 50% 무조건 흡수·전량 무효화.',
};

const MACC_MODE_LABELS: Record<string, string> = {
  step: 'Step · bottom-up 기술',
  exponential: 'Exponential · 레거시',
};

const TOOLTIP_STYLE = {
  fontSize: 11, borderRadius: 8,
  border: '1px solid #E5E7EB',
  boxShadow: '0 4px 16px rgba(0,0,0,.06)',
  fontFamily: "'Pretendard', 'Inter', sans-serif",
};
const TICK = { fontSize: 10.5, fontFamily: 'Inter', fill: '#9CA3AF' };

type Mode = PackageId | 'custom';

// ─── 메인 컴포넌트 ──────────────────────────────────────────
export function SimulatorPanel() {
  const [meta, setMeta] = useState<SolveMeta | null>(null);
  const [mode, setMode] = useState<Mode>('A');
  const [rows, setRows] = useState<PathRow[]>([]);
  const [pkg, setPkg] = useState<PkgResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // 커스텀 정책 레버
  const [scenario, setScenario] = useState<ScenarioId>('base');
  const [maccMode, setMaccMode] = useState('step');
  const [rho, setRho] = useState(0);
  const [thetaPlus, setThetaPlus] = useState(0);
  const [thetaMinus, setThetaMinus] = useState(0);
  const [release, setRelease] = useState(0);
  const [cancel, setCancel] = useState(0);
  const [lam0, setLam0] = useState(0);
  const [lamTerminal, setLamTerminal] = useState(0);
  const [rampYears, setRampYears] = useState(0);

  // 세계 가정(모형 레버) — 정책과 무관하게 비용·에너지가격 세계를 바꾼다. 두 모드 공통.
  const [h2Sc, setH2Sc] = useState('');
  const [elecSc, setElecSc] = useState('');
  const [techSc, setTechSc] = useState('');     // '' = cap 시나리오 추종
  const [costMult, setCostMult] = useState(1);

  // 초기 메타 로드: 커스텀 슬라이더를 엔진 SSOT 기본값으로 시드
  useEffect(() => {
    fetch(`${API}/api/solve`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((mt: SolveMeta) => {
        setMeta(mt);
        const lv = mt.model_levers;
        if (lv) {
          setH2Sc(String(lv.h2_scenario.default ?? ''));
          setElecSc(String(lv.elec_scenario.default ?? ''));
          setCostMult(Number(lv.cost_multiplier.default ?? 1));
        }
        const ld = mt.liquidity_defaults;
        if (ld) {
          setLam0(ld.lambda_0 ?? 0);
          setLamTerminal(ld.lambda_terminal_default ?? 0);
          setRampYears(ld.ramp_years_default ?? 0);
        }
        const p = mt.presets?.[CUSTOM_SEED_PRESET] ?? Object.values(mt.presets ?? {})[0];
        if (p) {
          setRho(p.rho);
          setThetaPlus(p.theta_plus_Mt);
          setThetaMinus(p.theta_minus_Mt);
          setRelease(p.release_Mt);
          setCancel(p.cancel);
        }
      })
      .catch(e => {
        setErr(e instanceof Error ? e.message : String(e));
        setLoading(false);
      });
  }, []);

  // 라이브 엔진 호출 (out-of-order 응답 무시)
  const seqRef = useRef(0);
  const solve = useCallback(async () => {
    const seq = ++seqRef.current;
    setLoading(true);
    setErr(null);
    try {
      // 세계 가정은 두 모드 공통. 빈 문자열(tech_scenario 미지정)은 보내지 않는다 —
      // 엔진이 cap 시나리오를 따르게 두는 것이 기본 동작이다.
      const overrides: Record<string, string | number> = { cost_multiplier: costMult };
      if (h2Sc) overrides.h2_scenario = h2Sc;
      if (elecSc) overrides.elec_scenario = elecSc;
      if (techSc) overrides.tech_scenario = techSc;

      const body = mode === 'custom'
        ? {
            scenario,
            macc_mode: maccMode,
            msr: { rho, theta_plus_Mt: thetaPlus, theta_minus_Mt: thetaMinus, release_Mt: release, cancel },
            liquidity: { lam_0: lam0, lam_terminal: lamTerminal, ramp_years: rampYears },
            overrides,
          }
        : { package_id: mode, overrides };
      const res = await fetch(`${API}/api/solve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const d = await res.json();
      if (d.error) throw new Error(d.error);
      if (seq === seqRef.current) {
        if (mode === 'custom') {
          setRows(d.path);
          setPkg(null);
        } else {
          setPkg(d as PkgResponse);
          setRows([]);
        }
      }
    } catch (e) {
      if (seq === seqRef.current) setErr(e instanceof Error ? e.message : String(e));
    } finally {
      if (seq === seqRef.current) setLoading(false);
    }
  }, [mode, scenario, maccMode, rho, thetaPlus, thetaMinus, release, cancel, lam0, lamTerminal, rampYears,
      h2Sc, elecSc, techSc, costMult]);

  // 레버 변경 시 디바운스 후 재계산 (메타 로드 후에만)
  useEffect(() => {
    if (!meta) return;
    const t = setTimeout(solve, DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [meta, solve]);

  const isPkg = mode !== 'custom';
  const pkgInfo = isPkg ? PKG[mode] : null;

  return (
    <div className="space-y-5">
      {/* ── API 오류 ── */}
      {err && (
        <div className="bg-[#FEF2F2] border border-[#FCA5A5] rounded-[10px] p-4 text-[12px] text-[#991B1B]">
          <div className="font-semibold mb-1">엔진 API 오류: {err}</div>
          <div className="text-[11px] leading-[1.6]">
            로컬 개발 환경이라면 파이썬 API 서버를 먼저 띄우세요:{' '}
            <code className="bg-white border border-[#FCA5A5] rounded px-1.5 py-0.5">python3 web/api/solve.py</code>
            {' '}(포트 8531 — next dev가 /api를 자동 프록시)
          </div>
        </div>
      )}

      {/* ── 모드 선택: 운영규칙 패키지 + 커스텀 ── */}
      <div className="bg-white border border-[#E5E7EB] rounded-[10px] p-4">
        <div className="text-[12px] font-semibold text-[#111827] mb-0.5">K-MSR 운영규칙 (논문 v4 패키지)</div>
        <div className="text-[10.5px] text-[#9CA3AF] mb-2.5">
          K-MSR은 법제화된 제도 — 아래는 그 운영규칙 4종 · 유상할당은 모두 정부 기발표 경로(A_gov) 공통
        </div>
        <div className="flex flex-wrap gap-1.5">
          {PKG_LIST.map(p => {
            const active = mode === p.id;
            return (
              <button key={p.id} onClick={() => setMode(p.id)} aria-pressed={active}
                className={`px-3 py-2 rounded-md text-[11.5px] border transition-all ${
                  active ? 'font-semibold' : 'border-[#E5E7EB] text-[#6B7280] hover:bg-[#F9FAFB]'
                }`}
                style={active ? { color: p.color, borderColor: p.color, background: p.soft } : {}}>
                {p.id} · {p.ko}
              </button>
            );
          })}
          <button onClick={() => setMode('custom')} aria-pressed={mode === 'custom'}
            className={`px-3 py-2 rounded-md text-[11.5px] border transition-all ${
              mode === 'custom'
                ? 'border-[#111827] bg-[#111827] text-white font-semibold'
                : 'border-[#E5E7EB] text-[#6B7280] hover:bg-[#F9FAFB]'
            }`}>
            커스텀 · 레버 직접 조절
          </button>
        </div>
        {isPkg && (
          <p className="text-[11px] text-[#6B7280] leading-[1.6] mt-2.5 mb-0">
            <strong style={{ color: pkgInfo?.color }}>{mode} {pkgInfo?.ko}</strong> — {PKG_DESC[mode]}
          </p>
        )}
      </div>

      {/* ── 세계 가정 (모형 레버) ── 정책과 독립. 두 모드 공통 ── */}
      <div className="bg-white border border-[#E5E7EB] rounded-[10px] p-4">
        <div className="text-[12px] font-semibold text-[#111827] mb-0.5">세계 가정 — 감축기술비용·에너지비용</div>
        <div className="text-[10.5px] text-[#9CA3AF] mb-2.5">
          위 운영규칙이 <strong>정부가 무엇을 약속하는가</strong>라면, 아래는 <strong>어떤 세계에서 그러는가</strong>다.
          값 목록은 엔진이 마스터 엑셀에서 읽어온다.
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <LeverSelect label="수소가격 경로" hint="H₂-DRI 비용을 구동"
                       value={h2Sc} onChange={setH2Sc}
                       options={meta?.model_levers?.h2_scenario?.values ?? []} />
          <LeverSelect label="전력가격 경로" hint="e-NCC·전기가열로 비용을 구동"
                       value={elecSc} onChange={setElecSc}
                       options={meta?.model_levers?.elec_scenario?.values ?? []} />
          <LeverSelect label="학습곡선" hint="미지정이면 Cap 시나리오를 따른다"
                       value={techSc} onChange={setTechSc} allowEmpty emptyLabel="Cap 시나리오 추종"
                       options={meta?.model_levers?.tech_scenario?.values ?? []} />
          <div>
            <div className="text-[11px] font-medium text-[#374151] mb-1">감축기술 자본비용</div>
            <Slider label="배율" display={`×${costMult.toFixed(2)}`} min={0.6} max={1.4} step={0.05}
                    value={costMult} onChange={setCostMult} accent="#B45309" />
            <div className="text-[10px] text-[#9CA3AF] mt-0.5 leading-[1.5]">논문 민감도 = ×0.8 / ×1.0 / ×1.2</div>
          </div>
        </div>
        <p className="text-[10.5px] text-[#6B7280] leading-[1.6] mt-2.5 mb-0">
          헤드라인 2기술(H₂-DRI · e-NCC)은 에너지가격 채널을 타므로 <strong>학습곡선에 반응하지 않는다</strong> —
          같은 학습을 두 번 세지 않기 위한 설계다. 이 기술들의 문턱 연도를 흔들려면 에너지가격 경로나 자본비용 배율을 쓴다.
        </p>
      </div>

      <div className={`grid gap-5 ${isPkg ? 'grid-cols-1' : 'grid-cols-[1fr_320px]'}`}>
        {/* ── 왼쪽: 결과 ── */}
        <div className="space-y-4">
          {isPkg ? <PackageResult pkg={pkg} mode={mode} loading={loading} />
                 : <CustomResult rows={rows} loading={loading} scenario={scenario} maccMode={maccMode} />}
        </div>

        {/* ── 오른쪽: 커스텀 레버 ── */}
        {!isPkg && (
          <div className="space-y-3">
            {/* Cap 시나리오 · MACC 방식 */}
            <div className="bg-white border border-[#E5E7EB] rounded-[10px] p-4">
              <div className="text-[12px] font-semibold text-[#111827] mb-2">Cap 시나리오 (NDC 기반)</div>
              <div className="space-y-1.5">
                {(meta?.scenarios ?? ['base', 'middle', 'ideal']).map(id => {
                  const s = SCEN[id as ScenarioId];
                  const active = scenario === id;
                  return (
                    <button key={id} onClick={() => setScenario(id as ScenarioId)}
                      className={`w-full text-left px-3 py-2 rounded-md text-[11.5px] border transition-all ${
                        active ? 'border-current font-semibold' : 'border-[#E5E7EB] text-[#6B7280]'
                      }`}
                      style={active ? { color: s?.color, borderColor: s?.color, background: '#FAFAFA' } : {}}>
                      {s ? `${s.ko} (${s.en})` : id}
                    </button>
                  );
                })}
              </div>
              <div className="text-[12px] font-semibold text-[#111827] mt-3 mb-2">MACC 방식</div>
              <div className="grid grid-cols-2 gap-1.5">
                {(meta?.macc_modes ?? ['step', 'exponential']).map(m => (
                  <button key={m} onClick={() => setMaccMode(m)}
                    aria-pressed={maccMode === m}
                    className={`rounded border px-2 py-1.5 text-[10.5px] transition-all ${
                      maccMode === m
                        ? 'border-[#111827] bg-[#111827] text-white'
                        : 'border-[#E5E7EB] text-[#6B7280] hover:bg-[#F9FAFB]'
                    }`}>
                    {MACC_MODE_LABELS[m] ?? m}
                  </button>
                ))}
              </div>
            </div>

            {/* K-MSR 물량규칙 */}
            <div className="bg-white border border-[#E5E7EB] rounded-[10px] p-4">
              <div className="text-[12px] font-semibold text-[#111827]">K-MSR 물량규칙</div>
              <div className="text-[10px] text-[#9CA3AF] mt-0.5 mb-2">
                초기값 = 시행령 draft 규칙 (엔진 SSOT) · 4기 예비분 {MSR_RESERVE_MT.toFixed(1)} Mt ·
                가격범위 {KMSR_DRAFT_ASSUMPTIONS.announcementDue} 공고 예정
              </div>
              <Slider label="흡수율 ρ" display={rho.toFixed(2)} min={0} max={0.5} step={0.01}
                      value={rho} onChange={setRho} />
              <Slider label="흡수 임계 θ⁺" display={`${thetaPlus.toFixed(0)} Mt`} min={0} max={150} step={1}
                      value={thetaPlus} onChange={setThetaPlus} />
              <Slider label="방출 임계 θ⁻" display={`${thetaMinus.toFixed(0)} Mt`} min={0} max={50} step={1}
                      value={thetaMinus} onChange={setThetaMinus} />
              <Slider label="연간 방출량" display={`${release.toFixed(0)} Mt`} min={0} max={40} step={1}
                      value={release} onChange={setRelease} />
              <Slider label="영구취소율" display={`${(cancel * 100).toFixed(0)}%`} min={0} max={1} step={0.05}
                      value={cancel} onChange={setCancel} />
            </div>

            {/* 유동성 (레벨-브리지) */}
            <div className="bg-white border border-[#E5E7EB] rounded-[10px] p-4">
              <div className="text-[12px] font-semibold text-[#111827]">유동성 λ (레벨-브리지)</div>
              <div className="text-[10px] text-[#9CA3AF] mt-0.5 mb-2">
                λ=0 정태 ↔ λ=1 Hotelling · 기본값은 엔진 SSOT (H1-2026 리프라이싱 역산)
              </div>
              <Slider label="초기 λ₀" display={lam0.toFixed(2)} min={0} max={1} step={0.05}
                      value={lam0} onChange={setLam0} accent="#10A574" />
              <Slider label="목표 λ" display={lamTerminal.toFixed(2)} min={0} max={1} step={0.05}
                      value={lamTerminal} onChange={setLamTerminal} accent="#10A574" />
              <Slider label="램프 기간" display={`${rampYears.toFixed(0)}년`} min={0} max={15} step={1}
                      value={rampYears} onChange={setRampYears} accent="#10A574" />
            </div>

            {/* 시세 참고 */}
            <div className="bg-[#F9FAFB] border border-[#E5E7EB] rounded-[10px] p-4 text-[10.5px] leading-[1.6] text-[#6B7280]" style={{ fontFamily: 'Inter' }}>
              최근 KAU 시세 <strong className="text-[#111827]">{fmtWon(LATEST_KAU_QUOTE.kau_krw)}원</strong> ({LATEST_KAU_QUOTE.date}) ·
              감시선 {fmtWon(KMSR_DRAFT_ASSUMPTIONS.lowPriceKrw)}~{fmtWon(KMSR_DRAFT_ASSUMPTIONS.highPriceKrw)}원 및
              잉여비율 {Math.round(KMSR_DRAFT_ASSUMPTIONS.lowerSurplusRatio * 100)}~{Math.round(KMSR_DRAFT_ASSUMPTIONS.upperSurplusRatio * 100)}%는
              공고({KMSR_DRAFT_ASSUMPTIONS.announcementDue}) 전 draft 가정
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── 패키지 모드 결과 ───────────────────────────────────────
function PackageResult({ pkg, mode, loading }: { pkg: PkgResponse | null; mode: PackageId; loading: boolean }) {
  const info = PKG[mode];
  const at = (y: number) => pkg?.path.find(r => r.year === y);
  const p30 = at(2030);
  const p35 = at(2035);
  const hasFloor = (pkg?.path ?? []).some(r => r.floor > 0);
  const h2Entry = pkg ? Object.entries(pkg.activation_headline).find(([k]) => k.includes('H₂-DRI')) : null;
  const enccEntry = pkg ? Object.entries(pkg.activation_headline).find(([k]) => k.includes('e-cracker')) : null;
  const h2 = h2Entry?.[1] ?? null;
  const encc = enccEntry?.[1] ?? null;

  return (
    <>
      {/* KPI */}
      <div className="grid grid-cols-4 gap-3">
        <Kpi label="2030 실현가격" value={p30 ? `${fmtWon(Math.round(p30.kau))}원` : '—'}
             sub={p30 && p30.floor > p30.kau_prefloor ? '회랑 하한이 구속' : '펀더멘털 경로'} feature />
        <Kpi label="2035 실현가격" value={p35 ? `${fmtWon(Math.round(p35.kau))}원` : '—'}
             sub={mode === 'A' ? 'H₂-DRI 문턱 앵커' : '실현경로 (λ hold)'} />
        <Kpi label="수소환원제철 (H₂-DRI)" value={h2 ? `${h2}년` : '미달성'}
             sub={h2 ? '학습조정 문턱 도달' : '2040년까지 문턱 미달'} />
        <Kpi label="NCC 전기분해 (e-NCC)" value={encc ? `${encc}년` : '미달성'}
             sub={encc ? '학습조정 문턱 도달' : '2040년까지 문턱 미달'} />
      </div>

      {/* 규칙별 방어·낙폭 배지 */}
      {pkg && (
        <div className="flex flex-wrap gap-2">
          {hasFloor && (
            <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] border ${
              pkg.defended_all ? 'border-[#10A574] text-[#065F46] bg-[#F0FDF4]' : 'border-[#DC2626] text-[#991B1B] bg-[#FEF2F2]'
            }`}>
              {pkg.defended_all ? '✓ 전 연도 하한 방어' : '✗ 방어 실패 연도 존재'} ·
              방어여유 최소 {(pkg.min_headroom * 100).toFixed(1)}%
            </span>
          )}
          {mode === 'B' && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] border border-[#E8A33D] text-[#92400E] bg-[#FEF3C7]">
              무효화 {pkg.cum_intake_Mt.toFixed(0)} Mt · 최대 낙폭 {(pkg.max_drawdown * 100).toFixed(1)}% — 수량일정의 변동성 비용
            </span>
          )}
          {mode === 'P1' && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] border border-[#DC2626] text-[#991B1B] bg-[#FEF2F2]">
              최대 낙폭 {(pkg.max_drawdown * 100).toFixed(1)}% — 2031 방출전환 waterbed
            </span>
          )}
        </div>
      )}

      {/* 가격경로 차트 */}
      <div className="bg-white border border-[#E5E7EB] rounded-[10px] p-4">
        <div className="flex items-baseline justify-between mb-2">
          <div>
            <h3 className="text-[14px] font-semibold text-[#111827] m-0">KAU 가격경로 (원/tCO₂)</h3>
            <div className="text-[10.5px] text-[#9CA3AF] mt-1" style={{ fontFamily: 'Inter' }}>
              Live engine · POST /api/solve · package {mode}
            </div>
          </div>
          {loading && <span className="text-[11px] text-[#9CA3AF]" style={{ fontFamily: 'Inter' }}>계산 중…</span>}
        </div>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={pkg?.path ?? []} margin={{ top: 8, right: 14, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#EEF0F2" vertical={false} />
            <XAxis dataKey="year" stroke="#9CA3AF" tick={TICK} tickLine={false} />
            <YAxis stroke="#9CA3AF" tick={TICK} tickLine={false} axisLine={false} tickFormatter={fmtWonK} />
            <Tooltip contentStyle={TOOLTIP_STYLE}
                     formatter={(v: unknown) => fmtWon(Math.round(Number(v ?? 0))) + ' 원'}
                     labelFormatter={(l) => l + '년'} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {h2 && (
              <ReferenceLine x={h2} stroke="#D1D5DB" strokeDasharray="2 4"
                label={{ value: `H₂-DRI ${h2}`, fontSize: 9.5, fill: '#9CA3AF', position: 'insideTopLeft' }} />
            )}
            {encc && (
              <ReferenceLine x={encc} stroke="#D1D5DB" strokeDasharray="2 4"
                label={{ value: `e-NCC ${encc}`, fontSize: 9.5, fill: '#9CA3AF', position: 'insideTopRight' }} />
            )}
            <Line dataKey="static" name="정태 (λ=0)" stroke="#D1D5DB" strokeWidth={1.2} strokeDasharray="5 3" dot={false} />
            <Line dataKey="hotelling" name="Hotelling (λ=1)" stroke="#AEB9CC" strokeWidth={1.2} dot={false} />
            {hasFloor && (
              <Line dataKey="floor" name="경매보류가격 (회랑 하한)" stroke={info.color}
                    strokeWidth={1.4} strokeDasharray="4 3" dot={false} />
            )}
            <Line dataKey="kau" name={`실현 (${mode} ${info.ko})`} stroke={info.color} strokeWidth={2.6} dot={false} />
          </LineChart>
        </ResponsiveContainer>
        <p className="text-[10.5px] text-[#6B7280] leading-[1.6] mt-2 mb-0">
          <strong>실현</strong>(굵은선) = λ 레벨-브리지 + {hasFloor ? '경매보류가격 overlay (하한이 구속하면 하한이 가격)' : '수량규칙 흡수 반영'} ·
          방어요건 W ≤ a·Cap은 기발표 경매물량 한도 내에서 판정.
        </p>
      </div>

      {/* Banking · 흡수 보조 차트 */}
      <div className="bg-white border border-[#E5E7EB] rounded-[10px] p-4">
        <div className="flex items-baseline justify-between mb-2">
          <h3 className="text-[13px] font-semibold text-[#111827] m-0">Banking 잔고 · MSR 흡수</h3>
          <div className="text-[10px] text-[#9CA3AF]" style={{ fontFamily: 'Inter' }}>
            bank_Mt (좌) · intake_Mt (우)
          </div>
        </div>
        <ResponsiveContainer width="100%" height={150}>
          <ComposedChart data={pkg?.path ?? []} margin={{ top: 4, right: 6, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#EEF0F2" vertical={false} />
            <XAxis dataKey="year" stroke="#9CA3AF" tick={{ ...TICK, fontSize: 9.5 }} tickLine={false} />
            <YAxis yAxisId="bank" stroke="#9CA3AF" tick={{ ...TICK, fontSize: 9.5 }} tickLine={false} axisLine={false} unit=" Mt" />
            <YAxis yAxisId="intake" orientation="right"
                   stroke="#9CA3AF" tick={{ ...TICK, fontSize: 9.5 }} tickLine={false} axisLine={false} unit=" Mt" />
            <Tooltip contentStyle={{ ...TOOLTIP_STYLE, fontSize: 10.5 }}
                     formatter={(v: unknown) => `${Number(v ?? 0).toFixed(1)} Mt`}
                     labelFormatter={(l) => l + '년'} />
            <Area yAxisId="bank" dataKey="bank_Mt" name="Banking 잔고" stroke="#5B7BAA" fill="#E3EAF4"
                  strokeWidth={1.6} fillOpacity={0.6} dot={false} />
            <Line yAxisId="intake" dataKey="intake_Mt" name="MSR 흡수(무효화)" stroke={PKG.B.color} strokeWidth={2} dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}

// ─── 커스텀 모드 결과 ───────────────────────────────────────
function CustomResult({ rows, loading, scenario, maccMode }: {
  rows: PathRow[]; loading: boolean; scenario: string; maccMode: string;
}) {
  const p30 = rows.find(r => r.year === 2030);
  const net30 = p30 ? p30.kau_realized - p30.static : 0;
  return (
    <>
      {/* KPI */}
      <div className="grid grid-cols-3 gap-3">
        <Kpi label="2030 실현가격" value={p30 ? `${fmtWon(Math.round(p30.kau_realized))}원` : '—'}
             sub={p30 ? `${net30 >= 0 ? '+' : ''}${fmtWon(Math.round(net30))} vs 정태` : '계산 대기'} feature />
        <Kpi label="2030 정태 (λ=0)" value={p30 ? `${fmtWon(Math.round(p30.static))}원` : '—'} sub="현 얇은시장 anchor" />
        <Kpi label="2030 Hotelling (λ=1)" value={p30 ? `${fmtWon(Math.round(p30.hotelling))}원` : '—'} sub="완전차익거래 anchor" />
      </div>

      {/* 가격경로 차트 */}
      <div className="bg-white border border-[#E5E7EB] rounded-[10px] p-4">
        <div className="flex items-baseline justify-between mb-2">
          <div>
            <h3 className="text-[14px] font-semibold text-[#111827] m-0">KAU 가격경로 (원/tCO₂)</h3>
            <div className="text-[10.5px] text-[#9CA3AF] mt-1" style={{ fontFamily: 'Inter' }}>
              Live engine · POST /api/solve · {scenario} / {maccMode} / custom
            </div>
          </div>
          {loading && <span className="text-[11px] text-[#9CA3AF]" style={{ fontFamily: 'Inter' }}>계산 중…</span>}
        </div>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={rows} margin={{ top: 8, right: 14, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#EEF0F2" vertical={false} />
            <XAxis dataKey="year" stroke="#9CA3AF" tick={TICK} tickLine={false} />
            <YAxis stroke="#9CA3AF" tick={TICK} tickLine={false} axisLine={false} tickFormatter={fmtWonK} />
            <Tooltip contentStyle={TOOLTIP_STYLE}
                     formatter={(v: unknown) => fmtWon(Math.round(Number(v ?? 0))) + ' 원'}
                     labelFormatter={(l) => l + '년'} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line dataKey="eua" name="EUA 참조" stroke={EUA_COLOR} strokeWidth={1.3} strokeDasharray="2 3" dot={false} />
            <Line dataKey="static" name="정태 (λ=0)" stroke="#9CA3AF" strokeWidth={1.6} strokeDasharray="5 3" dot={false} />
            <Line dataKey="hotelling" name="Hotelling (λ=1)" stroke="#5B7BAA" strokeWidth={1.8} dot={false} />
            <Line dataKey="kau_realized" name="실현 (유동성 반영)" stroke="#111827" strokeWidth={2.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
        <p className="text-[10.5px] text-[#6B7280] leading-[1.6] mt-2 mb-0">
          <strong>정태</strong>(회색점선) = 차익거래 없는 현 얇은시장, <strong>Hotelling</strong>(파랑) = 완전차익거래 펀더멘털,{' '}
          <strong>실현</strong>(검정) = λ로 두 anchor를 보간한 레벨-브리지 가격.
        </p>
      </div>

      {/* λ · Banking 보조 차트 */}
      <div className="bg-white border border-[#E5E7EB] rounded-[10px] p-4">
        <div className="flex items-baseline justify-between mb-2">
          <h3 className="text-[13px] font-semibold text-[#111827] m-0">λ 경로 · Banking 잔고</h3>
          <div className="text-[10px] text-[#9CA3AF]" style={{ fontFamily: 'Inter' }}>
            bank_Mt (좌) · λ (우, 0–1)
          </div>
        </div>
        <ResponsiveContainer width="100%" height={150}>
          <ComposedChart data={rows} margin={{ top: 4, right: 6, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#EEF0F2" vertical={false} />
            <XAxis dataKey="year" stroke="#9CA3AF" tick={{ ...TICK, fontSize: 9.5 }} tickLine={false} />
            <YAxis yAxisId="mt" stroke="#9CA3AF" tick={{ ...TICK, fontSize: 9.5 }} tickLine={false} axisLine={false} unit=" Mt" />
            <YAxis yAxisId="lam" orientation="right" domain={[0, 1]} ticks={[0, 0.5, 1]}
                   stroke="#9CA3AF" tick={{ ...TICK, fontSize: 9.5 }} tickLine={false} axisLine={false} />
            <Tooltip contentStyle={{ ...TOOLTIP_STYLE, fontSize: 10.5 }}
                     formatter={(v: unknown, name) =>
                       name === 'λ (유동성)' ? Number(v ?? 0).toFixed(2) : `${Number(v ?? 0).toFixed(1)} Mt`}
                     labelFormatter={(l) => l + '년'} />
            <Area yAxisId="mt" dataKey="bank_Mt" name="Banking 잔고" stroke="#5B7BAA" fill="#E3EAF4"
                  strokeWidth={1.6} fillOpacity={0.6} dot={false} />
            <Line yAxisId="lam" dataKey="lambda" name="λ (유동성)" stroke="#10A574" strokeWidth={2} dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}

// ─── 소품 컴포넌트 ──────────────────────────────────────────
function Kpi({ label, value, sub, feature }: { label: string; value: string; sub: string; feature?: boolean }) {
  return (
    <div className={`border rounded-[10px] px-4 py-3 ${feature ? 'bg-[#111827] border-[#111827]' : 'bg-white border-[#E5E7EB]'}`}>
      <div className="text-[10.5px] text-[#9CA3AF]">{label}</div>
      <div className={`text-[19px] font-bold tracking-[-0.02em] my-0.5 ${feature ? 'text-white' : 'text-[#111827]'}`}
           style={{ fontFamily: 'Inter' }}>
        {value}
      </div>
      <div className={`text-[10px] ${feature ? 'text-[#AEB9CC]' : 'text-[#6B7280]'}`} style={{ fontFamily: 'Inter' }}>{sub}</div>
    </div>
  );
}

/** 시나리오 레버 선택 — 옵션은 엔진이 시트에서 읽어 내려준 값 그대로. */
function LeverSelect({ label, hint, value, onChange, options, allowEmpty, emptyLabel }: {
  label: string; hint: string;
  value: string; onChange: (v: string) => void;
  options: string[];
  allowEmpty?: boolean; emptyLabel?: string;
}) {
  return (
    <label className="block">
      <span className="block text-[11px] font-medium text-[#374151] mb-1">{label}</span>
      <select value={value} onChange={e => onChange(e.target.value)}
        className="w-full rounded-md border border-[#E5E7EB] bg-white px-2 py-1.5 text-[11.5px] text-[#111827]">
        {allowEmpty && <option value="">{emptyLabel ?? '기본'}</option>}
        {options.map(o => <option key={o} value={o}>{LEVER_LABELS[o] ?? o}</option>)}
      </select>
      <span className="block text-[10px] text-[#9CA3AF] mt-0.5 leading-[1.5]">{hint}</span>
    </label>
  );
}

function Slider({ label, display, min, max, step, value, onChange, accent = '#5B7BAA' }: {
  label: string; display: string;
  min: number; max: number; step: number;
  value: number; onChange: (v: number) => void;
  accent?: string;
}) {
  return (
    <label className="block mb-2.5 last:mb-0">
      <span className="flex justify-between text-[10.5px] mb-0.5">
        <span className="text-[#6B7280]">{label}</span>
        <span className="font-semibold text-[#111827]" style={{ fontFamily: 'Inter' }}>{display}</span>
      </span>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(parseFloat(e.target.value))}
        className="w-full" style={{ accentColor: accent }} />
    </label>
  );
}

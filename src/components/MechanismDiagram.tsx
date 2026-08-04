'use client';

/**
 * 가격 결정 메커니즘 도형 — ASCII 아트를 대체하는 SVG 2종.
 *
 *  1) FlowDiagram    공급·수요 → 시장청산 → 이월(Hotelling) → λ 전달 → 실현가격 → 두 갈래 결과
 *  2) LambdaBridge   정태 ↔ Hotelling 수직선 위에 관측 λ 위치를 찍는 그림 (모형의 핵심)
 *
 * 숫자는 전부 results_v1.json(P0 2026행)에서 온다 — 하드코딩 없음.
 */

import { pkgRowAt } from '@/lib/results';

const NAVY = '#1f4e79';
const INK = '#111827';
const MUTE = '#6B7280';
const LINE = '#D1D5DB';
const PANEL = '#F9FAFB';
const GREEN = '#10A574';
const AMBER = '#F59E0B';
const BLUE = '#3B82F6';

const won = (v: number) => `${Math.round(v).toLocaleString('ko-KR')}원`;

/* ── 공용 프리미티브 ──────────────────────────────────────── */

function Box({
  x, y, w, h, title, sub, accent = NAVY, fill = '#FFFFFF', dashed = false,
}: {
  x: number; y: number; w: number; h: number;
  title: string; sub?: string; accent?: string; fill?: string; dashed?: boolean;
}) {
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={8}
            fill={fill} stroke={accent} strokeWidth={1.4}
            strokeDasharray={dashed ? '5 4' : undefined} />
      <rect x={x} y={y} width={4} height={h} rx={2} fill={accent} />
      <text x={x + w / 2} y={sub ? y + h / 2 - 6 : y + h / 2 + 5}
            textAnchor="middle" fontSize={14} fontWeight={700} fill={INK}>{title}</text>
      {sub && (
        <text x={x + w / 2} y={y + h / 2 + 14} textAnchor="middle"
              fontSize={11.5} fill={MUTE}>{sub}</text>
      )}
    </g>
  );
}

function Arrow({ x1, y1, x2, y2, label, color = LINE, dashed = false }: {
  x1: number; y1: number; x2: number; y2: number;
  label?: string; color?: string; dashed?: boolean;
}) {
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  const horizontal = Math.abs(y2 - y1) < Math.abs(x2 - x1);
  return (
    <g>
      <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth={1.6}
            strokeDasharray={dashed ? '4 4' : undefined} markerEnd="url(#arrowhead)" />
      {label && (
        <text x={horizontal ? mx : mx + 8} y={horizontal ? my - 7 : my}
              textAnchor={horizontal ? 'middle' : 'start'}
              dominantBaseline={horizontal ? 'auto' : 'middle'}
              fontSize={11} fontWeight={600} fill={MUTE}>{label}</text>
      )}
    </g>
  );
}

/* ── 1. 전체 흐름도 ───────────────────────────────────────── */

export function FlowDiagram() {
  return (
    <figure className="my-4 overflow-x-auto">
      <svg viewBox="0 0 940 508" role="img" width="100%"
           style={{ minWidth: 620, display: 'block' }}
           aria-label="배출권 가격 결정 흐름도: 공급과 수요가 시장에서 만나 정태가격을 만들고, 이월이 미래 희소성을 당겨와 Hotelling 가격을 만들며, 유동성 전달계수 람다가 두 값을 잇는 실현가격을 결정한다.">
        <defs>
          <marker id="arrowhead" markerWidth="9" markerHeight="7"
                  refX="8" refY="3.5" orient="auto">
            <polygon points="0 0, 9 3.5, 0 7" fill={LINE} />
          </marker>
          <linearGradient id="bridgeGrad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={BLUE} />
            <stop offset="100%" stopColor={NAVY} />
          </linearGradient>
        </defs>

        {/* 1행 — 공급 · 수요 */}
        <text x={470} y={20} textAnchor="middle" fontSize={11} fontWeight={700}
              fill={MUTE} letterSpacing={1.2}>① 그 해의 수급</text>

        <Box x={40} y={34} w={250} h={68} accent={NAVY}
             title="공급 — 정부" sub="배출허용총량(cap) · 무상/유상 배분 · K-MSR" />
        <Box x={650} y={34} w={250} h={68} accent={AMBER}
             title="수요 — 기업" sub="BAU 배출 − 감축(MACC 계단)" />

        <Arrow x1={290} y1={68} x2={392} y2={68} label="공급" />
        <Arrow x1={650} y1={68} x2={548} y2={68} label="수요" />

        {/* 2행 — 시장청산 */}
        <Box x={392} y={38} w={156} h={60} accent={INK} fill={PANEL}
             title="단일 시장" sub="경매 = 1차 · 장내 = 2차" />

        <Arrow x1={470} y1={98} x2={470} y2={132} />

        <Box x={330} y={132} w={280} h={62} accent={BLUE} fill="#EFF6FF"
             title="정태 균형가격  P_static" sub="그 해 수급만으로 청산 (λ = 0)" />

        {/* 3행 — 이월/Hotelling */}
        <text x={470} y={222} textAnchor="middle" fontSize={11} fontWeight={700}
              fill={MUTE} letterSpacing={1.2}>② 시점 간 연결</text>

        <Arrow x1={470} y1={194} x2={470} y2={236} />

        <Box x={330} y={236} w={280} h={62} accent={NAVY} fill="#EEF4FA"
             title="Hotelling 가격  P_hotelling" sub="이월로 미래 희소성 반영 (λ = 1)" />

        <Box x={648} y={236} w={252} h={62} accent={LINE} fill="#FFFFFF" dashed
             title="이월 상한" sub="상한에 걸리면 상승률 > 이자율 가능" />
        <Arrow x1={648} y1={267} x2={614} y2={267} dashed />

        <Box x={40} y={236} w={252} h={62} accent={LINE} fill="#FFFFFF" dashed
             title="학습곡선" sub="기술비용 ↓ → 문턱 ↓" />
        <Arrow x1={292} y1={267} x2={326} y2={267} dashed />

        {/* 4행 — λ 전달 */}
        <text x={470} y={326} textAnchor="middle" fontSize={11} fontWeight={700}
              fill={MUTE} letterSpacing={1.2}>③ 유동성 전달</text>

        <Arrow x1={470} y1={298} x2={470} y2={340} />

        <rect x={250} y={340} width={440} height={46} rx={8}
              fill="url(#bridgeGrad)" opacity={0.10} stroke={NAVY} strokeWidth={1.4} />
        <text x={470} y={362} textAnchor="middle" fontSize={13.5} fontWeight={700} fill={INK}>
          실현가격 = P_static + λ · ( P_hotelling − P_static )
        </text>
        <text x={470} y={378} textAnchor="middle" fontSize={11} fill={MUTE}>
          λ = 관측가에서 역산 — 시장이 미래를 얼마나 오늘로 옮기는가
        </text>

        {/* 5행 — 결과 두 갈래 */}
        <Arrow x1={470} y1={386} x2={470} y2={414} />
        <line x1={250} y1={414} x2={690} y2={414} stroke={LINE} strokeWidth={1.6} />
        <Arrow x1={250} y1={414} x2={250} y2={440} />
        <Arrow x1={690} y1={414} x2={690} y2={440} />

        <Box x={100} y={440} w={300} h={58} accent={GREEN} fill="#F0FDF4"
             title="전환기술 문턱 도달 연도" sub="H₂-DRI · e-NCC 투자 신호" />
        <Box x={540} y={440} w={300} h={58} accent={AMBER} fill="#FFFBEB"
             title="K-MSR 운영규칙이 개입" sub="가격약속(A) · 수량약속(B)" />
      </svg>
      <figcaption className="text-[11.5px] text-[#6B7280] mt-2 leading-[1.6]">
        점선 상자는 가격을 직접 만들지는 않지만 경로의 모양을 바꾸는 제약이다.
        ①은 그 해의 청산, ②는 시점 간 연결, ③은 둘 사이 어디에 실제 가격이 놓이는지를 정한다.
      </figcaption>
    </figure>
  );
}

/* ── 2. λ 브리지 ──────────────────────────────────────────── */

export function LambdaBridge({ year = 2026 }: { year?: number }) {
  const row = pkgRowAt('P0', year);
  if (!row) return null;

  const { static: ps, hotelling: ph, kau, lambda } = row;
  const X0 = 110, X1 = 830, Y = 108;
  const pos = (v: number) => X0 + ((v - ps) / (ph - ps)) * (X1 - X0);
  const xNow = pos(kau);

  return (
    <figure className="my-4 overflow-x-auto">
      <svg viewBox="0 0 940 214" role="img" width="100%"
           style={{ minWidth: 620, display: 'block' }}
           aria-label={`${year}년 실현가격 ${won(kau)}은 정태 ${won(ps)}과 Hotelling ${won(ph)} 사이 λ=${lambda}에 위치한다.`}>
        <defs>
          <linearGradient id="lamGrad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={BLUE} />
            <stop offset="100%" stopColor={NAVY} />
          </linearGradient>
        </defs>

        <text x={470} y={22} textAnchor="middle" fontSize={11} fontWeight={700}
              fill={MUTE} letterSpacing={1.2}>
          {year}년 실현가격은 두 극단 사이 어디에 있나
        </text>

        {/* 축 */}
        <rect x={X0} y={Y - 7} width={X1 - X0} height={14} rx={7}
              fill="url(#lamGrad)" opacity={0.18} />
        <line x1={X0} y1={Y} x2={X1} y2={Y} stroke={LINE} strokeWidth={1.5} />

        {/* 좌 끝 — 정태 */}
        <line x1={X0} y1={Y - 20} x2={X0} y2={Y + 20} stroke={BLUE} strokeWidth={2.5} />
        <text x={X0} y={Y - 30} textAnchor="middle" fontSize={12.5} fontWeight={700} fill={BLUE}>
          λ = 0 · 정태
        </text>
        <text x={X0} y={Y + 38} textAnchor="middle" fontSize={13.5} fontWeight={700} fill={INK}>
          {won(ps)}
        </text>
        <text x={X0} y={Y + 54} textAnchor="middle" fontSize={11} fill={MUTE}>
          미래를 전혀 반영 못 함
        </text>

        {/* 우 끝 — Hotelling */}
        <line x1={X1} y1={Y - 20} x2={X1} y2={Y + 20} stroke={NAVY} strokeWidth={2.5} />
        <text x={X1} y={Y - 30} textAnchor="middle" fontSize={12.5} fontWeight={700} fill={NAVY}>
          λ = 1 · Hotelling
        </text>
        <text x={X1} y={Y + 38} textAnchor="middle" fontSize={13.5} fontWeight={700} fill={INK}>
          {won(ph)}
        </text>
        <text x={X1} y={Y + 54} textAnchor="middle" fontSize={11} fill={MUTE}>
          완전한 시점 간 차익거래
        </text>

        {/* 현재 위치 */}
        <line x1={xNow} y1={Y - 44} x2={xNow} y2={Y + 16} stroke={GREEN} strokeWidth={2} />
        <circle cx={xNow} cy={Y} r={8} fill={GREEN} stroke="#FFFFFF" strokeWidth={2.5} />
        <rect x={xNow - 86} y={Y - 82} width={172} height={38} rx={7}
              fill="#F0FDF4" stroke={GREEN} strokeWidth={1.4} />
        <text x={xNow} y={Y - 66} textAnchor="middle" fontSize={13} fontWeight={700} fill="#065F46">
          실현 {won(kau)}
        </text>
        <text x={xNow} y={Y - 52} textAnchor="middle" fontSize={11.5} fontWeight={600} fill="#047857">
          λ = {lambda.toFixed(3)}
        </text>

        <text x={470} y={192} textAnchor="middle" fontSize={11.5} fill={MUTE}>
          λ는 가정이 아니라 관측 KAU 시세에서 역산한 값이다 — scripts/calibrate_liquidity.py가 재계산해 대조한다.
        </text>
      </svg>
    </figure>
  );
}

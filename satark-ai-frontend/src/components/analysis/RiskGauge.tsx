import { useEffect, useRef } from 'react'

export type Verdict = 'SAFE' | 'SUSPICIOUS' | 'PHISHING'

interface RiskGaugeProps {
  score: number        // 0–100
  verdict: Verdict
  size?: number        // SVG viewport size, default 240
  animated?: boolean
}

// ── Helpers ────────────────────────────────────────────────────────────────────
const VERDICT_COLOR: Record<Verdict, string> = {
  SAFE: '#22C55E',
  SUSPICIOUS: '#F59E0B',
  PHISHING: '#EF4444',
}

const VERDICT_GLOW: Record<Verdict, string> = {
  SAFE: 'drop-shadow(0 0 8px rgba(34,197,94,0.6))',
  SUSPICIOUS: 'drop-shadow(0 0 8px rgba(245,158,11,0.6))',
  PHISHING: 'drop-shadow(0 0 8px rgba(239,68,68,0.6))',
}

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180
  return {
    x: cx + r * Math.cos(rad),
    y: cy + r * Math.sin(rad),
  }
}

function arcPath(cx: number, cy: number, r: number, startAngle: number, endAngle: number): string {
  const start = polarToCartesian(cx, cy, r, endAngle)
  const end = polarToCartesian(cx, cy, r, startAngle)
  const largeArc = endAngle - startAngle > 180 ? 1 : 0
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y}`
}

// Gauge sweeps from -135° to +135° (270° total arc)
const START_ANGLE = -135
const END_ANGLE   = 135
const TOTAL_SWEEP = END_ANGLE - START_ANGLE // 270

export default function RiskGauge({
  score,
  verdict,
  size = 240,
  animated = true,
}: RiskGaugeProps) {
  const clampedScore = Math.min(100, Math.max(0, score))
  const fillAngle = START_ANGLE + (clampedScore / 100) * TOTAL_SWEEP

  const cx = size / 2
  const cy = size / 2
  const outerR = size * 0.42
  const innerR = size * 0.30
  const trackR  = (outerR + innerR) / 2
  const strokeW = outerR - innerR

  const color = VERDICT_COLOR[verdict]
  const glow  = VERDICT_GLOW[verdict]

  // Stroke-dasharray animation on arc element
  const arcRef = useRef<SVGPathElement>(null)

  useEffect(() => {
    if (!animated || !arcRef.current) return
    const el = arcRef.current
    const len = el.getTotalLength()
    el.style.strokeDasharray = `${len}`
    el.style.strokeDashoffset = `${len}`
    el.style.transition = 'none'
    // trigger reflow
    void el.getBoundingClientRect()
    requestAnimationFrame(() => {
      el.style.transition = 'stroke-dashoffset 1s cubic-bezier(0.4, 0, 0.2, 1)'
      el.style.strokeDashoffset = '0'
    })
  }, [score, animated])

  return (
    <div className="flex flex-col items-center gap-2">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        aria-label={`Risk score: ${clampedScore} out of 100`}
        role="img"
      >
        {/* Track (background arc) */}
        <path
          d={arcPath(cx, cy, trackR, START_ANGLE, END_ANGLE)}
          fill="none"
          stroke="#1E293B"
          strokeWidth={strokeW}
          strokeLinecap="round"
        />

        {/* Fill arc */}
        {clampedScore > 0 && (
          <path
            ref={arcRef}
            d={arcPath(cx, cy, trackR, START_ANGLE, fillAngle)}
            fill="none"
            stroke={color}
            strokeWidth={strokeW}
            strokeLinecap="round"
            style={{ filter: glow }}
          />
        )}

        {/* Centre label */}
        <text
          x={cx}
          y={cy - 4}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize={size * 0.18}
          fontWeight="800"
          fill={color}
          fontFamily="Inter, sans-serif"
        >
          {clampedScore}
        </text>
        <text
          x={cx}
          y={cy + size * 0.11}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize={size * 0.07}
          fill="#94A3B8"
          fontFamily="Inter, sans-serif"
        >
          / 100
        </text>

        {/* Min / Max labels */}
        <text
          x={cx - outerR * 0.97}
          y={cy + outerR * 0.55}
          textAnchor="middle"
          fontSize={size * 0.055}
          fill="#475569"
          fontFamily="Inter, sans-serif"
        >
          0
        </text>
        <text
          x={cx + outerR * 0.97}
          y={cy + outerR * 0.55}
          textAnchor="middle"
          fontSize={size * 0.055}
          fill="#475569"
          fontFamily="Inter, sans-serif"
        >
          100
        </text>
      </svg>

      <p className="text-xs font-medium text-slate-400 tracking-widest uppercase">Risk Score</p>
    </div>
  )
}

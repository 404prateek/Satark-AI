import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'

export interface SHAPFeature {
  feature: string   // human-readable feature name
  value: number     // SHAP value (negative = pushes toward safe, positive = toward phishing)
}

interface SHAPChartProps {
  features: SHAPFeature[]
  maxItems?: number
  isSafeVerdict?: boolean
}

// ── Custom tooltip ─────────────────────────────────────────────────────────────
interface TooltipProps {
  active?: boolean
  payload?: Array<{ payload: SHAPFeature; value: number }>
}

function CustomTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload?.length) return null
  const { feature, value } = payload[0].payload
  const isRisk = value >= 0
  return (
    <div className="bg-[#1E293B] border border-slate-700 rounded-xl px-3 py-2 shadow-xl text-xs">
      <p className="text-slate-300 font-medium mb-0.5">{feature}</p>
      <p className={isRisk ? 'text-red-400' : 'text-green-400'}>
        Impact: {value > 0 ? '+' : ''}{value.toFixed(4)}
      </p>
      <p className="text-slate-500 mt-0.5">
        {isRisk ? '↑ Increases risk' : '↓ Reduces risk'}
      </p>
    </div>
  )
}

// ── Custom Y-axis tick ─────────────────────────────────────────────────────────
interface AxisTickProps {
  x?: number
  y?: number
  payload?: { value: string }
}

function FeatureTick({ x = 0, y = 0, payload }: AxisTickProps) {
  const label = payload?.value ?? ''
  const truncated = label.length > 38 ? label.slice(0, 36) + '…' : label
  return (
    <text
      x={x}
      y={y}
      dy={4}
      textAnchor="end"
      fill="#94A3B8"
      fontSize={11}
      fontFamily="Inter, sans-serif"
    >
      {truncated}
    </text>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function SHAPChart({ features, maxItems = 6, isSafeVerdict = false }: SHAPChartProps) {
  const sorted = [...features]
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    .slice(0, maxItems)
    // recharts horizontal bars render bottom-to-top; reverse so highest impact is on top
    .reverse()

  const barHeight = 34
  const chartHeight = Math.max(200, sorted.length * barHeight + 40)

  // 1. Calculate explicit domain bounds ensuring 0 is always visible
  const values = sorted.map(f => f.value)
  const minValue = Math.min(0, ...values)
  const maxValue = Math.max(0, ...values)

  // 3. Function to determine bar color based on magnitude and sign
  const getBarColor = (val: number) => {
    if (val < 0) return '#22C55E' // negative = green (reduces risk)
    if (val < 0.15) return '#F59E0B' // positive but low = amber (minor nudge)
    return '#EF4444' // positive high = red (strong signal)
  }

  return (
    <div className="w-full">
      <div className="mb-5">
        <div style={{ fontSize: 10, fontFamily: "'Outfit', sans-serif", fontWeight: 700, letterSpacing: '0.12em', color: '#DFFF00', marginBottom: '0.3rem' }}>
          EXPLAINABLE AI
        </div>
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
          Suspicious Keywords/Patterns Detected
        </h3>
        <p className="text-xs text-slate-400 mt-1.5">
          These are the specific words and patterns that pushed this message's risk score up.
        </p>
        {isSafeVerdict && (
          <div className="mt-3 px-3 py-2 rounded-lg" style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.2)' }}>
            <p style={{ fontSize: 11, color: '#4ADE80', margin: 0, fontFamily: "'Inter', sans-serif" }}>
              <strong>Note:</strong> Even safe messages have some contributing words — what matters is the OVERALL score, not individual bars.
            </p>
          </div>
        )}
      </div>

      {sorted.length === 0 ? (
        <p className="text-slate-500 text-sm text-center py-8">No SHAP data available.</p>
      ) : (
        <ResponsiveContainer width="100%" height={chartHeight}>
          <BarChart
            data={sorted}
            layout="vertical"
            margin={{ top: 4, right: 16, left: 8, bottom: 4 }}
          >
            <XAxis
              type="number"
              domain={[minValue, maxValue]}
              tick={{ fill: '#475569', fontSize: 10, fontFamily: 'Inter, sans-serif' }}
              axisLine={{ stroke: '#334155' }}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="feature"
              width={250}
              tick={<FeatureTick />}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              content={<CustomTooltip />}
              cursor={{ fill: 'rgba(255,255,255,0.03)' }}
            />
            <ReferenceLine x={0} stroke="#666" strokeWidth={1} />
            <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={22}>
              {sorted.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={getBarColor(entry.value)}
                  fillOpacity={0.85}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}

      <div className="flex items-center gap-4 mt-3 text-xs text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-sm bg-red-500/80" />
          Increases risk (strong)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-sm bg-amber-500/80" />
          Increases risk (minor)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-sm bg-green-500/80" />
          Reduces risk
        </span>
      </div>
    </div>
  )
}

import { ShieldCheck, ShieldAlert, ShieldX } from 'lucide-react'

export type Verdict = 'SAFE' | 'SUSPICIOUS' | 'PHISHING'

interface VerdictBadgeProps {
  verdict: Verdict
  size?: 'sm' | 'md' | 'lg'
}

const CONFIG: Record<
  Verdict,
  { label: string; bg: string; border: string; text: string; glow: string; Icon: React.ElementType }
> = {
  SAFE: {
    label: 'Safe',
    bg: 'bg-green-500/10',
    border: 'border-green-500/30',
    text: 'text-green-400',
    glow: 'shadow-green-500/20',
    Icon: ShieldCheck,
  },
  SUSPICIOUS: {
    label: 'Suspicious',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    text: 'text-amber-400',
    glow: 'shadow-amber-500/20',
    Icon: ShieldAlert,
  },
  PHISHING: {
    label: 'Phishing',
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
    text: 'text-red-400',
    glow: 'shadow-red-500/20',
    Icon: ShieldX,
  },
}

const SIZE_CLASSES: Record<NonNullable<VerdictBadgeProps['size']>, { wrap: string; icon: string; text: string }> = {
  sm: { wrap: 'px-3 py-1.5 gap-1.5 rounded-lg', icon: 'w-3.5 h-3.5', text: 'text-xs font-semibold' },
  md: { wrap: 'px-4 py-2 gap-2 rounded-xl',   icon: 'w-5 h-5',   text: 'text-sm font-bold' },
  lg: { wrap: 'px-6 py-3 gap-2.5 rounded-2xl', icon: 'w-6 h-6',   text: 'text-lg font-extrabold tracking-wide' },
}

export default function VerdictBadge({ verdict, size = 'md' }: VerdictBadgeProps) {
  const { label, bg, border, text, glow, Icon } = CONFIG[verdict]
  const { wrap, icon, text: textCls } = SIZE_CLASSES[size]

  return (
    <span
      role="status"
      aria-label={`Verdict: ${label}`}
      className={`inline-flex items-center border ${bg} ${border} ${text} ${glow} ${wrap} shadow-lg transition-all duration-300`}
    >
      <Icon className={icon} aria-hidden="true" />
      <span className={`${textCls} uppercase tracking-widest`}>{label}</span>
    </span>
  )
}

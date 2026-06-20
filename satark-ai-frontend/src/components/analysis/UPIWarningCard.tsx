import { IndianRupee, AlertOctagon } from 'lucide-react'

interface UPIDetails {
  upi_found: boolean
  vpa: string
  amount: number | null
  mismatch: {
    mismatch_detected: boolean
    explanation: string
  }
}

interface UPIWarningCardProps {
  upiDetails?: UPIDetails | null
}

export default function UPIWarningCard({ upiDetails }: UPIWarningCardProps) {
  if (!upiDetails?.upi_found) return null

  return (
    <div className="glass p-5 border border-white/10 rounded-xl space-y-4 bg-white/[0.02]">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-green-500/10 flex items-center justify-center">
          <IndianRupee size={16} className="text-green-400" />
        </div>
        <h3 className="text-sm font-bold text-white uppercase tracking-wide">
          UPI Payment Link Detected
        </h3>
      </div>

      <div className="flex flex-wrap gap-x-8 gap-y-2 text-sm">
        <div className="flex items-center gap-2">
          <span className="text-slate-500 font-medium">Pays to:</span>
          <span className="text-slate-200 font-mono">{upiDetails.vpa}</span>
        </div>
        {upiDetails.amount !== null && upiDetails.amount !== undefined && (
          <div className="flex items-center gap-2">
            <span className="text-slate-500 font-medium">Amount:</span>
            <span className="text-slate-200 font-mono font-bold">₹{upiDetails.amount}</span>
          </div>
        )}
      </div>

      {upiDetails.mismatch?.mismatch_detected && (
        <div className="mt-4 bg-red-500/10 border-2 border-red-500 rounded-xl p-4 flex items-start gap-3 shadow-[0_0_15px_rgba(239,68,68,0.2)]">
          <AlertOctagon size={20} className="text-red-500 shrink-0 mt-0.5" />
          <p className="text-red-100 font-bold text-sm leading-relaxed">
            {upiDetails.mismatch.explanation}
          </p>
        </div>
      )}
    </div>
  )
}

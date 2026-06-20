import { QrCode } from 'lucide-react'

interface QRCodeData {
  data: string
  qr_type: string
}

interface QRDetectedBadgeProps {
  qrDetected?: boolean
  qrCodes?: QRCodeData[]
}

export default function QRDetectedBadge({ qrDetected, qrCodes }: QRDetectedBadgeProps) {
  if (!qrDetected || !qrCodes || qrCodes.length === 0) return null

  return (
    <div className="flex flex-col gap-3">
      <div className="inline-flex items-center gap-2 self-start border border-[#DFFF00]/40 bg-[#DFFF00]/10 rounded-full px-3 py-1.5">
        <QrCode size={14} className="text-[#DFFF00]" />
        <span className="text-xs font-bold text-[#DFFF00] uppercase tracking-wide">
          QR Code Detected
        </span>
      </div>
      <div className="flex flex-col gap-2 pl-2 border-l-2 border-[#DFFF00]/20">
        {qrCodes.map((qr, idx) => {
          let typeColor = 'bg-slate-500/20 text-slate-400 border-slate-500/30'
          if (qr.qr_type.toUpperCase() === 'URL') typeColor = 'bg-blue-500/20 text-blue-400 border-blue-500/30'
          else if (qr.qr_type.toUpperCase() === 'UPI') typeColor = 'bg-red-500/20 text-red-400 border-red-500/30'

          const truncated = qr.data.length > 60 ? qr.data.slice(0, 60) + '...' : qr.data

          return (
            <div key={idx} className="flex items-center gap-3">
              <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded border ${typeColor}`}>
                {qr.qr_type}
              </span>
              <span className="font-mono text-xs text-slate-300 break-all" title={qr.data}>
                {truncated}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

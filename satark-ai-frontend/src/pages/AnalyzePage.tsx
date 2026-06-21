import { useState, FormEvent, useRef } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Search, LogOut, Loader2, AlertCircle, Copy, CheckCheck, Zap, Image as ImageIcon, Languages, Link as LinkIcon, Brain, ShieldCheck, FileText, AlertTriangle, X } from 'lucide-react'
import apiClient from '../api/client'
import { useAuthStore } from '../store/authStore'
import RiskGauge, { Verdict } from '../components/analysis/RiskGauge'
import VerdictBadge from '../components/analysis/VerdictBadge'
import SHAPChart, { SHAPFeature } from '../components/analysis/SHAPChart'
import ExplanationCard from '../components/analysis/ExplanationCard'
import FeedbackWidget from '../components/analysis/FeedbackWidget'
import URLReputationPanel from '../components/analysis/URLReputationPanel'
import FeatureShowcase from '../components/landing/FeatureShowcase'
import QRDetectedBadge from '../components/analysis/QRDetectedBadge'
import UPIWarningCard from '../components/analysis/UPIWarningCard'

import { analyzeMessage, analyzeImage, analyzeURL, ScanResponse } from '../api/analyze'
import { extractErrorMessage } from '../api/errorHandling'

const TRIGGER_LABELS: Record<string, string> = {
  urgency_language: "Urgency language",
  otp_extraction: "OTP request",
  phone_number_in_text: "Phone number included",
  url_in_message: "Suspicious link included",
  prize_amount_mentioned: "Prize/cashback amount mentioned",
}

function formatTriggerLabel(trigger: string): string {
  if (TRIGGER_LABELS[trigger]) return TRIGGER_LABELS[trigger];
  
  if (trigger.startsWith("impersonates_")) {
    return `Brand impersonation (${trigger.replace("impersonates_", "")})`;
  }
  if (trigger.startsWith("urgency_")) return "Urgency language";
  if (trigger.startsWith("fear_")) return "Threat or coercion";
  if (trigger.startsWith("prize_")) return "Prize/cashback lure";
  if (trigger.startsWith("cred_")) return "Data extraction attempt";
  if (trigger.startsWith("link_")) return "Suspicious link included";

  // Defensive fallback: strip colons, replace underscores, title case
  return trigger
    .replace(/:/g, " ")
    .replace(/_/g, " ")
    .replace(/\b\w/g, c => c.toUpperCase());
}

// ── Demo presets ─────────────────────────────────────────────────────────────
const DEMO_INPUTS = [
  {
    label: "🔴 Hindi KYC Scam",
    text: "प्रिय ग्राहक, आपका SBI खाता KYC सत्यापन के लिए अनुरोध किया गया है। अभी लिंक पर क्लिक करें: bit.ly/sbi-kyc99 अन्यथा आपका खाता 24 घंटे में बंद हो जाएगा।"
  },
  {
    label: "🔴 Hinglish Prize Scam",
    text: "Congratulations! Aapne Jio Lucky Draw mein Rs 25,00,000 jeeta hai. Apna prize claim karne ke liye abhi call karein: 9876543210"
  },
  {
    label: "🔴 Fake HDFC URL",
    text: "URGENT: Your HDFC account suspended. Verify immediately: hdfc-account-verify.xyz/login?ref=urgent"
  },
  {
    label: "🟢 Real Bank SMS",
    text: "Your HDFC Bank account XX4521 has been credited with Rs.5,000 on 18-Jun-2026. Available balance: Rs.23,450."
  },
  {
    label: "🟡 Job Scam",
    text: "Dear Candidate, You have been selected for Data Entry job. Work from home. Earn Rs 15,000/month. WhatsApp CV: wa.me/919988776655"
  },
  {
    label: "💸 Fake UPI QR Scam",
    text: "🎉 You won ₹5000 cashback! Scan QR to claim: upi://pay?pa=prize-claim@okhdfcbank&pn=PrizeTeam&am=499&cu=INR"
  },
]

// ── Verdict-aware colors ───────────────────────────────────────────────────
function verdictColor(v?: Verdict) {
  if (v === 'PHISHING')   return '#EF4444'
  if (v === 'SUSPICIOUS') return '#F59E0B'
  return '#22C55E'
}

// ── Stat card ──────────────────────────────────────────────────────────────
function StatCard({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div
      className="flex flex-col items-center justify-center py-5 px-4"
      style={{
        background: 'rgba(255,255,255,0.03)',
        border: `1px solid ${accent ?? 'rgba(255,255,255,0.08)'}`,
        borderRadius: 12,
      }}
    >
      <span
        style={{
          fontFamily: "'Syncopate', sans-serif",
          fontSize: 'clamp(1.2rem, 2.5vw, 1.8rem)',
          fontWeight: 700,
          color: accent ?? '#DFFF00',
          lineHeight: 1,
        }}
      >
        {value}
      </span>
      <span
        style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.12em', color: '#555', marginTop: '0.4rem', textAlign: 'center' }}
      >
        {label}
      </span>
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────
export default function AnalyzePage() {
  const { user, logout } = useAuthStore()
  const [message, setMessage] = useState('')
  const [inputTab, setInputTab] = useState<'text' | 'screenshot' | 'url'>('text')
  const [urlInput, setUrlInput] = useState('')
  const [copied, setCopied] = useState(false)

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isLongScreenshot, setIsLongScreenshot] = useState(false)
  const [fileError, setFileError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [scanResult, setScanResult] = useState<ScanResponse | null>(null)

  const messageMutation = useMutation<ScanResponse, Error, string>({
    mutationFn: analyzeMessage,
    onSuccess: (data) => setScanResult(data),
  })

  const imageMutation = useMutation<ScanResponse, Error, File>({
    mutationFn: analyzeImage,
    onSuccess: (data) => setScanResult(data),
  })

  const urlMutation = useMutation<ScanResponse, Error, string>({
    mutationFn: analyzeURL,
    onSuccess: (data) => setScanResult(data),
  })

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setScanResult(null)
    if (inputTab === 'text') {
      if (!message.trim()) return
      messageMutation.mutate(message.trim())
    } else if (inputTab === 'screenshot') {
      if (!selectedFile) return
      imageMutation.mutate(selectedFile)
    } else if (inputTab === 'url') {
      if (!urlInput.trim()) return
      urlMutation.mutate(urlInput.trim())
    }
  }

  const handleExample = (text: string) => {
    setInputTab('text')
    setMessage(text)
    setScanResult(null)
    messageMutation.mutate(text)
  }

  const handleExampleImage = async (imagePath: string, tabName: string) => {
    setInputTab('screenshot')
    setScanResult(null)
    try {
      const response = await fetch(imagePath)
      const blob = await response.blob()
      const file = new File([blob], tabName + '.png', { type: blob.type || 'image/png' })
      setSelectedFile(file)
      // Small delay to allow UI to update the tab before mutation starts
      setTimeout(() => {
        imageMutation.mutate(file)
      }, 50)
    } catch (e) {
      console.error("Failed to load demo image", e)
      alert("Failed to load demo image.")
    }
  }

  const handleCopy = async () => {
    if (!scanResult) return
    await navigator.clipboard.writeText(
      `Verdict: ${scanResult.verdict}\nRisk Score: ${scanResult.risk_score}/100\n\n${scanResult.explanation}`,
    )
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelect(e.dataTransfer.files[0])
    }
  }

  const handleFileSelect = (file: File) => {
    setFileError(null)
    setIsLongScreenshot(false)
    imageMutation.reset()
    if (file.size > 5 * 1024 * 1024) {
      setFileError('File size exceeds 5MB limit.')
      return
    }
    if (!['image/jpeg', 'image/png', 'image/jpg', 'image/webp'].includes(file.type)) {
      setFileError('Invalid file type. Please upload a JPG, PNG, or WEBP image.')
      return
    }
    
    const objUrl = URL.createObjectURL(file)
    const img = new window.Image()
    img.onload = () => {
      const aspectRatio = Math.max(img.width / img.height, img.height / img.width)
      if (aspectRatio > 4) {
        setIsLongScreenshot(true)
      }
    }
    img.src = objUrl
    
    setSelectedFile(file)
    setPreviewUrl(objUrl)
  }

  const clearFile = () => {
    setSelectedFile(null)
    setIsLongScreenshot(false)
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    setPreviewUrl(null)
    setFileError(null)
    imageMutation.reset()
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const result = scanResult
  const isPending = messageMutation.isPending || imageMutation.isPending || urlMutation.isPending
  const isError = messageMutation.isError || urlMutation.isError
  const errorMessage = messageMutation.error ? extractErrorMessage(messageMutation.error) :
                       urlMutation.error ? extractErrorMessage(urlMutation.error) : null
  const vColor = verdictColor(result?.verdict)

  const topReason = (() => {
    if (result?.verdict === 'SAFE') {
      return result.behavioral_triggers?.length > 0
        ? formatTriggerLabel(result.behavioral_triggers[0])
        : 'No significant threat indicators'
    }
    if (result?.behavioral_triggers && result.behavioral_triggers.length > 0) {
      return result.behavioral_triggers.slice(0, 2).map(formatTriggerLabel).join(' + ')
    }
    if (result?.shap_features && result.shap_features.length > 0) {
      // Filter out very short/generic tokens before displaying
      const meaningful = result.shap_features.filter(f => f.feature.length > 3 && f.value > 0)
      if (meaningful.length > 0) return `Suspicious pattern: ${meaningful[0].feature}`
    }
    return 'Suspicious language pattern detected'
  })()

  return (
    <div className="relative w-full flex-1">
      {/* Noise overlay */}
      <div className="noise-overlay" />

      {/* ── Main ─────────────────────────────────────────────────────────── */}
      <main className="max-w-5xl w-full mx-auto px-4 md:px-8 py-12 space-y-10">

        {/* Hero heading */}
        <div className="text-center space-y-3">
          <div
            className="inline-flex items-center gap-2 mb-3"
            style={{
              background: 'rgba(223,255,0,0.05)',
              border: '1px solid rgba(223,255,0,0.15)',
              borderRadius: 100,
              padding: '0.3rem 1rem',
              fontSize: 10,
              fontFamily: "'Outfit', sans-serif",
              fontWeight: 500,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: '#DFFF00',
            }}
          >
            <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#DFFF00', display: 'inline-block', animation: 'pulse-dot 1.5s ease-in-out infinite' }} />
            AI Analysis Ready
          </div>
          <h1
            style={{
              fontFamily: "'Syncopate', sans-serif",
              fontSize: 'clamp(1.8rem, 4vw, 3rem)',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '-0.02em',
              lineHeight: 1.1,
            }}
          >
            Detect Phishing Instantly
          </h1>
          <p style={{ color: '#666', fontSize: 15, maxWidth: 480, margin: '0 auto' }}>
            Get instant risk scores with plain-language explanations — in English, Hindi, or Hinglish.
          </p>

          {/* Capability Chips */}
          <div className="flex flex-wrap justify-center gap-3 pt-6 pb-2">
            {[
              { icon: ImageIcon, label: 'Screenshot OCR' },
              { icon: Languages, label: 'Hindi + Hinglish' },
              { icon: LinkIcon, label: 'Deep URL Scan' },
              { icon: Brain, label: 'Explainable AI' },
              { icon: Zap, label: 'Groq-Powered, <0.5s' },
              { icon: ShieldCheck, label: 'ArmorIQ Protected' },
            ].map((chip, idx) => (
              <div 
                key={idx}
                className="flex items-center gap-1.5"
                style={{
                  background: 'rgba(255,255,255,0.05)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 100,
                  padding: '0.4rem 1rem',
                }}
              >
                <chip.icon size={13} style={{ color: '#DFFF00' }} />
                <span style={{ 
                  fontSize: 10, 
                  color: '#ccc', 
                  fontFamily: "'Outfit', sans-serif", 
                  fontWeight: 500, 
                  letterSpacing: '0.08em', 
                  textTransform: 'uppercase' 
                }}>
                  {chip.label}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* ── Input form ─────────────────────────────────────────────────── */}
        <form
          onSubmit={handleSubmit}
          className="glass glass-acid p-6 md:p-8 space-y-5"
        >
          {/* Form Header & Tabs */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-2">
            <label
              htmlFor="analyze-input"
              style={{ display: 'block', fontSize: 12, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#888' }}
            >
              Message / URL to Analyse
            </label>
            
            <div className="flex items-center gap-1" style={{ background: 'rgba(0,0,0,0.2)', padding: 4, borderRadius: 8, border: '1px solid rgba(255,255,255,0.05)' }}>
              <button
                type="button"
                onClick={() => setInputTab('text')}
                className="flex items-center gap-1.5"
                style={{
                  background: inputTab === 'text' ? 'rgba(255,255,255,0.1)' : 'transparent',
                  color: inputTab === 'text' ? '#fff' : '#666',
                  fontSize: 11,
                  fontWeight: 500,
                  padding: '4px 10px',
                  borderRadius: 6,
                  transition: 'all 0.2s'
                }}
              >
                <FileText size={12} /> Text
              </button>
              <button
                type="button"
                onClick={() => setInputTab('screenshot')}
                className="flex items-center gap-1.5"
                style={{
                  background: inputTab === 'screenshot' ? 'rgba(255,255,255,0.1)' : 'transparent',
                  color: inputTab === 'screenshot' ? '#fff' : '#666',
                  fontSize: 11,
                  fontWeight: 500,
                  padding: '4px 10px',
                  borderRadius: 6,
                  transition: 'all 0.2s'
                }}
              >
                <ImageIcon size={12} /> Screenshot
              </button>
              <button
                type="button"
                onClick={() => setInputTab('url')}
                className="flex items-center gap-1.5"
                title="Coming in this build"
                style={{
                  background: inputTab === 'url' ? 'rgba(255,255,255,0.1)' : 'transparent',
                  color: inputTab === 'url' ? '#fff' : '#666',
                  fontSize: 11,
                  fontWeight: 500,
                  padding: '4px 10px',
                  borderRadius: 6,
                  transition: 'all 0.2s'
                }}
              >
                <LinkIcon size={12} /> URL only
              </button>
            </div>
          </div>

          {inputTab === 'text' && (
            <textarea
              id="analyze-input"
              rows={5}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Paste an SMS, email body, or suspicious link here…"
              style={{
                width: '100%',
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 10,
                padding: '0.875rem 1rem',
                color: '#fff',
                fontSize: 14,
                fontFamily: "'Outfit', sans-serif",
                lineHeight: 1.6,
                resize: 'none',
                outline: 'none',
                transition: 'border-color 0.2s',
              }}
              onFocus={e => (e.currentTarget.style.borderColor = 'rgba(223,255,0,0.35)')}
              onBlur={e => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)')}
            />
          )}

          {inputTab === 'screenshot' && (
            <div 
              className={`relative flex flex-col items-center justify-center border-2 border-dashed rounded-xl p-6 text-center transition-colors h-48 overflow-hidden ${
                isDragging ? 'border-[#DFFF00] bg-[#DFFF00]/5' : 'border-white/10 bg-white/5'
              } ${!previewUrl ? 'cursor-pointer' : ''}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => !previewUrl && fileInputRef.current?.click()}
            >
              <input 
                type="file" 
                ref={fileInputRef} 
                className="hidden" 
                accept="image/png,image/jpeg,image/jpg,image/webp" 
                onChange={e => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
              />
              
              {imageMutation.isError ? (
                <div className="flex flex-col items-center gap-3 w-full">
                  <div className="text-red-400 font-bold text-sm text-center">
                    ⚠️ {extractErrorMessage(imageMutation.error)}
                  </div>
                  <button 
                    type="button" 
                    onClick={(e) => { e.stopPropagation(); clearFile(); }}
                    className="px-4 py-1.5 bg-white/10 hover:bg-white/20 rounded-md text-xs font-medium transition-colors text-white"
                  >
                    Try Again
                  </button>
                </div>
              ) : previewUrl ? (
                <div className="relative w-full h-full flex flex-col items-center justify-center">
                  {isLongScreenshot && (
                    <div className="absolute top-2 left-0 right-0 z-10 mx-auto w-max max-w-[90%] bg-yellow-500/20 border border-yellow-500/50 text-yellow-200 text-[10px] px-2 py-1 rounded-md backdrop-blur-md text-center">
                      ⚠️ This looks like a long scrolling screenshot — we'll automatically resize it for analysis.
                    </div>
                  )}
                  <img src={previewUrl} alt="Preview" className="max-h-full object-contain rounded" />
                  <button 
                    type="button" 
                    onClick={(e) => { e.stopPropagation(); clearFile(); }}
                    className="absolute top-2 right-2 bg-black/60 hover:bg-black text-white p-1.5 rounded transition-colors"
                    title="Remove"
                  >
                    <X size={14} />
                  </button>
                  {imageMutation.isPending && (
                    <div className="absolute inset-0 bg-black/60 backdrop-blur-sm flex flex-col items-center justify-center rounded gap-3">
                      <Loader2 size={24} className="animate-spin text-[#DFFF00]" />
                      <span className="text-[#DFFF00] text-sm font-medium">Reading text from image…</span>
                      <span className="text-white/40 text-xs text-center max-w-[220px]">
                        First scan may take up to 90s while OCR model loads
                      </span>
                    </div>
                  )}
                </div>
              ) : (
                <>
                  <ImageIcon size={28} className="text-white/20 mb-3" />
                  <p className="text-white/40 text-sm font-medium">Drag & Drop a screenshot or click to upload</p>
                  {fileError && <p className="text-red-400 text-xs mt-2 font-medium">{fileError}</p>}
                </>
              )}
            </div>
          )}

          {inputTab === 'url' && (
            <input
              type="url"
              placeholder="https://example.com"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              style={{
                width: '100%',
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 10,
                padding: '0.875rem 1rem',
                color: '#fff',
                fontSize: 14,
                fontFamily: "'Outfit', sans-serif",
                outline: 'none',
                transition: 'border-color 0.2s',
              }}
              onFocus={e => (e.currentTarget.style.borderColor = 'rgba(223,255,0,0.35)')}
              onBlur={e => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)')}
            />
          )}

          {/* Example chips */}
          <div className="flex flex-col gap-3 mb-2">
            <div className="flex flex-wrap gap-2 items-center">
              <span style={{ fontSize: 11, color: '#444', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Try:</span>
              {DEMO_INPUTS.map((ex, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => handleExample(ex.text)}
                  style={{
                    fontSize: 11,
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: 8,
                    padding: '0.3rem 0.75rem',
                    color: '#666',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    fontFamily: "'Outfit', sans-serif",
                  }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(223,255,0,0.3)'; e.currentTarget.style.color = '#DFFF00' }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)'; e.currentTarget.style.color = '#666' }}
                  title={ex.text}
                >
                  {ex.label}
                </button>
              ))}
            </div>

            {/* Stress Tests */}
            <div className="flex flex-wrap gap-2 items-center">
              <span style={{ fontSize: 11, color: '#F59E0B', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Stress Tests:</span>
              {[
                { label: "Axis OCR Noise", path: "/stress_axis.png" },
                { label: "Jio Hindi Ambiguous", path: "/stress_jio.png" },
                { label: "Messy Email Forward", path: "/stress_email.png" }
              ].map((ex, i) => (
                <button
                  key={`stress-${i}`}
                  type="button"
                  onClick={() => handleExampleImage(ex.path, ex.label)}
                  style={{
                    fontSize: 11,
                    background: 'rgba(245,158,11,0.05)',
                    border: '1px solid rgba(245,158,11,0.2)',
                    borderRadius: 8,
                    padding: '0.3rem 0.75rem',
                    color: '#F59E0B',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    fontFamily: "'Outfit', sans-serif",
                  }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(245,158,11,0.5)'; e.currentTarget.style.color = '#FCD34D' }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(245,158,11,0.2)'; e.currentTarget.style.color = '#F59E0B' }}
                  title={ex.text}
                >
                  {ex.label}
                </button>
              ))}
            </div>
          </div>

          {/* Submit */}
          <button
            id="analyze-submit"
            type="submit"
            disabled={isPending || (inputTab === 'text' && !message.trim()) || (inputTab === 'screenshot' && !selectedFile) || (inputTab === 'url' && !urlInput.trim())}
            title={inputTab === 'screenshot' && !selectedFile ? "Upload a screenshot first" : ""}
            className="btn-acid flex items-center gap-2"
            style={{ fontSize: 12, opacity: (isPending || (inputTab === 'text' && !message.trim()) || (inputTab === 'screenshot' && !selectedFile) || (inputTab === 'url' && !urlInput.trim())) ? 0.5 : 1, cursor: (isPending || (inputTab === 'text' && !message.trim()) || (inputTab === 'screenshot' && !selectedFile) || (inputTab === 'url' && !urlInput.trim())) ? 'not-allowed' : 'pointer' }}
          >
            {isPending ? (
              <><Loader2 size={16} className="animate-spin" /> Analysing…</>
            ) : (
              <><Zap size={16} /> Analyse Now</>
            )}
          </button>
        </form>

        {/* ── Feature Showcase (Pre-Analysis) ─────────────────────────────── */}
        {!result && (
          <FeatureShowcase />
        )}

        {/* ── Error ──────────────────────────────────────────────────────── */}
        {isError && (
          <div
            className="flex items-start gap-3"
            style={{
              background: 'rgba(239,68,68,0.08)',
              border: '1px solid rgba(239,68,68,0.25)',
              borderRadius: 12,
              padding: '1rem 1.25rem',
            }}
          >
            <AlertCircle size={18} style={{ color: '#EF4444', flexShrink: 0, marginTop: 2 }} />
            <div>
              <p style={{ color: '#EF4444', fontSize: 14, fontWeight: 600 }}>Analysis failed</p>
              <p style={{ color: 'rgba(239,68,68,0.7)', fontSize: 12, marginTop: 2 }}>{errorMessage}</p>
            </div>
          </div>
        )}

        {/* ── Results ────────────────────────────────────────────────────── */}
        {result && (
          <div className="space-y-6 animate-fade-in">
            {/* OCR Extracted Text */}
            {result.extracted_text && (
              <div className="glass p-6 mb-5 space-y-3">
                <div className="flex items-center gap-2">
                  <h3 style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#888' }}>
                    📄 Extracted Text
                  </h3>
                  {result.ocr_confidence != null && (
                    <span className="px-2 py-0.5 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-[10px] font-bold">
                      {Math.round(result.ocr_confidence * 100)}% confidence
                    </span>
                  )}
                </div>
                <div className="p-4 bg-black/40 rounded-lg border border-white/5 font-mono text-xs text-slate-300 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
                  {result.extracted_text}
                </div>
              </div>
            )}

            {/* Top row — Gauge + Stats */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">

              {/* Gauge card */}
              <div
                className="glass flex flex-col items-center justify-center gap-5 p-8 h-full"
                style={{ borderColor: `${vColor}30`, boxShadow: `0 8px 32px ${vColor}15` }}
              >
                <RiskGauge score={result.risk_score} verdict={result.verdict} size={220} />
                <div className="flex flex-col items-center gap-2">
                  <VerdictBadge verdict={result.verdict} size="lg" />
                  <div className="flex items-start gap-1.5 text-sm mt-1 max-w-[280px] text-center font-medium" style={{ color: vColor }}>
                    {result.verdict === 'SAFE'
                      ? <ShieldCheck size={15} className="mt-0.5 shrink-0" />
                      : <AlertTriangle size={15} className="mt-0.5 shrink-0" />}
                    <span>{result.verdict === 'SAFE' ? 'Status: ' : 'Detected: '}{topReason}</span>
                  </div>
                  {result.certainty !== 'high' && (
                    <div className="mt-2 p-3 rounded-md flex items-start gap-2 max-w-[300px] text-left" style={{ background: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.2)' }}>
                      <AlertCircle size={14} className="mt-0.5 shrink-0" style={{ color: '#60A5FA' }} />
                      <span style={{ fontSize: 11, color: '#93C5FD', lineHeight: 1.4, fontFamily: "'Outfit', sans-serif" }}>
                        {result.certainty === 'low' 
                          ? "This message has unusual characteristics our system hasn't seen much of. Use your own judgment alongside this result."
                          : "Moderate confidence — consider the explanation below carefully."}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Stats card */}
              <div className="glass p-6 flex flex-col justify-between gap-5 h-full">
                <div>
                  <h2 style={{ fontFamily: "'Syncopate', sans-serif", fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#DFFF00', marginBottom: '0.4rem' }}>
                    Analysis Summary
                  </h2>
                  <p style={{ color: '#444', fontSize: 12 }}>
                    {new Date(result.analyzed_at).toLocaleString('en-IN')}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <StatCard label="Risk Score"  value={`${result.risk_score}/100`}                  accent={vColor} />
                  <StatCard label="Confidence"  value={`${(result.confidence * 100).toFixed(0)}%`}  accent="#DFFF00" />
                  <StatCard label="Processing Time" value={`${result.processing_ms}ms`} />
                  <div 
                    onClick={() => document.getElementById('shap-section')?.scrollIntoView({behavior:'smooth'})}
                    className="cursor-pointer transition-transform hover:scale-[1.02]"
                  >
                    <StatCard label="Risk Indicators" value={String(result.shap_features.length)} />
                  </div>
                </div>

                {/* Copy button */}
                <button
                  id="copy-results-btn"
                  type="button"
                  onClick={handleCopy}
                  className="flex items-center gap-2 self-start"
                  style={{
                    fontSize: 12,
                    color: '#555',
                    border: '1px solid rgba(255,255,255,0.08)',
                    background: 'none',
                    borderRadius: 8,
                    padding: '0.4rem 0.9rem',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    fontFamily: "'Outfit', sans-serif",
                  }}
                  onMouseEnter={e => { e.currentTarget.style.color = '#DFFF00'; e.currentTarget.style.borderColor = 'rgba(223,255,0,0.3)' }}
                  onMouseLeave={e => { e.currentTarget.style.color = '#555'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)' }}
                >
                  {copied ? <><CheckCheck size={13} style={{ color: '#22C55E' }} /> Copied!</> : <><Copy size={13} /> Copy Report</>}
                </button>
              </div>
            </div>

            {/* ── QR and UPI Results Placeholder ───────────────────────────── */}
            {(result.qr_detected || result.upi_details?.upi_found) && (
              <div className="space-y-4 animate-fade-in glass p-6">
                <QRDetectedBadge qrDetected={result.qr_detected} qrCodes={result.qr_codes_found} />
                <UPIWarningCard upiDetails={result.upi_details} />
              </div>
            )}

            {/* URL Reputation — multi-source breakdown */}
            <URLReputationPanel urlAnalysis={result.url_analysis} />

            {/* SHAP chart */}
            {result.shap_features.length > 0 && (
              <div id="shap-section" className="glass p-6">
                <SHAPChart 
                  features={result.shap_features} 
                  maxItems={6} 
                  isSafeVerdict={result.risk_score < 40}
                />
              </div>
            )}

            {/* Detection Layers */}
            <div className="glass p-6 flex flex-col gap-4">
              <h3 style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#888' }}>
                Detection Layers
              </h3>
              <div className="flex flex-wrap gap-3">
                {[
                  { label: 'NLP Engine', obj: result.component_scores.nlp, notAppReason: 'Not applicable (no text found)' },
                  { label: 'URL Engine', obj: result.component_scores.url, notAppReason: 'Not applicable (no link found)' },
                  { label: 'Behavioral', obj: result.component_scores.behavioral, notAppReason: 'Not applicable' },
                  { label: 'OCR', obj: result.component_scores.ocr, notAppReason: 'Not applicable (not an image upload)' },
                ].map((layer, idx) => {
                  if (!layer.obj || layer.obj.score === null || layer.obj.score === undefined) {
                    return (
                      <div key={idx} className="flex flex-col justify-center border rounded-lg px-4 py-3" style={{ borderColor: 'rgba(255,255,255,0.05)', background: 'rgba(255,255,255,0.02)', minWidth: 200, opacity: 0.5 }}>
                        <div className="flex justify-between items-center w-full">
                          <span style={{ fontSize: 11, fontWeight: 600, color: '#666', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{layer.label}</span>
                        </div>
                        <span style={{ fontSize: 11, color: '#666', marginTop: 4 }}>— {layer.notAppReason}</span>
                      </div>
                    )
                  }

                  const score = layer.obj.score
                  const weightPct = Math.round(layer.obj.weight * 100)
                  const contrib = layer.obj.contribution

                  let badgeColor = '#555'
                  let bgCol = 'rgba(255,255,255,0.02)'
                  if (score > 70) {
                    badgeColor = '#EF4444' // red
                    bgCol = 'rgba(239,68,68,0.08)'
                  } else if (score >= 40) {
                    badgeColor = '#F59E0B' // amber
                    bgCol = 'rgba(245,158,11,0.08)'
                  } else {
                    badgeColor = '#22C55E' // green
                    bgCol = 'rgba(34,197,94,0.08)'
                  }
                  
                  return (
                    <div key={idx} className="flex flex-col justify-center border rounded-lg px-4 py-3" style={{ borderColor: badgeColor !== '#555' ? badgeColor + '30' : 'rgba(255,255,255,0.05)', background: bgCol, minWidth: 200 }}>
                      <div className="flex justify-between items-center w-full gap-4">
                        <span style={{ fontSize: 11, fontWeight: 600, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{layer.label}</span>
                        <span style={{ fontSize: 14, fontWeight: 800, color: badgeColor }}>{score}%</span>
                      </div>
                      <div style={{ fontSize: 11, color: '#888', marginTop: 6, fontWeight: 500 }}>
                        Weight: {weightPct}% <span style={{ color: '#555', margin: '0 4px' }}>→</span> <span style={{ color: badgeColor }}>+{contrib} pts</span>
                      </div>
                    </div>
                  )
                })}
              </div>
              <p style={{ fontSize: 11, color: '#666', marginTop: 4 }}>
                Final score = sum of weighted contributions across active layers
              </p>
            </div>

            {/* Explanation */}
            <ExplanationCard
              explanation={result.explanation}
              isLoading={false}
              model={result.model_version}
            />

            {/* Feedback widget — below-the-fold, non-intrusive */}
            <FeedbackWidget
              scanId={result.scan_id}
              verdict={result.verdict}
            />
          </div>
        )}
      </main>
    </div>
  )
}

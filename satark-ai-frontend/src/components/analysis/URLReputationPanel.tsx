/**
 * URLReputationPanel — shows multi-source reputation results for a URL.
 *
 * Placed between Detection Layers and SHAP chart in AnalyzePage.
 * Returns null when no URL was analysed (url_analysis is null).
 */

import { ShieldAlert, ShieldCheck, Globe, Clock, AlertTriangle, Info } from 'lucide-react'
import type { ScanResponse } from '../../api/analyze'

type UrlAnalysis = NonNullable<ScanResponse['url_analysis']>

interface Props {
  urlAnalysis: UrlAnalysis | null
}

const SOURCE_LABELS: Record<string, string> = {
  phishtank:            'PhishTank',
  google_safe_browsing: 'Google Safe Browsing',
  virustotal:           'VirusTotal',
  domain_age_heuristic: 'Domain Age',
}

function verdictColor(v: string) {
  if (v === 'malicious')  return { text: '#EF4444', bg: 'rgba(239,68,68,0.10)',  border: 'rgba(239,68,68,0.25)'  }
  if (v === 'suspicious') return { text: '#F59E0B', bg: 'rgba(245,158,11,0.10)', border: 'rgba(245,158,11,0.25)' }
  if (v === 'clean')      return { text: '#22C55E', bg: 'rgba(34,197,94,0.10)',  border: 'rgba(34,197,94,0.25)'  }
  return                         { text: '#6B7280', bg: 'rgba(107,114,128,0.08)', border: 'rgba(107,114,128,0.2)' }
}

function verdictIcon(v: string, size = 13) {
  if (v === 'malicious' || v === 'suspicious') return <ShieldAlert size={size} />
  if (v === 'clean') return <ShieldCheck size={size} />
  return <Info size={size} />
}

function verdictLabel(v: string) {
  return v.charAt(0).toUpperCase() + v.slice(1)
}

function isApiKeyError(raw: Record<string, unknown>): boolean {
  return typeof raw['error'] === 'string' && String(raw['error']).includes('not configured')
}

export default function URLReputationPanel({ urlAnalysis }: Props) {
  if (!urlAnalysis) return null

  const {
    final_url,
    reputation_verdict,
    sources_agreeing,
    insufficient_reputation_data,
    source_results,
    domain_age_days,
    hop_count,
    typosquatted_brand,
    is_suspicious_tld,
    whois_info,
  } = urlAnalysis

  const totalSources = source_results.length
  const flaggingColor =
    sources_agreeing >= 2 ? '#EF4444' :
    sources_agreeing === 1 ? '#F59E0B' :
    '#22C55E'

  const displayDomain = (() => {
    try { return new URL(final_url).hostname } catch { return final_url }
  })()

  return (
    <div
      className="glass p-6 flex flex-col gap-4"
      id="url-reputation-panel"
    >
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Globe size={14} style={{ color: '#DFFF00' }} />
          <h3 style={{
            fontSize: 11, fontWeight: 700, textTransform: 'uppercase',
            letterSpacing: '0.1em', color: '#888',
          }}>
            URL Reputation
          </h3>
        </div>
        <span
          className="text-xs font-mono px-2 py-0.5 rounded"
          style={{ background: 'rgba(255,255,255,0.04)', color: '#555', maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
          title={final_url}
        >
          {displayDomain}
        </span>
      </div>

      {/* Insufficient data amber banner */}
      {insufficient_reputation_data && (
        <div
          className="flex items-start gap-2 rounded-lg px-3 py-2.5"
          style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)' }}
        >
          <AlertTriangle size={14} className="mt-0.5 shrink-0" style={{ color: '#F59E0B' }} />
          <div>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#F59E0B' }}>Unverified Domain</p>
            <p style={{ fontSize: 11, color: '#D97706', lineHeight: 1.5, marginTop: 2 }}>
              This domain isn't yet listed in any threat database — could mean it's brand new
              (a common phishing tactic) or simply obscure. Treating with elevated caution.
            </p>
          </div>
        </div>
      )}

      {/* Summary line */}
      <div className="flex items-center gap-2 flex-wrap">
        <span style={{ fontSize: 13, fontWeight: 700, color: flaggingColor }}>
          {sources_agreeing} of {totalSources} sources flagged this domain
        </span>
        <span
          className="px-2 py-0.5 rounded-full text-xs font-semibold"
          style={{
            background: verdictColor(reputation_verdict).bg,
            border: `1px solid ${verdictColor(reputation_verdict).border}`,
            color: verdictColor(reputation_verdict).text,
          }}
        >
          {verdictLabel(reputation_verdict)}
        </span>
        {hop_count > 0 && (
          <span className="text-xs" style={{ color: '#F59E0B' }}>
            ↪ {hop_count} redirect{hop_count > 1 ? 's' : ''}
          </span>
        )}
        {typosquatted_brand && (
          <span
            className="px-2 py-0.5 rounded-full text-xs font-semibold"
            style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: '#EF4444' }}
          >
            Impersonates {typosquatted_brand}
          </span>
        )}
        {is_suspicious_tld && (
          <span
            className="px-2 py-0.5 rounded-full text-xs font-semibold"
            style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: '#EF4444' }}
          >
            Suspicious TLD
          </span>
        )}
      </div>

      {/* Per-source chips */}
      <div className="flex flex-wrap gap-2">
        {source_results.map((src) => {
          const c = verdictColor(src.verdict)
          const apiMissing = isApiKeyError(src.raw)
          return (
            <div
              key={src.source}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg"
              style={{
                background: apiMissing ? 'rgba(255,255,255,0.03)' : c.bg,
                border: `1px solid ${apiMissing ? 'rgba(255,255,255,0.08)' : c.border}`,
                opacity: apiMissing ? 0.55 : 1,
              }}
              title={apiMissing ? 'API key not configured' : `Confidence: ${Math.round(src.confidence * 100)}%`}
            >
              <span style={{ color: apiMissing ? '#555' : c.text }}>
                {verdictIcon(src.verdict)}
              </span>
              <span style={{ fontSize: 11, fontWeight: 600, color: apiMissing ? '#555' : c.text }}>
                {SOURCE_LABELS[src.source] ?? src.source}
              </span>
              {apiMissing && (
                <span style={{ fontSize: 10, color: '#444' }}>— no key</span>
              )}
              {!apiMissing && src.verdict !== 'unknown' && (
                <span style={{ fontSize: 10, color: '#555' }}>
                  {verdictLabel(src.verdict)} ({Math.round(src.confidence * 100)}%)
                </span>
              )}
            </div>
          )
        })}
      </div>

      {/* Domain age + WHOIS row */}
      {(domain_age_days !== null || whois_info?.registrar) && (
        <div className="flex flex-wrap gap-4 pt-1" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
          {domain_age_days !== null && (
            <div className="flex items-center gap-1.5">
              <Clock size={12} style={{ color: '#555' }} />
              <span style={{ fontSize: 11, color: '#666' }}>
                Domain age:{' '}
                <span style={{ color: domain_age_days < 90 ? '#F59E0B' : '#888', fontWeight: 600 }}>
                  {domain_age_days < 1 ? '<1 day' : domain_age_days < 365 ? `${domain_age_days}d` : `${Math.round(domain_age_days / 365)}y ${Math.round((domain_age_days % 365) / 30)}m`}
                </span>
                {domain_age_days < 90 && <span style={{ color: '#F59E0B' }}> ⚠ very new</span>}
              </span>
            </div>
          )}
          {whois_info?.registrar && (
            <div className="flex items-center gap-1.5">
              <Globe size={12} style={{ color: '#555' }} />
              <span style={{ fontSize: 11, color: '#666' }}>
                {whois_info.registrar}
                {whois_info.country ? ` · ${whois_info.country}` : ''}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Missing API key hint */}
      {source_results.some(s => isApiKeyError(s.raw)) && (
        <p style={{ fontSize: 10, color: '#444', marginTop: -8 }}>
          💡 Add <code style={{ color: '#666' }}>GOOGLE_SAFE_BROWSING_API_KEY</code> and <code style={{ color: '#666' }}>VIRUSTOTAL_API_KEY</code> to .env for full multi-source coverage.
        </p>
      )}
    </div>
  )
}

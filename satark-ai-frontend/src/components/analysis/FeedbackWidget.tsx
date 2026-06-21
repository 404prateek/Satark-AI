/**
 * FeedbackWidget — sits below the AI Explanation card.
 *
 * Non-intrusive: two small ghost buttons.
 * On "wrong" → expands an inline correction form.
 * On submit   → collapses back to a thank-you state.
 *
 * Design follows the existing acid-yellow (#DFFF00) token system.
 */

import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { CheckCheck, ThumbsDown, ThumbsUp, Loader2, X } from 'lucide-react'
import { submitFeedback, CorrectionType } from '../../api/feedback'

interface FeedbackWidgetProps {
  scanId: string
  verdict: 'SAFE' | 'SUSPICIOUS' | 'PHISHING'
}

export default function FeedbackWidget({ scanId, verdict }: FeedbackWidgetProps) {
  const [phase, setPhase] = useState<'idle' | 'wrong-form' | 'done'>('idle')
  const [selectedLabel, setSelectedLabel] = useState<'safe' | 'scam'>(
    verdict === 'SAFE' ? 'scam' : 'safe',
  )
  const [notes, setNotes] = useState('')

  const mutation = useMutation({
    mutationFn: ({ correction, notes }: { correction: CorrectionType; notes?: string }) =>
      submitFeedback(scanId, { correction, notes }),
    onSuccess: () => setPhase('done'),
  })

  // ── Done state ──────────────────────────────────────────────────────────────
  if (phase === 'done') {
    return (
      <div
        className="flex items-center gap-2 py-2 px-3 rounded-xl"
        style={{
          background: 'rgba(223,255,0,0.06)',
          border: '1px solid rgba(223,255,0,0.18)',
        }}
      >
        <CheckCheck size={14} style={{ color: '#DFFF00', flexShrink: 0 }} />
        <span style={{ fontSize: 12, color: '#DFFF00', fontFamily: "'Outfit', sans-serif" }}>
          Thanks — this helps us catch scams like this faster.
        </span>
      </div>
    )
  }

  // ── Correction form ─────────────────────────────────────────────────────────
  if (phase === 'wrong-form') {
    const oppositeIsScam = verdict === 'SAFE'  // if safe, the correction is "this is a scam"

    return (
      <div
        className="rounded-xl overflow-hidden"
        style={{
          background: 'rgba(255,255,255,0.03)',
          border: '1px solid rgba(255,255,255,0.08)',
        }}
      >
        {/* Form header */}
        <div
          className="flex items-center justify-between px-4 py-3"
          style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}
        >
          <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#888' }}>
            What should it be?
          </span>
          <button
            type="button"
            onClick={() => setPhase('idle')}
            style={{ color: '#555', background: 'none', padding: 0, cursor: 'pointer' }}
            aria-label="Cancel"
          >
            <X size={14} />
          </button>
        </div>

        <div className="px-4 py-4 space-y-4">
          {/* Toggle */}
          <div className="flex gap-2">
            {(['safe', 'scam'] as const).map((opt) => {
              const active = selectedLabel === opt
              const label = opt === 'safe' ? '✓ This is actually safe' : '⚠ This is actually a scam'
              return (
                <button
                  key={opt}
                  type="button"
                  onClick={() => setSelectedLabel(opt)}
                  style={{
                    flex: 1,
                    fontSize: 11,
                    fontWeight: 600,
                    fontFamily: "'Outfit', sans-serif",
                    padding: '0.5rem 0.75rem',
                    borderRadius: 8,
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                    background: active
                      ? opt === 'safe'
                        ? 'rgba(34,197,94,0.15)'
                        : 'rgba(239,68,68,0.15)'
                      : 'rgba(255,255,255,0.04)',
                    border: active
                      ? `1px solid ${opt === 'safe' ? 'rgba(34,197,94,0.5)' : 'rgba(239,68,68,0.5)'}`
                      : '1px solid rgba(255,255,255,0.08)',
                    color: active
                      ? opt === 'safe' ? '#22C55E' : '#EF4444'
                      : '#555',
                  }}
                >
                  {label}
                </button>
              )
            })}
          </div>

          {/* Optional notes */}
          <textarea
            rows={2}
            placeholder="Optional: any context? (e.g. 'This is my bank's real SMS')"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            maxLength={500}
            style={{
              width: '100%',
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 8,
              padding: '0.5rem 0.75rem',
              color: '#ccc',
              fontSize: 12,
              fontFamily: "'Outfit', sans-serif",
              resize: 'none',
              outline: 'none',
            }}
            onFocus={(e) => (e.currentTarget.style.borderColor = 'rgba(223,255,0,0.25)')}
            onBlur={(e) => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)')}
          />

          {/* Submit */}
          <button
            type="button"
            disabled={mutation.isPending}
            onClick={() => {
              // Derive correction type from (verdict, selectedLabel)
              let correction: CorrectionType
              if (verdict === 'SAFE' && selectedLabel === 'scam') {
                correction = 'false_negative'
              } else if (verdict !== 'SAFE' && selectedLabel === 'safe') {
                correction = 'false_positive'
              } else {
                // Edge case: user opened the form but kept the same label — treat as correct
                correction = 'correct'
              }
              mutation.mutate({ correction, notes: notes.trim() || undefined })
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 11,
              fontWeight: 700,
              fontFamily: "'Outfit', sans-serif",
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
              padding: '0.5rem 1.25rem',
              borderRadius: 8,
              cursor: mutation.isPending ? 'not-allowed' : 'pointer',
              background: mutation.isPending ? 'rgba(223,255,0,0.3)' : '#DFFF00',
              color: '#000',
              border: 'none',
              transition: 'opacity 0.15s',
              opacity: mutation.isPending ? 0.7 : 1,
            }}
          >
            {mutation.isPending ? (
              <><Loader2 size={12} className="animate-spin" /> Submitting…</>
            ) : (
              'Submit Correction'
            )}
          </button>

          {mutation.isError && (
            <p style={{ fontSize: 11, color: '#EF4444', marginTop: 4 }}>
              Couldn't submit. Please try again.
            </p>
          )}
        </div>
      </div>
    )
  }

  // ── Idle state (default) ────────────────────────────────────────────────────
  return (
    <div className="flex items-center gap-3 pt-1">
      <span style={{ fontSize: 11, color: '#444', fontFamily: "'Outfit', sans-serif" }}>
        Was this accurate?
      </span>

      {/* ✓ Correct */}
      <button
        type="button"
        onClick={() => mutation.mutate({ correction: 'correct' })}
        disabled={mutation.isPending}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 5,
          fontSize: 11,
          fontFamily: "'Outfit', sans-serif",
          background: 'none',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: 6,
          padding: '0.3rem 0.75rem',
          color: '#555',
          cursor: 'pointer',
          transition: 'all 0.15s',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = 'rgba(34,197,94,0.4)'
          e.currentTarget.style.color = '#22C55E'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)'
          e.currentTarget.style.color = '#555'
        }}
        aria-label="This result looks correct"
      >
        <ThumbsUp size={11} />
        This looks right
      </button>

      {/* ✗ Wrong */}
      <button
        type="button"
        onClick={() => setPhase('wrong-form')}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 5,
          fontSize: 11,
          fontFamily: "'Outfit', sans-serif",
          background: 'none',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: 6,
          padding: '0.3rem 0.75rem',
          color: '#555',
          cursor: 'pointer',
          transition: 'all 0.15s',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = 'rgba(239,68,68,0.4)'
          e.currentTarget.style.color = '#EF4444'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)'
          e.currentTarget.style.color = '#555'
        }}
        aria-label="This result is wrong"
      >
        <ThumbsDown size={11} />
        This is wrong
      </button>
    </div>
  )
}

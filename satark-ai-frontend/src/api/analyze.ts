import apiClient, { imageApiClient } from './client'

export interface ScanResponse {
  scan_id: string
  verdict: 'SAFE' | 'SUSPICIOUS' | 'PHISHING'
  risk_score: number
  certainty: 'high' | 'medium' | 'low'
  confidence: number
  language: string
  component_scores: {
    nlp: { score: number; weight: number; contribution: number }
    behavioral: { score: number; weight: number; contribution: number }
    url: { score: number | null; weight: number; contribution: number | null } | null
    ocr: { score: number | null; weight: number; contribution: number | null } | null
  }
  shap_features: Array<{ feature: string; value: number }>
  behavioral_triggers: string[]
  explanation: string
  url_found: string | null
  url_analysis: {
    url: string
    final_url: string
    score: number
    is_phishtank_hit: boolean
    typosquatted_brand: string | null
    is_suspicious_tld: boolean
    domain_age_days: number | null
    whois_info: { registrar?: string; country?: string; created?: string; updated?: string }
    redirect_chain: string[]
    hop_count: number
    reputation_score: number
    reputation_verdict: 'malicious' | 'suspicious' | 'clean' | 'unknown'
    reputation_sources: string[]
    sources_agreeing: number
    insufficient_reputation_data: boolean
    source_results: Array<{
      source: string
      verdict: 'malicious' | 'suspicious' | 'clean' | 'unknown'
      confidence: number
      raw: Record<string, unknown>
    }>
  } | null
  extracted_text: string | null
  ocr_confidence: number | null
  model_version: string
  analyzed_at: string
  processing_ms: number
  actions: Array<{ label: string; url?: string; type: string }>
  qr_detected?: boolean
  qr_codes_found?: Array<{ data: string; qr_type: string }>
  upi_details?: {
    upi_found: boolean
    vpa: string
    amount: number | null
    mismatch: {
      mismatch_detected: boolean
      explanation: string
    }
  } | null
}

export const analyzeMessage = async (text: string): Promise<ScanResponse> => {
  const res = await apiClient.post('/analyze/message', { message: text })
  return res.data
}

export const analyzeImage = async (file: File): Promise<ScanResponse> => {
  const form = new FormData()
  form.append('file', file)
  // Use imageApiClient (180 s timeout) — EasyOCR on CPU can take ~45-90 s on first load.
  const res = await imageApiClient.post('/analyze/image', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export const analyzeURL = async (url: string): Promise<ScanResponse> => {
  const res = await apiClient.post('/analyze/url', { url })
  return res.data
}

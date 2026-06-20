import apiClient from './client'

export interface ScanResponse {
  scan_id: string
  verdict: 'SAFE' | 'SUSPICIOUS' | 'PHISHING'
  risk_score: number
  confidence: number
  language: string
  component_scores: {
    nlp: { score: number; weight: number; contribution: number }
    url: { score: number | null; weight: number; contribution: number }
    behavioral: { score: number; weight: number; contribution: number }
    ocr: { score: number | null; weight: number; contribution: number }
  }
  shap_features: Array<{ feature: string; value: number }>
  behavioral_triggers: string[]
  explanation: string
  url_found: string | null
  url_analysis: any | null
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
  extracted_text?: string
  ocr_confidence?: number
}

export const analyzeMessage = async (text: string): Promise<ScanResponse> => {
  const res = await apiClient.post('/analyze/message', { message: text })
  return res.data
}

export const analyzeImage = async (file: File): Promise<ScanResponse> => {
  const form = new FormData()
  form.append('file', file)
  const res = await apiClient.post('/analyze/image', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export const analyzeURL = async (url: string): Promise<ScanResponse> => {
  const res = await apiClient.post('/analyze/url', { url })
  return res.data
}

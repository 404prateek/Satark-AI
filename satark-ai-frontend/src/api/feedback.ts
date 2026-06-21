import apiClient from './client'

export type CorrectionType = 'correct' | 'false_positive' | 'false_negative'

export interface FeedbackRequest {
  correction: CorrectionType
  notes?: string
}

export interface FeedbackResponse {
  status: string
  thank_you: boolean
  feedback_id: string
}

export const submitFeedback = async (
  scanId: string,
  body: FeedbackRequest,
): Promise<FeedbackResponse> => {
  const res = await apiClient.post(`/feedback/${scanId}`, body)
  return res.data
}

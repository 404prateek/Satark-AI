import axios from 'axios'

export function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status;
    const detail = error.response?.data?.detail;
    
    if (status === 422) {
      return detail || "We couldn't find any readable content in that input.";
    }
    if (status === 504) {
      return detail || "That took too long to process. Please try again.";
    }
    if (status === 500) {
      return "Something went wrong on our end. Please try again in a moment.";
    }
    if (status === 401) {
      return "Your session expired. Please log in again.";
    }
    if (!error.response) {
      // Axios timeout (ECONNABORTED) — OCR on CPU can take 45-90 s on first load
      if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        return "Image analysis is taking longer than expected (OCR is warming up). Please try again — it will be faster now.";
      }
      return "Can't reach the server. Check that the backend is running.";
    }
    return detail || "Analysis failed. Please try again.";
  }
  return "Something unexpected happened. Please try again.";
}


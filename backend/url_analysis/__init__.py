"""url_analysis package — URL phishing detection engine for Satark AI."""

from backend.url_analysis.url_analyzer import URLAnalyzer, URLAnalysisResult
from backend.url_analysis.tld_checker import INDIAN_BRANDS

__all__ = ["URLAnalyzer", "URLAnalysisResult", "INDIAN_BRANDS"]

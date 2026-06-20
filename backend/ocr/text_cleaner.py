import unicodedata
import re

def clean_text(raw_text: str) -> str:
    """
    Cleans and normalizes raw OCR text.
    Handles Unicode normalization (especially important for Devanagari),
    and strips excess whitespace.
    """
    if not raw_text:
        return ""

    # Normalize unicode to NFKC (Normal Form KC)
    # This combines decomposed characters into single characters
    # e.g., for Hindi/Devanagari: 'क' + '्' + 'ष' -> 'क्ष' if applicable,
    # and fixes spacing issues.
    normalized = unicodedata.normalize('NFKC', raw_text)

    # Remove non-printable characters except spaces and newlines
    # (keeps basic punctuation, alphanumeric, and valid unicode chars)
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch)[0] != 'C' or ch in '\n\t')

    # Replace multiple spaces with a single space
    cleaned = re.sub(r'[ \t]+', ' ', normalized)
    
    # Replace multiple newlines with a single newline
    cleaned = re.sub(r'\n+', '\n', cleaned)

    return cleaned.strip()

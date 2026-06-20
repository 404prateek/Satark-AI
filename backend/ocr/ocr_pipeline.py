import io
import numpy as np
from PIL import Image
import easyocr
import logging

from backend.ocr.text_cleaner import clean_text

logger = logging.getLogger(__name__)

class OCRPipeline:
    def __init__(self, languages=['en', 'hi']):
        """
        Initializes the EasyOCR reader with the specified languages.
        This model download and loading into memory takes a few seconds.
        """
        logger.info(f"Initializing EasyOCR with languages: {languages}")
        # gpu=True will automatically use CUDA if available, else fallback to CPU
        self.reader = easyocr.Reader(languages, gpu=True)

    def extract_text(self, image_bytes: bytes) -> dict:
        """
        Takes raw image bytes, runs preprocessing, and performs OCR.
        Returns the extracted text, overall confidence, and word count.
        """
        try:
            # 1. Preprocess: Load image with Pillow, convert to RGB, then to NumPy array
            # EasyOCR expects a NumPy array or a file path
            img = Image.open(io.BytesIO(image_bytes))
            if img.mode != 'RGB':
                img = img.convert('RGB')
                
            img_array = np.array(img)

            # 2. Extract Text using EasyOCR
            # paragraph=True groups text into multi-line paragraphs automatically
            results = self.reader.readtext(img_array, paragraph=False)

            if not results:
                return {
                    "text": "",
                    "confidence": 0.0,
                    "word_count": 0
                }

            # 3. Post-process results
            raw_lines = []
            confidences = []
            
            for (bbox, text, prob) in results:
                raw_lines.append(text)
                confidences.append(prob)

            raw_combined_text = "\n".join(raw_lines)
            
            # Clean and normalize text (handles unicode and whitespace)
            final_text = clean_text(raw_combined_text)
            
            # Calculate metrics
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            word_count = len(final_text.split())

            return {
                "text": final_text,
                "confidence": round(avg_confidence, 4),
                "word_count": word_count
            }

        except Exception as e:
            logger.error(f"OCR Pipeline failed: {str(e)}")
            raise RuntimeError(f"Failed to process image through OCR: {str(e)}")

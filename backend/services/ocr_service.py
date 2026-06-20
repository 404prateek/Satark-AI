import asyncio
import logging
from typing import Optional

from backend.ocr.ocr_pipeline import OCRPipeline
from backend.ocr.image_validator import validate_image

logger = logging.getLogger(__name__)

# Global singleton instance, lazy-loaded on first request
_ocr_pipeline_instance: Optional[OCRPipeline] = None

def _get_ocr_pipeline() -> OCRPipeline:
    """
    Lazy-loads the OCR pipeline to prevent slow application startup times.
    Model weights are loaded into memory only when the first OCR request hits.
    """
    global _ocr_pipeline_instance
    if _ocr_pipeline_instance is None:
        _ocr_pipeline_instance = OCRPipeline(languages=['en', 'hi'])
    return _ocr_pipeline_instance

async def extract_from_image(image_bytes: bytes, filename: str = "upload") -> dict:
    """
    Validates an image and runs OCR extraction asynchronously.
    Offloads the CPU-heavy OCR task to a separate thread.
    """
    try:
        # 1. Validate image constraints (runs synchronously as it's fast)
        meta = validate_image(image_bytes, filename)
        logger.info(f"Image validated successfully: {meta}")

        # 2. Get the singleton pipeline
        pipeline = _get_ocr_pipeline()

        # 3. Offload the CPU-bound OCR process to a thread pool
        # This ensures the async FastAPI event loop is not blocked
        result = await asyncio.to_thread(pipeline.extract_text, image_bytes)
        
        return result

    except ValueError as ve:
        # Validation errors
        logger.warning(f"Image validation failed: {str(ve)}")
        raise
    except Exception as e:
        # OCR processing errors
        logger.error(f"Error extracting text from image: {str(e)}")
        raise

import asyncio
import logging
from typing import Optional

from backend.ocr.ocr_pipeline import OCRPipeline, resize_for_ocr, OCRTimeoutError, OCRProcessingError
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

def _run_pipeline(image_bytes: bytes) -> dict:
    pipeline = _get_ocr_pipeline()
    return pipeline.extract_text(image_bytes)

async def extract_from_image(image_bytes: bytes, filename: str = "upload") -> dict:
    """
    Validates an image, resizes if too large, and runs OCR extraction asynchronously with a timeout.
    """
    try:
        # 1. Validate image constraints (runs synchronously as it's fast)
        meta = validate_image(image_bytes, filename)
        logger.info(f"Image validated successfully: {meta}")

        # 2. Resize image if necessary
        resized_bytes = resize_for_ocr(image_bytes)

        # 3. Offload the CPU-bound OCR initialization and process to a thread pool with a timeout.
        # With MAX_DIMENSION=1024 this should complete in <30s on CPU even for dense images.
        # Timeout is 120s to match the uvicorn --timeout-keep-alive value.
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_run_pipeline, resized_bytes),
                timeout=120.0
            )
            return result
        except asyncio.TimeoutError:
            raise OCRTimeoutError("OCR processing took too long")
        except Exception as e:
            logger.error(f"OCR pipeline failed: {e}")
            raise OCRProcessingError(f"OCR failed: {str(e)}")

    except ValueError as ve:
        # Validation errors
        logger.warning(f"Image validation failed: {str(ve)}")
        raise

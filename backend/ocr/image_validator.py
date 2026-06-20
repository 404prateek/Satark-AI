import io
from PIL import Image

# We use Pillow as the primary validator for image type and dimensions.
# python-magic could be used, but Pillow natively verifies headers 
# and provides width/height out of the box securely.

ALLOWED_FORMATS = {'JPEG', 'PNG', 'WEBP'}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_DIMENSION = 4096

def validate_image(file_bytes: bytes, filename: str = "") -> dict:
    """
    Validates the uploaded image bytes for:
    - Max file size
    - Valid image format (JPEG, PNG, WEBP)
    - Max dimensions (Width x Height)
    
    Raises ValueError if validation fails.
    Returns a dict with image metadata on success.
    """
    file_size = len(file_bytes)
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"Image exceeds maximum allowed size of 5MB. Got: {file_size / (1024*1024):.2f}MB")

    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            # Pillow lazily loads the image header, which is safe and fast
            img_format = img.format
            
            if img_format not in ALLOWED_FORMATS:
                raise ValueError(f"Unsupported image format: {img_format}. Allowed: {', '.join(ALLOWED_FORMATS)}")
                
            width, height = img.size
            if width > MAX_DIMENSION or height > MAX_DIMENSION:
                raise ValueError(f"Image dimensions ({width}x{height}) exceed maximum allowed ({MAX_DIMENSION}x{MAX_DIMENSION})")

            # Verify image integrity
            img.verify()

            return {
                "format": img_format,
                "width": width,
                "height": height,
                "size_bytes": file_size,
                "filename": filename
            }
            
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Invalid or corrupted image file: {str(e)}")

import pytesseract
from PIL import Image
import io

def extract_text_from_image(file_bytes: bytes) -> str:
    """
    Extract text from an uploaded image using Tesseract OCR.
    """
    image = Image.open(io.BytesIO(file_bytes))
    text = pytesseract.image_to_string(image)
    return text.strip()

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from a PDF (requires pdf2image).
    """
    from pdf2image import convert_from_path
    pages = convert_from_path(pdf_path)
    text = ""
    for page in pages:
        text += pytesseract.image_to_string(page) + "\n"
    return text.strip()

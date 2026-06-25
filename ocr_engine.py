"""
core/ocr_engine.py
------------------
Handles all input types:
  - Plain text        → passed through directly
  - Digital PDFs      → PyMuPDF (no OCR needed, exact text extraction)
  - Scanned PDFs      → EasyOCR per page
  - Images (jpg/png)  → EasyOCR

No API calls. No internet at runtime.
"""

import io
from pathlib import Path
from typing import Union
import numpy as np

import fitz  # PyMuPDF
import easyocr
from PIL import Image


# EasyOCR reader is expensive to init — instantiate once and reuse
_ocr_reader = None


def _get_ocr_reader() -> easyocr.Reader:
    global _ocr_reader
    if _ocr_reader is None:
        # gpu=False ensures CPU-only — works on all student laptops
        _ocr_reader = easyocr.Reader(["en"], gpu=False)
    return _ocr_reader


def extract_text_from_image(image: Union[str, Path, np.ndarray, Image.Image]) -> str:
    """
    Extract text from an image file or numpy array using EasyOCR.
    """
    reader = _get_ocr_reader()

    if isinstance(image, Image.Image):
        image = np.array(image)

    results = reader.readtext(image, detail=0, paragraph=True)
    return "\n".join(results)


def extract_text_from_pdf(pdf_path: Union[str, Path]) -> str:
    """
    Extract text from a PDF.
    - If the PDF has embedded text (digital PDF): use PyMuPDF directly (fast, exact).
    - If pages have no embedded text (scanned PDF): fall back to EasyOCR per page.
    """
    pdf_path = Path(pdf_path)
    doc = fitz.open(str(pdf_path))
    pages_text = []

    for page_num, page in enumerate(doc):
        # Try embedded text extraction first
        text = page.get_text("text").strip()

        if len(text) > 50:
            # Digital PDF page — use extracted text directly
            pages_text.append(text)
        else:
            # Scanned page — render to image and run EasyOCR
            mat = fitz.Matrix(2.0, 2.0)  # 2x scale for better OCR accuracy
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)

            import cv2
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            ocr_text = extract_text_from_image(img)
            pages_text.append(f"[Page {page_num + 1}]\n{ocr_text}")

    doc.close()
    return "\n\n".join(pages_text)


def extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
    """
    Route file bytes to the right extractor based on file extension.
    Used by the Streamlit uploader.
    """
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        # Write to temp file for PyMuPDF (needs file path)
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            return extract_text_from_pdf(tmp_path)
        finally:
            os.unlink(tmp_path)

    elif ext in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}:
        img = Image.open(io.BytesIO(file_bytes))
        return extract_text_from_image(img)

    elif ext in {".txt", ".md", ".csv"}:
        return file_bytes.decode("utf-8", errors="replace")

    else:
        raise ValueError(f"Unsupported file type: {ext}")


def extract_text(source: Union[str, bytes, Path], filename: str = "") -> str:
    """
    Unified entry point. Accepts:
      - str  → treated as raw text, returned as-is
      - Path → routed to pdf/image extractor
      - bytes → routed via filename extension
    """
    if isinstance(source, str):
        return source  # already text

    if isinstance(source, Path):
        if source.suffix.lower() == ".pdf":
            return extract_text_from_pdf(source)
        else:
            return extract_text_from_image(source)

    if isinstance(source, bytes):
        return extract_text_from_bytes(source, filename)

    raise TypeError(f"Unsupported source type: {type(source)}")

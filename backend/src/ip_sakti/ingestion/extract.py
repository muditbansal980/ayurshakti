"""Page-preserving PDF extraction with optional local OCR, never cloud OCR."""

import re
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path

from pypdf import PdfReader


def ocr_page(path: Path, number: int) -> str:
    if not shutil.which("pdftoppm") or not shutil.which("tesseract"):
        raise ValueError("OCR needs pdftoppm and Tesseract (eng + hin). Use the backend Docker image.")
    with tempfile.TemporaryDirectory(prefix="sakti-ocr-") as directory:
        prefix = str(Path(directory) / "page")
        subprocess.run(["pdftoppm", "-f", str(number), "-l", str(number),
                        "-r", "200", "-singlefile", "-png", str(path), prefix],
                       check=True, capture_output=True, timeout=120)
        result = subprocess.run(["tesseract", prefix + ".png", "stdout", "-l", "eng+hin"],
                                check=True, capture_output=True, text=True, timeout=180)
        return result.stdout


def extract_pdf(path: Path, *, ocr: bool = False) -> list[dict]:
    reader = PdfReader(path)
    if reader.is_encrypted and not reader.decrypt(""):
        raise ValueError("Encrypted PDF requires an accessible original.")
    pages = []
    for number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        method = "pdf_text"
        # A blank cover is allowed. An image page with no usable text is not
        # silently dropped: that could remove a legally important exception.
        if len(text.strip()) < 40 and len(page.images):
            if not ocr:
                raise ValueError(f"PDF page {number} needs OCR review; rerun with --ocr.")
            text = ocr_page(path, number)
            method = "tesseract_eng_hin"
            if len(text.strip()) < 40:
                raise ValueError(f"OCR produced insufficient text on PDF page {number}; review manually.")
        text = unicodedata.normalize("NFC", text).replace("\x00", "")
        # Preserve punctuation, brackets, amendment notes and line breaks.
        lines = [re.sub(r"[\t ]+", " ", line).strip() for line in text.splitlines()]
        cleaned = []
        for line in lines:
            if line == "IndiaCode":
                continue
            if line.isdigit() and (not cleaned or line == str(number)):
                continue
            cleaned.append(line)
        pages.append({"page": number, "text": "\n".join(cleaned).strip(), "method": method})
    if sum(len(page["text"]) for page in pages) < 100:
        raise ValueError("No usable document text; OCR or a text-readable replacement is required.")
    return pages


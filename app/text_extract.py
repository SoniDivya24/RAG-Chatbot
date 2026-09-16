import io
from pathlib import Path

from pypdf import PdfReader


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from an uploaded file's bytes based on its extension.

    Supports .txt, .md (read as UTF-8) and .pdf (parsed page-by-page via pypdf).
    """
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        reader = PdfReader(io.BytesIO(file_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    if ext in (".txt", ".md"):
        return file_bytes.decode("utf-8")

    raise ValueError(
        f'Unsupported file type "{ext}". Please upload a .txt, .md, or .pdf file.'
    )

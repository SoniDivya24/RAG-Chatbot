import io
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from an uploaded file's bytes based on its extension.

    Supports .txt, .md (read as UTF-8) and .pdf (parsed page-by-page via pypdf).
    """
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        reader = PdfReader(io.BytesIO(file_bytes))
        if reader.is_encrypted:
            raise ValueError("Password-protected PDFs aren't supported yet.")
        try:
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except FileNotDecryptedError as exc:
            raise ValueError("Password-protected PDFs aren't supported yet.") from exc

    if ext in (".txt", ".md"):
        return file_bytes.decode("utf-8")

    raise ValueError(
        f'Unsupported file type "{ext}". Please upload a .txt, .md, or .pdf file.'
    )

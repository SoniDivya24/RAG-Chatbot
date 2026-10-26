import hashlib

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.profiles.base import Chunk, Profile
from app.text_extract import extract_text

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
RETRIEVAL_K = 5

# A vector search always returns the top-k closest chunks even when none of
# them are actually relevant (e.g. an off-topic question with documents
# uploaded); those shouldn't be sent to the LLM as context or shown to the user
# as "sources" for an answer they didn't actually inform.
MIN_RELEVANCE_SCORE = 0.62


class StandardProfile(Profile):
    """The original pipeline: plain text, fixed-size overlapping chunks."""

    id = "standard"
    label = "Standard"
    description = "General-purpose RAG over .txt, .md and .pdf files."

    retrieval_k = RETRIEVAL_K
    min_score = MIN_RELEVANCE_SCORE

    grounded_instructions = (
        "You are a helpful assistant answering questions about the uploaded "
        "documents. Use the CONTEXT below if it's relevant to the question. "
        "If the answer isn't in the context AND isn't something already "
        "established earlier in this conversation, say you don't have that "
        "information in the documents. Do not make up details. Answer "
        "directly - do not add meta-commentary about which documents are "
        "or aren't in scope, how many were provided, or reminders to upload "
        "more, unless the user explicitly asks what's available."
    )

    def __init__(self) -> None:
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
        )

    def extract(self, content: bytes, filename: str) -> str:
        return extract_text(content, filename)

    def chunk(self, extracted: str) -> list[Chunk]:
        texts = self.splitter.split_text(extracted)
        if not texts:
            raise ValueError("Document produced no usable text - is the file empty?")
        return [Chunk(text=t) for t in texts]

    def fingerprint(self, content: bytes, extracted: str) -> str:
        # By extracted text, not file bytes: the same words uploaded as .txt
        # and as .md (or re-exported as a PDF) count as the same document.
        return hashlib.sha256(extracted.encode("utf-8")).hexdigest()

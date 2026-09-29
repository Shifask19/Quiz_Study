"""
Document processing service.

Handles:
  - Text extraction from PDF, DOCX, PPTX, TXT, MD
  - Text cleaning and normalization
  - Chunking with overlap
  - Safe filename sanitization
  - Page-level metadata tracking
"""
import re
import unicodedata
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".md", ".markdown"}


@dataclass
class TextChunk:
    text: str
    chunk_index: int
    page: int = 0
    word_count: int = 0
    char_count: int = 0


@dataclass
class ExtractedDocument:
    filename: str
    file_type: str
    page_count: int
    full_text: str
    chunks: List[TextChunk] = field(default_factory=list)
    error: Optional[str] = None


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal and injection.
    Allows alphanumeric, dots, hyphens, underscores only.
    """
    # Remove path components
    name = Path(filename).name
    # Normalize unicode
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    # Allow only safe characters
    name = re.sub(r"[^\w.\-]", "_", name)
    # Collapse multiple underscores/dots
    name = re.sub(r"_{2,}", "_", name)
    name = re.sub(r"\.{2,}", ".", name)
    # Truncate
    stem = Path(name).stem[:100]
    suffix = Path(name).suffix
    return f"{stem}{suffix}"


def extract_text_from_pdf(file_path: Path) -> Tuple[str, int]:
    """Extract text from PDF using PyMuPDF. Returns (full_text, page_count)."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(file_path))
        pages_text = []
        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            if text.strip():
                pages_text.append(f"[Page {page_num + 1}]\n{text}")
        doc.close()
        return "\n\n".join(pages_text), len(doc)
    except ImportError:
        raise ImportError("PyMuPDF not installed. Run: pip install pymupdf")
    except Exception as e:
        raise RuntimeError(f"PDF extraction failed: {e}")


def extract_text_from_docx(file_path: Path) -> Tuple[str, int]:
    """Extract text from DOCX using python-docx."""
    try:
        from docx import Document
        doc = Document(str(file_path))
        paragraphs = []
        for para in doc.paragraphs:
            if para.text.strip():
                paragraphs.append(para.text)
        # Also extract tables
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    paragraphs.append(row_text)
        full_text = "\n\n".join(paragraphs)
        # Estimate pages (DOCX has no page concept; 500 words ≈ 1 page)
        word_count = len(full_text.split())
        page_count = max(1, word_count // 500)
        return full_text, page_count
    except ImportError:
        raise ImportError("python-docx not installed. Run: pip install python-docx")
    except Exception as e:
        raise RuntimeError(f"DOCX extraction failed: {e}")


def extract_text_from_pptx(file_path: Path) -> Tuple[str, int]:
    """Extract text from PPTX using python-pptx."""
    try:
        from pptx import Presentation
        prs = Presentation(str(file_path))
        slides_text = []
        for i, slide in enumerate(prs.slides):
            slide_parts = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    slide_parts.append(shape.text.strip())
            if slide_parts:
                slides_text.append(f"[Slide {i + 1}]\n" + "\n".join(slide_parts))
        return "\n\n".join(slides_text), len(prs.slides)
    except ImportError:
        raise ImportError("python-pptx not installed. Run: pip install python-pptx")
    except Exception as e:
        raise RuntimeError(f"PPTX extraction failed: {e}")


def extract_text_from_txt(file_path: Path) -> Tuple[str, int]:
    """Extract text from TXT or Markdown files."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        word_count = len(text.split())
        page_count = max(1, word_count // 400)
        return text, page_count
    except Exception as e:
        raise RuntimeError(f"Text file extraction failed: {e}")


def clean_text(text: str) -> str:
    """Basic text cleaning: normalize whitespace, remove control chars."""
    # Remove null bytes and other control characters (except newlines/tabs)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
    # Normalize multiple spaces/tabs to single space
    text = re.sub(r"[ \t]+", " ", text)
    # Normalize multiple newlines to max 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 64,
) -> List[TextChunk]:
    """
    Split text into overlapping chunks by word count.
    Respects page markers inserted during extraction.
    Returns list of TextChunk with page numbers where available.
    """
    chunks = []
    current_page = 1

    # Split into paragraphs first
    paragraphs = re.split(r"\n{2,}", text)
    words_buffer: List[str] = []
    page_for_buffer = 1

    chunk_index = 0

    for para in paragraphs:
        # Detect page marker
        page_match = re.match(r"\[(?:Page|Slide)\s+(\d+)\]", para.strip())
        if page_match:
            current_page = int(page_match.group(1))
            continue

        para_words = para.split()
        if not para_words:
            continue

        words_buffer.extend(para_words)

        while len(words_buffer) >= chunk_size:
            chunk_words = words_buffer[:chunk_size]
            chunk_text_str = " ".join(chunk_words)
            chunks.append(TextChunk(
                text=chunk_text_str,
                chunk_index=chunk_index,
                page=current_page,
                word_count=len(chunk_words),
                char_count=len(chunk_text_str),
            ))
            chunk_index += 1
            # Move forward with overlap
            words_buffer = words_buffer[chunk_size - overlap:]

    # Remaining words
    if words_buffer:
        chunk_text_str = " ".join(words_buffer)
        if chunk_text_str.strip():
            chunks.append(TextChunk(
                text=chunk_text_str,
                chunk_index=chunk_index,
                page=current_page,
                word_count=len(words_buffer),
                char_count=len(chunk_text_str),
            ))

    return chunks


def extract_document(file_path: Path, chunk_size: int = 512, overlap: int = 64) -> ExtractedDocument:
    """
    Main entry point: extract, clean, and chunk a document.
    Returns ExtractedDocument with all metadata.
    """
    suffix = file_path.suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        return ExtractedDocument(
            filename=file_path.name,
            file_type=suffix,
            page_count=0,
            full_text="",
            error=f"Unsupported file type: {suffix}. Supported: {', '.join(SUPPORTED_EXTENSIONS)}",
        )

    try:
        if suffix == ".pdf":
            raw_text, page_count = extract_text_from_pdf(file_path)
            file_type = "pdf"
        elif suffix == ".docx":
            raw_text, page_count = extract_text_from_docx(file_path)
            file_type = "docx"
        elif suffix == ".pptx":
            raw_text, page_count = extract_text_from_pptx(file_path)
            file_type = "pptx"
        elif suffix in (".txt", ".md", ".markdown"):
            raw_text, page_count = extract_text_from_txt(file_path)
            file_type = suffix.lstrip(".")
        else:
            return ExtractedDocument(
                filename=file_path.name, file_type=suffix,
                page_count=0, full_text="", error="Unsupported type"
            )

        if not raw_text.strip():
            return ExtractedDocument(
                filename=file_path.name,
                file_type=file_type,
                page_count=page_count,
                full_text="",
                error="Document appears to be empty or contains no extractable text.",
            )

        cleaned = clean_text(raw_text)
        chunks = chunk_text(cleaned, chunk_size=chunk_size, overlap=overlap)

        return ExtractedDocument(
            filename=file_path.name,
            file_type=file_type,
            page_count=page_count,
            full_text=cleaned,
            chunks=chunks,
        )

    except Exception as e:
        logger.error(f"Document extraction failed for {file_path}: {e}")
        return ExtractedDocument(
            filename=file_path.name,
            file_type=suffix.lstrip("."),
            page_count=0,
            full_text="",
            error=str(e),
        )

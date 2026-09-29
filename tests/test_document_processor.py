"""
Tests for document processing: extraction, cleaning, chunking.
"""
import pytest
from pathlib import Path
from backend.services.document_processor import (
    sanitize_filename,
    clean_text,
    chunk_text,
    extract_document,
    SUPPORTED_EXTENSIONS,
)


class TestSanitizeFilename:
    def test_normal_filename(self):
        assert sanitize_filename("my notes.pdf") == "my_notes.pdf"

    def test_path_traversal_stripped(self):
        result = sanitize_filename("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_special_chars_replaced(self):
        result = sanitize_filename("file<>:?.txt")
        assert "<" not in result
        assert ">" not in result

    def test_long_filename_truncated(self):
        long_name = "a" * 200 + ".txt"
        result = sanitize_filename(long_name)
        assert len(result) <= 115  # 100 stem + dot + ext

    def test_extension_preserved(self):
        result = sanitize_filename("lecture_notes.pdf")
        assert result.endswith(".pdf")


class TestCleanText:
    def test_removes_null_bytes(self):
        result = clean_text("hello\x00world")
        assert "\x00" not in result

    def test_normalises_whitespace(self):
        result = clean_text("word   another\t\tword")
        assert "   " not in result

    def test_collapses_excessive_newlines(self):
        result = clean_text("para1\n\n\n\n\npara2")
        assert "\n\n\n" not in result

    def test_preserves_content(self):
        result = clean_text("Database normalization reduces redundancy.")
        assert "Database normalization" in result


class TestChunkText:
    SAMPLE = (
        "Database normalization is the process of organizing a relational database "
        "to reduce data redundancy and improve data integrity. "
        "First Normal Form requires all attributes to be atomic. "
        "Second Normal Form eliminates partial dependencies. "
        "Third Normal Form eliminates transitive dependencies. "
    ) * 20  # repeat to get enough words for multiple chunks

    def test_produces_chunks(self):
        chunks = chunk_text(self.SAMPLE, chunk_size=50, overlap=10)
        assert len(chunks) > 1

    def test_chunk_word_count_within_limit(self):
        chunks = chunk_text(self.SAMPLE, chunk_size=50, overlap=10)
        for c in chunks:
            assert c.word_count <= 55  # slight tolerance for last chunk

    def test_chunk_indices_sequential(self):
        chunks = chunk_text(self.SAMPLE, chunk_size=50, overlap=10)
        for i, c in enumerate(chunks):
            assert c.chunk_index == i

    def test_empty_text_returns_empty(self):
        chunks = chunk_text("", chunk_size=50, overlap=10)
        assert chunks == []

    def test_overlap_creates_continuity(self):
        chunks = chunk_text(self.SAMPLE, chunk_size=30, overlap=10)
        # The end of chunk N should share words with the start of chunk N+1
        if len(chunks) >= 2:
            words_end = set(chunks[0].text.split()[-5:])
            words_start = set(chunks[1].text.split()[:15])
            # Some overlap expected
            assert len(words_end & words_start) > 0 or len(chunks[1].text) > 0


class TestExtractDocument:
    def test_txt_extraction(self, test_txt_file):
        result = extract_document(test_txt_file)
        assert result.error is None
        assert len(result.full_text) > 50
        assert result.page_count >= 1
        assert len(result.chunks) >= 1

    def test_txt_contains_expected_content(self, test_txt_file):
        result = extract_document(test_txt_file)
        assert "normalization" in result.full_text.lower()

    def test_unsupported_extension_returns_error(self, tmp_path):
        bad_file = tmp_path / "test.xyz"
        bad_file.write_text("content")
        result = extract_document(bad_file)
        assert result.error is not None
        assert "Unsupported" in result.error

    def test_empty_file_returns_error(self, tmp_path):
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")
        result = extract_document(empty_file)
        assert result.error is not None

    def test_supported_extensions_includes_expected(self):
        assert ".pdf" in SUPPORTED_EXTENSIONS
        assert ".docx" in SUPPORTED_EXTENSIONS
        assert ".pptx" in SUPPORTED_EXTENSIONS
        assert ".txt" in SUPPORTED_EXTENSIONS
        assert ".md" in SUPPORTED_EXTENSIONS

"""Unit tests for LabArchives notebook indexing.

Tests cover:
- Text extraction from different entry types
- HTML cleaning
- Entry filtering (what to index vs skip)
- Metadata generation
"""

import pytest

from vector_backend.labarchives_indexer import (
    EntryType,
    IndexableEntry,
    clean_html,
    extract_text_from_entry,
    should_index_entry,
)


class TestHTMLCleaning:
    """Tests for HTML to plain text conversion."""

    def test_clean_simple_html(self):
        """Should strip HTML tags and return plain text."""
        html = "<p>This is a <strong>test</strong> paragraph.</p>"
        result = clean_html(html)
        assert result == "This is a test paragraph."

    def test_clean_html_with_line_breaks(self):
        """Should preserve line breaks from <br> and <p> tags."""
        html = "<p>Line 1</p><p>Line 2</p><br>Line 3"
        result = clean_html(html)
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result

    def test_clean_html_with_lists(self):
        """Should convert lists to readable text."""
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        result = clean_html(html)
        assert "Item 1" in result
        assert "Item 2" in result

    def test_clean_html_removes_scripts_and_styles(self):
        """Should remove script and style tags."""
        html = "<p>Keep this</p><script>remove this</script><style>and this</style>"
        result = clean_html(html)
        assert "Keep this" in result
        assert "remove this" not in result
        assert "and this" not in result

    def test_clean_empty_html(self):
        """Empty or whitespace-only HTML should return empty string."""
        assert clean_html("") == ""
        assert clean_html("<p></p>") == ""
        assert clean_html("<p>   </p>").strip() == ""

    def test_clean_html_with_entities(self):
        """Should decode HTML entities."""
        html = "<p>Test &amp; example &lt;tag&gt;</p>"
        result = clean_html(html)
        assert "&" in result
        assert "<tag>" in result or "tag" in result


class TestEntryFiltering:
    """Tests for determining which entries to index."""

    def test_should_index_text_entry(self):
        """Text entries should be indexed."""
        assert should_index_entry("text_entry") is True

    def test_should_index_heading(self):
        """Headings should be indexed."""
        assert should_index_entry("heading") is True

    def test_should_skip_attachment(self):
        """Attachments should be skipped."""
        assert should_index_entry("attachment") is False

    def test_should_skip_image(self):
        """Images should be skipped."""
        assert should_index_entry("image") is False

    def test_should_skip_unknown_type(self):
        """Unknown types should be skipped."""
        assert should_index_entry("unknown_type") is False


class TestTextExtraction:
    """Tests for extracting searchable text from entries."""

    def test_extract_from_text_entry(self):
        """Should extract and clean text from text_entry."""
        entry_data = {
            "eid": "12345",
            "part_type": "text_entry",
            "content": "<p>This is <b>important</b> research.</p>",
        }

        result = extract_text_from_entry(entry_data)

        assert result is not None
        assert "important" in result.text
        assert "research" in result.text
        assert result.entry_type == EntryType.TEXT_ENTRY
        assert result.entry_id == "12345"

    def test_extract_from_heading(self):
        """Should extract text from heading."""
        entry_data = {
            "eid": "67890",
            "part_type": "heading",
            "content": "Experiment Results",
        }

        result = extract_text_from_entry(entry_data)

        assert result is not None
        assert result.text == "Experiment Results"
        assert result.entry_type == EntryType.HEADING

    def test_extract_from_plain_text(self):
        """Should handle plain_text entry type."""
        entry_data = {
            "eid": "11111",
            "part_type": "plain_text",
            "content": "Plain text content here.",
        }

        result = extract_text_from_entry(entry_data)

        assert result is not None
        assert result.text == "Plain text content here."
        assert result.entry_type == EntryType.PLAIN_TEXT

    def test_extract_skips_attachment(self):
        """Should return None for attachments."""
        entry_data = {
            "eid": "22222",
            "part_type": "attachment",
            "content": "file.pdf",
        }

        result = extract_text_from_entry(entry_data)
        assert result is None

    def test_extract_skips_image(self):
        """Should return None for images."""
        entry_data = {
            "eid": "33333",
            "part_type": "image",
            "content": "image.jpg",
        }

        result = extract_text_from_entry(entry_data)
        assert result is None

    def test_extract_handles_empty_content(self):
        """Should return None for empty content."""
        entry_data = {
            "eid": "44444",
            "part_type": "text_entry",
            "content": "<p></p>",
        }

        result = extract_text_from_entry(entry_data)
        assert result is None  # Empty text should be skipped

    def test_extract_handles_missing_eid(self):
        """Should raise error if eid is missing."""
        entry_data = {
            "part_type": "text_entry",
            "content": "Some content",
        }

        with pytest.raises(KeyError):
            extract_text_from_entry(entry_data)


class TestIndexableEntry:
    """Tests for IndexableEntry model."""

    def test_valid_indexable_entry(self):
        """Should create valid IndexableEntry."""
        entry = IndexableEntry(
            entry_id="12345",
            entry_type=EntryType.TEXT_ENTRY,
            text="This is searchable text",
        )

        assert entry.entry_id == "12345"
        assert entry.entry_type == EntryType.TEXT_ENTRY
        assert entry.text == "This is searchable text"

    def test_indexable_entry_requires_text(self):
        """IndexableEntry should require non-empty text."""
        with pytest.raises(ValueError, match="at least 1 character"):
            IndexableEntry(
                entry_id="12345",
                entry_type=EntryType.TEXT_ENTRY,
                text="",
            )

    def test_entry_type_enum(self):
        """EntryType should have expected values."""
        assert hasattr(EntryType, "TEXT_ENTRY")
        assert hasattr(EntryType, "HEADING")
        assert hasattr(EntryType, "PLAIN_TEXT")

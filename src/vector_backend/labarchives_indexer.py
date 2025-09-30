"""LabArchives notebook indexing utilities.

Extracts searchable text from LabArchives notebook entries and prepares them
for vector indexing.
"""

from enum import Enum

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field


class EntryType(str, Enum):
    """Types of LabArchives entries that can be indexed."""

    TEXT_ENTRY = "text_entry"
    HEADING = "heading"
    PLAIN_TEXT = "plain_text"


class IndexableEntry(BaseModel):
    """A LabArchives entry that contains searchable text.

    Attributes:
        entry_id: LabArchives entry ID (eid)
        entry_type: Type of entry
        text: Cleaned, searchable text content
    """

    entry_id: str
    entry_type: EntryType
    text: str = Field(..., min_length=1)


def clean_html(html: str) -> str:
    """Convert HTML to clean plain text.

    Args:
        html: HTML string to clean

    Returns:
        Plain text with HTML tags removed

    Example:
        >>> clean_html("<p>Hello <b>world</b></p>")
        'Hello world'
    """
    if not html or not html.strip():
        return ""

    # Parse HTML
    soup = BeautifulSoup(html, "html.parser")

    # Remove script and style elements
    for element in soup(["script", "style"]):
        element.decompose()

    # Get text and clean up whitespace
    text = soup.get_text(separator=" ", strip=True)

    # Normalize whitespace
    text = " ".join(text.split())

    return text


def should_index_entry(entry_type: str) -> bool:
    """Determine if an entry type should be indexed.

    Args:
        entry_type: LabArchives entry part_type

    Returns:
        True if entry should be indexed, False otherwise
    """
    # Normalize: API returns "text entry" with space, but we use underscore internally
    normalized_type = entry_type.lower().replace(" ", "_")
    indexable_types = {"text_entry", "heading", "plain_text"}
    return normalized_type in indexable_types


def extract_text_from_entry(entry_data: dict) -> IndexableEntry | None:
    """Extract searchable text from a LabArchives entry.

    Args:
        entry_data: Dictionary containing entry data with keys:
            - eid: Entry ID
            - part_type: Entry type
            - content: Entry content

    Returns:
        IndexableEntry if text can be extracted, None otherwise

    Raises:
        KeyError: If required fields are missing
    """
    entry_id = entry_data["eid"]
    part_type = entry_data["part_type"]
    content = entry_data.get("content", "")

    # Skip non-indexable types
    if not should_index_entry(part_type):
        return None

    # Normalize entry type (API returns "text entry" with space)
    normalized_type = part_type.lower().replace(" ", "_")

    # Clean HTML if present
    if normalized_type == "text_entry":
        text = clean_html(content)
    else:
        # Plain text or heading
        text = content.strip()

    # Skip empty content
    if not text:
        return None

    # Map to EntryType enum (using normalized type)
    try:
        entry_type = EntryType(normalized_type)
    except ValueError:
        # Unknown indexable type, default to text_entry
        entry_type = EntryType.TEXT_ENTRY

    return IndexableEntry(
        entry_id=entry_id,
        entry_type=entry_type,
        text=text,
    )

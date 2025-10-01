from __future__ import annotations

import pytest

from labarchives_mcp.transform import (
    LabArchivesAPIError,
    NotebookTransformer,
    translate_labarchives_fault,
)


def test_notebook_transformer_parses_minimal_xml() -> None:
    """Given a minimal XML response, when parsing notebooks, then return normalized JSON."""
    xml_payload = """
        <response status="success">
            <notebooks>
                <notebook>
                    <nbid>123</nbid>
                    <name>Example</name>
                    <owner>user@example.com</owner>
                    <owner-email>user@example.com</owner-email>
                    <owner-name>Example User</owner-name>
                    <created-at>2025-01-01 00:00:00</created-at>
                    <modified-at>2025-01-05 13:45:09</modified-at>
                </notebook>
            </notebooks>
        </response>
    """
    notebooks = NotebookTransformer.parse_notebook_list(xml_payload)
    assert notebooks == [
        {
            "nbid": "123",
            "name": "Example",
            "owner": "user@example.com",
            "owner_email": "user@example.com",
            "owner_name": "Example User",
            "created_at": "2025-01-01T00:00:00Z",
            "modified_at": "2025-01-05T13:45:09Z",
        }
    ]


def test_notebook_transformer_rejects_missing_fields() -> None:
    """Given an invalid record missing nbid, when parsing, then raise a validation error."""
    xml_payload = """
        <response status="success">
            <notebooks>
                <notebook>
                    <name>Missing ID</name>
                </notebook>
            </notebooks>
        </response>
    """
    with pytest.raises(ValueError, match="id"):
        NotebookTransformer.parse_notebook_list(xml_payload)


def test_notebook_transformer_requires_owner_email() -> None:
    """Given missing owner metadata, when parsing notebooks, then use fallback defaults."""
    xml_payload = """
        <response status="success">
            <notebooks>
                <notebook>
                    <nbid>123</nbid>
                    <name>Example</name>
                    <owner>user@example.com</owner>
                    <created-at>2025-01-01 00:00:00</created-at>
                    <modified-at>2025-01-05 13:45:09</modified-at>
                </notebook>
            </notebooks>
        </response>
    """
    # Should not raise - uses fallback from <owner> tag
    result = NotebookTransformer.parse_notebook_list(xml_payload)
    assert len(result) == 1
    assert result[0]["owner_email"] == "user@example.com"  # Fallback from <owner>


def test_notebook_transformer_rejects_invalid_timestamp() -> None:
    """Given an invalid timestamp, when parsing notebooks, then raise a validation error."""
    xml_payload = """
        <response status="success">
            <notebooks>
                <notebook>
                    <nbid>123</nbid>
                    <name>Example</name>
                    <owner>user@example.com</owner>
                    <owner-email>user@example.com</owner-email>
                    <owner-name>Example User</owner-name>
                    <created-at>not-a-date</created-at>
                    <modified-at>2025-01-05 13:45:09</modified-at>
                </notebook>
            </notebooks>
        </response>
    """
    with pytest.raises(ValueError, match="created-at|invalid"):
        NotebookTransformer.parse_notebook_list(xml_payload)


@pytest.mark.parametrize(  # type: ignore[misc]
    ("code", "message", "expected_retryable"),
    [
        (4500, "Unknown", False),
        (4505, "Rate Limit", True),
        (4999, "Session expired", False),
    ],
)
def test_translate_labarchives_fault_maps_codes(
    code: int, message: str, expected_retryable: bool
) -> None:
    """Given a LabArchives API fault, when translating, then emit MCP-consistent error metadata."""
    error = LabArchivesAPIError(code=code, message=message)
    translated = translate_labarchives_fault(error)

    assert translated["code"] == f"labarchives:{code}"
    assert translated["message"] == message
    assert translated["retryable"] is expected_retryable
    assert translated["domain"] == "labarchives"

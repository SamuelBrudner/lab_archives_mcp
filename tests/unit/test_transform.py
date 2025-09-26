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
                    <created-at>2025-01-01T00:00:00Z</created-at>
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
            "created_at": "2025-01-01T00:00:00Z",
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
    with pytest.raises(ValueError, match="nbid"):
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

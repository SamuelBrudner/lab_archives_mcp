"""Tests for pagination helper utilities."""

from labarchives_mcp.tools.utils import paginate_items


def test_paginates_with_limit_and_reports_meta() -> None:
    items = [{"id": i} for i in range(5)]

    sliced, meta = paginate_items(items, limit=2, offset=1)

    assert sliced == [{"id": 1}, {"id": 2}]
    assert meta["total"] == 5
    assert meta["offset"] == 1
    assert meta["limit"] == 2
    assert meta["truncated"] is True


def test_paginates_without_limit_returns_all() -> None:
    items = [{"id": i} for i in range(3)]

    sliced, meta = paginate_items(items, limit=None, offset=0)

    assert sliced == items
    assert meta["truncated"] is False

"""Reusable pagination envelope (Step 11).

Paginated list endpoints return ``{"items": [...], "pagination": {...}}``
instead of a raw array. Concrete list models compose these, e.g.::

    class HotelListResponse(BaseModel):
        items: list[HotelListItem]
        pagination: PaginationMetadata
"""

from pydantic import BaseModel, ConfigDict


class PaginationMetadata(BaseModel):
    """Page bookkeeping computed from total_items (never from client math)."""

    model_config = ConfigDict(from_attributes=True)

    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool


def build_metadata(page: int, page_size: int, total_items: int) -> PaginationMetadata:
    """Build metadata; total_pages is 0 when there is nothing to page."""
    total_pages = (total_items + page_size - 1) // page_size if total_items else 0
    return PaginationMetadata(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    )

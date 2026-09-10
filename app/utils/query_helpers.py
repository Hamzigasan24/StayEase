"""Reusable query helpers for search/filter/sort/pagination (Step 11).

All helpers are DB-side building blocks: validation raises HTTP 400
(never 422, per the API contract), sorting only accepts whitelisted
column attributes (no string interpolation into SQL), and pagination
uses SQL OFFSET/LIMIT with a separate COUNT query.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Query

from app.schemas.pagination_schema import PaginationMetadata, build_metadata

MAX_PAGE_SIZE = 100


def validate_page(page: int, page_size: int) -> tuple[int, int]:
    """Enforce page >= 1 and 1 <= page_size <= 100 (400 otherwise)."""
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page must be >= 1",
        )
    if not 1 <= page_size <= MAX_PAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"page_size must be between 1 and {MAX_PAGE_SIZE}",
        )
    return page, page_size


def validate_sort(sort_by: str | None, sort_order: str, allowed: dict[str, object]) -> tuple[object | None, bool]:
    """Resolve a whitelisted sort column + direction (400 on abuse).

    Returns (column_attribute_or_None, descending_bool). Anything not
    in ``allowed`` — including SQL-injection probes — gets a 400.
    """
    order = (sort_order or "asc").lower()
    if order not in ("asc", "desc"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="sort_order must be 'asc' or 'desc'",
        )
    if sort_by is None:
        return None, False
    column = allowed.get(sort_by)
    if column is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sort_by. Allowed: {', '.join(sorted(allowed))}",
        )
    return column, order == "desc"


def apply_sort(query: Query, column: object | None, descending: bool, default: object | None = None) -> Query:
    """ORDER BY a validated column (or a default, e.g. newest first)."""
    if column is not None:
        return query.order_by(column.desc() if descending else column.asc())
    if default is not None:
        return query.order_by(default)
    return query


def paginate(query: Query, page: int, page_size: int) -> tuple[list, PaginationMetadata]:
    """COUNT once, then fetch one page. Returns (items, metadata)."""
    total_items = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, build_metadata(page, page_size, total_items)

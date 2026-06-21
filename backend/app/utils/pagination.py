"""Shared pagination helpers for list endpoints.

Every list endpoint in the app uses the same two query parameters:

  - skip  (alias: offset): number of records to skip (default 0)
  - limit (alias: page_size): maximum records to return (default 20, max 200)

FastAPI dependencies are used so all routes get the same validated,
documented parameters without duplicating Annotated[int, Query(...)] blocks.

The response envelope (`PagedResponse`) wraps the data list with metadata
the frontend needs to render pagination controls (total count, whether
there's a next/previous page).

Why cap at 200?
  A hard cap prevents accidental or malicious full-table scans via the API.
  For larger exports the dedicated /export endpoints exist.
"""

from typing import Generic, TypeVar
from fastapi import Query
from pydantic import BaseModel
from pydantic.generics import GenericModel

T = TypeVar("T")


class PageParams:
    """FastAPI dependency for pagination query parameters.

    Usage::

        @router.get("/")
        def list_items(
            page: PageParams = Depends(),
            db: Session = Depends(get_db),
        ):
            query = db.query(MyModel)
            total = query.count()
            items = query.offset(page.skip).limit(page.limit).all()
            return PagedResponse.create(items, total, page)
    """

    def __init__(
        self,
        skip: int = Query(0, ge=0, description="Number of records to skip (offset)"),
        limit: int = Query(20, ge=1, le=200, description="Maximum records to return (1–200)"),
    ):
        self.skip = skip
        self.limit = limit


class PageMeta(BaseModel):
    """Metadata block returned with every paginated response."""
    total: int
    skip: int
    limit: int
    has_next: bool
    has_prev: bool


class PagedResponse(GenericModel, Generic[T]):
    """Generic paginated envelope.

    All list endpoints return this shape:

        {
            "data": [...],
            "meta": {
                "total": 142,
                "skip": 20,
                "limit": 20,
                "has_next": true,
                "has_prev": true
            }
        }
    """
    data: list[T]
    meta: PageMeta

    @classmethod
    def create(cls, data: list, total: int, page: PageParams) -> "PagedResponse":
        return cls(
            data=data,
            meta=PageMeta(
                total=total,
                skip=page.skip,
                limit=page.limit,
                has_next=(page.skip + page.limit) < total,
                has_prev=page.skip > 0,
            ),
        )

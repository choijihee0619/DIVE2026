"""API_Contract_260714.yaml 공통 Schema(Pagination 등)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Pagination(BaseModel):
    page: int
    size: int
    total_elements: int
    total_pages: int


def build_pagination(page: int, size: int, total_elements: int) -> Pagination:
    total_pages = (total_elements + size - 1) // size if size > 0 else 0
    return Pagination(page=page, size=size, total_elements=total_elements, total_pages=max(total_pages, 1 if total_elements else 0))


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)

    @property
    def skip(self) -> int:
        return (self.page - 1) * self.size

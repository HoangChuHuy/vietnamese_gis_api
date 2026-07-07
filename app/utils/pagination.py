from fastapi import Query

from app.core.config import settings


class Pagination:
    def __init__(self, page: int, limit: int):
        self.page = page
        self.limit = limit
        self.skip = (page - 1) * limit


def pagination_params(
    page: int = Query(1, ge=1, description="Số trang, bắt đầu từ 1"),
    limit: int = Query(
        settings.default_page_size,
        ge=1,
        le=settings.max_page_size,
        description="Số bản ghi mỗi trang",
    ),
) -> Pagination:
    return Pagination(page=page, limit=limit)


def paginated_response(items: list, total: int, pagination: Pagination) -> dict:
    return {
        "items": items,
        "page": pagination.page,
        "limit": pagination.limit,
        "total": total,
        "total_pages": (total + pagination.limit - 1) // pagination.limit if pagination.limit else 0,
    }

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class GeoJSONGeometry(BaseModel):
    type: Literal["Polygon", "MultiPolygon"]
    coordinates: Any

    @field_validator("coordinates")
    @classmethod
    def coordinates_not_empty(cls, v):
        if not v:
            raise ValueError("coordinates không được rỗng")
        return v


class BoundaryCreate(BaseModel):
    unit_code: str
    geometry: GeoJSONGeometry
    era: Optional[str] = Field(None, description="pre_reform | post_reform")
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    source: Optional[str] = None
    status: Literal["active", "inactive"] = "active"
    auto_fix: bool = Field(
        False,
        description="Nếu geometry tự cắt (self-intersecting), tự sửa bằng buffer(0) thay vì từ chối request",
    )


class BoundaryBulkCreate(BaseModel):
    boundaries: list[BoundaryCreate] = Field(..., min_length=1, max_length=1000)


class IntersectRequest(BaseModel):
    geometry: GeoJSONGeometry = Field(..., description="Vùng AOI (Polygon/MultiPolygon) cần tìm giao cắt")
    province_code: Optional[str] = None
    level: Optional[int] = Field(None, ge=1, le=3)
    status: Optional[str] = Field("active", description="Bỏ trống để lấy cả active/inactive")

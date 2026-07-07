from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class UnitCreate(BaseModel):
    code: str = Field(..., description="Mã đơn vị hành chính, duy nhất")
    name: str
    slug: Optional[str] = None
    type: str = Field(..., description="vd: tinh, thanh-pho, huyen, xa, phuong...")
    node_type: Optional[str] = None
    name_with_type: Optional[str] = None
    path: Optional[str] = None
    path_with_type: Optional[str] = None
    parent_code: Optional[str] = None
    level: int = Field(..., ge=1, le=3)
    status: Literal["active", "inactive"] = "active"


class UnitBulkCreate(BaseModel):
    units: list[UnitCreate] = Field(..., min_length=1, max_length=2000)


class RestructureRequest(BaseModel):
    action: Literal["merge", "split", "rename", "dissolve"]
    target_codes: list[str] = Field(
        default_factory=list,
        description="Mã đơn vị đích sau khi sáp nhập/tách (bỏ trống nếu action=rename)",
    )
    new_name: Optional[str] = Field(None, description="Tên mới, bắt buộc khi action=rename")
    legal_document_id: Optional[str] = None
    effective_date: Optional[datetime] = None
    reason: Optional[str] = None

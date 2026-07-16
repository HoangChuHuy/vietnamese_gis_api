from typing import Literal, Optional

from pydantic import BaseModel, model_validator


class AddressConvertRequest(BaseModel):
    province_code: Optional[str] = None
    district_code: Optional[str] = None
    ward_code: Optional[str] = None

    @model_validator(mode="after")
    def at_least_one_code(self):
        if not (self.province_code or self.district_code or self.ward_code):
            raise ValueError("Cần ít nhất 1 trong: province_code, district_code, ward_code")
        return self


class AddressConvertByNameRequest(BaseModel):
    province_name: str
    district_name: Optional[str] = None
    ward_name: Optional[str] = None
    direction: Literal["old_to_new", "new_to_old"]

    @model_validator(mode="after")
    def hierarchy_order(self):
        if self.ward_name and self.direction == "old_to_new" and not self.district_name:
            raise ValueError(
                "Cần district_name khi truyền ward_name với direction=old_to_new "
                "(xã/phường cũ luôn thuộc 1 quận/huyện cũ, dùng để tra cứu và làm fallback)"
            )
        return self

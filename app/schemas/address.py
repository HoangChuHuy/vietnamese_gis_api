from typing import Optional

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

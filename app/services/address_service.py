from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.collections import BOUNDARIES, UNITS
from app.schemas.address import AddressConvertRequest
from app.utils.serialization import serialize_doc


async def convert_address(db: AsyncIOMotorDatabase, payload: AddressConvertRequest) -> dict:
    old_code = payload.ward_code or payload.district_code or payload.province_code

    old_unit = await db[UNITS].find_one({"code": old_code})
    boundary = await db[BOUNDARIES].find_one({"unit_code": old_code})

    new_unit: Optional[dict] = None
    resolution_note = "Không tìm thấy dữ liệu sáp nhập cho mã này."

    if boundary and boundary.get("merged_into_code"):
        new_code = boundary["merged_into_code"]
        new_unit = await db[UNITS].find_one({"code": new_code})
        resolution_note = f"Đã sáp nhập vào đơn vị mã {new_code} (theo administrative_boundaries.merged_into_code)."
    elif old_unit and old_unit.get("status") == "active":
        new_unit = old_unit
        resolution_note = "Đơn vị vẫn còn hiệu lực, không có thay đổi."

    return {
        "input_code": old_code,
        "old_unit": serialize_doc(old_unit) if old_unit else None,
        "new_unit": serialize_doc(new_unit) if new_unit else None,
        "resolved": new_unit is not None,
        "note": resolution_note,
    }

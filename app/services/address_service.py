import re
from typing import Optional

from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.collections import BOUNDARIES, LEGAL_DOCUMENTS, UNITS
from app.schemas.address import AddressConvertByNameRequest, AddressConvertRequest
from app.utils.serialization import serialize_doc, serialize_docs


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


def _name_pattern(name: str) -> re.Pattern:
    return re.compile(re.escape(name.strip()), re.IGNORECASE)


_ADMIN_PREFIX_RE = re.compile(
    r"^(thành phố|tp\.?|thị xã|tx\.?|thị trấn|tt\.?|quận|q\.?|huyện|h\.?|phường|p\.?|xã|x\.?|tỉnh)\s+",
    re.IGNORECASE,
)


def _strip_admin_prefix(name: str) -> str:
    """Bỏ tiền tố loại hình hành chính (Thành phố/Quận/Huyện/Phường/Xã/Tỉnh...).

    `administrative_boundaries.district_name` chỉ lưu tên trần (VD "Tuyên Quang"),
    không có field "district_name_with_type" — nếu người dùng gõ kèm tiền tố
    (VD "thành phố Tuyên Quang") thì pattern sẽ dài hơn field lưu trong DB và
    không bao giờ khớp được. Ward/tỉnh không cần hàm này vì đã có field
    name_with_type riêng để khớp trực tiếp.
    """
    stripped = name.strip()
    match = _ADMIN_PREFIX_RE.match(stripped)
    return stripped[match.end() :].strip() if match else stripped


async def _match_units_by_name(
    db: AsyncIOMotorDatabase, level: int, name: str, parent_code: Optional[str] = None
) -> list[dict]:
    pattern = _name_pattern(name)
    query: dict = {"level": level, "$or": [{"name": pattern}, {"name_with_type": pattern}, {"slug": pattern}]}
    if parent_code is not None:
        query["parent_code"] = parent_code
    cursor = db[UNITS].find(query)
    return await cursor.to_list(length=50)


async def _resolve_one(db: AsyncIOMotorDatabase, level: int, level_label: str, name: str, parent_code: Optional[str] = None, parent_label: str = "") -> dict:
    matches = await _match_units_by_name(db, level, name, parent_code=parent_code)
    if not matches:
        raise HTTPException(422, f"Không tìm thấy {level_label} khớp với '{name}'{parent_label}")
    if len(matches) > 1:
        raise HTTPException(
            422,
            detail={
                "message": f"Tên {level_label} '{name}' khớp nhiều đơn vị, vui lòng nhập chính xác hơn",
                "candidates": serialize_docs(matches),
            },
        )
    return matches[0]


async def _resolve_province(db: AsyncIOMotorDatabase, province_name: str) -> dict:
    return await _resolve_one(db, 1, "tỉnh/thành phố", province_name)


async def _attach_legal_documents(db: AsyncIOMotorDatabase, boundaries: list[dict]) -> None:
    """Gắn kèm văn bản pháp lý (Nghị quyết sáp nhập) vào từng bản ghi xã/phường mới.

    `administrative_boundaries` (bản ghi post_reform) lưu sẵn `legal_document_id`
    trỏ sang collection `legal_documents` — tra ngược lại để trả kèm số hiệu, ngày
    hiệu lực, tiêu đề... của văn bản đã tạo ra đơn vị này. `merge_info` (nếu có)
    đã nằm sẵn trên bản ghi, mô tả các xã/phường cũ đã gộp thành đơn vị này.
    """
    doc_ids = {b["legal_document_id"] for b in boundaries if b.get("legal_document_id")}
    if not doc_ids:
        return
    legal_docs = await db[LEGAL_DOCUMENTS].find({"_id": {"$in": list(doc_ids)}}).to_list(length=len(doc_ids))
    by_id = {ld["_id"]: ld for ld in legal_docs}
    for b in boundaries:
        legal_doc = by_id.get(b.get("legal_document_id"))
        if legal_doc:
            b["legal_document"] = legal_doc


async def _convert_ward_old_to_new(
    db: AsyncIOMotorDatabase, province: dict, district_name: str, ward_name: str
) -> dict:
    """Tỉnh cũ + quận/huyện cũ + xã/phường cũ -> xã/phường mới.

    Tra thẳng trên `administrative_boundaries` (không qua administrative_units) vì
    collection này lưu district_name của bản ghi cũ kèm merged_into_code -> đáng tin
    cậy hơn so với việc dò cây parent_code (huyện đã bị xoá hẳn sau sáp nhập, không
    còn đơn vị kế thừa nên không thể dò theo administrative_units).

    Lọc theo `province_name` (text) thay vì `province_code`: cùng 1 tỉnh nhưng
    administrative_boundaries lưu 2 mã tỉnh khác nhau cho 2 kỳ pre_reform/post_reform
    (VD Gia Lai = "64" trước sáp nhập, "52" sau sáp nhập) — administrative_units chỉ
    có 1 bản ghi/tỉnh nên `province["code"]` chỉ đại diện đúng cho 1 trong 2 kỳ đó.

    Lọc `era=pre_reform` để tránh trùng unit_code giữa 2 kỳ, và loại thêm những bản
    ghi có `legal_document_id` (~3.2k bản ghi): đây là "bản sao" của chính xã/phường
    MỚI được gắn nhãn era=pre_reform để lưu vết địa giới trước sáp nhập (cùng unit_id
    với bản ghi post_reform, cùng unit_code), không phải xã/phường cũ thật sự —
    xã/phường cũ thật sự (bị thay thế) không có legal_document_id.
    """
    province_pattern = _name_pattern(province["name"])
    district_pattern = _name_pattern(_strip_admin_prefix(district_name))
    ward_pattern = _name_pattern(ward_name)

    exact_query = {
        "province_name": province_pattern,
        "district_name": district_pattern,
        "era": "pre_reform",
        "legal_document_id": {"$exists": False},
        "$or": [{"unit_name": ward_pattern}, {"unit_name_with_type": ward_pattern}],
    }
    exact_matches = await db[BOUNDARIES].find(exact_query, {"geometry": 0}).to_list(length=50)

    if len(exact_matches) > 1:
        raise HTTPException(
            422,
            detail={
                "message": f"Tên xã/phường '{ward_name}' khớp nhiều bản ghi trong quận/huyện cũ '{district_name}', vui lòng nhập chính xác hơn",
                "candidates": serialize_docs(exact_matches),
            },
        )

    if len(exact_matches) == 1:
        old_boundary = exact_matches[0]
        new_code = old_boundary.get("merged_into_code")
        mapped_units: list[dict] = []
        if new_code:
            new_boundary = await db[BOUNDARIES].find_one(
                {"unit_code": new_code, "era": "post_reform"}, {"geometry": 0}
            )
            if new_boundary:
                mapped_units = [new_boundary]
            note = f"Đã sáp nhập vào đơn vị mã {new_code} (theo administrative_boundaries.merged_into_code)."
        else:
            mapped_units = [old_boundary]
            note = "Đơn vị vẫn còn hiệu lực, không có thay đổi."
        await _attach_legal_documents(db, mapped_units)
        return {
            "match_type": "exact",
            "matched_unit": serialize_doc(old_boundary),
            "mapped_units": serialize_docs(mapped_units),
            "resolved": len(mapped_units) > 0,
            "note": note,
        }

    # Không có bản ghi merged_into_code trực tiếp cho xã/phường này -> có thể do nó
    # bị TÁCH, chỉ một phần sáp nhập vào (các) đơn vị mới khác nhau (không phải gộp
    # nguyên xã). Trường hợp này administrative_boundaries không có dòng riêng cho xã
    # cũ, chỉ còn dấu vết trong `merge_info` (text tự do) của (các) xã mới liên quan
    # — VD "Kim Phú" ở Tuyên Quang bị tách 1 phần vào cả "Minh Xuân" lẫn "Mỹ Lâm".
    bare_ward = _strip_admin_prefix(ward_name)
    split_matches = await db[BOUNDARIES].find(
        {
            "province_name": province_pattern,
            "era": "post_reform",
            "merge_info": _name_pattern(bare_ward),
        },
        {"geometry": 0},
    ).to_list(length=50)

    if split_matches:
        await _attach_legal_documents(db, split_matches)
        old_unit: Optional[dict] = None
        try:
            district = await _resolve_one(db, 2, "quận/huyện", district_name, parent_code=province["code"])
            old_unit = await db[UNITS].find_one(
                {"level": 3, "parent_code": district["code"], "name": _name_pattern(bare_ward)}
            )
        except HTTPException:
            pass
        return {
            "match_type": "split_match",
            "matched_unit": serialize_doc(old_unit) if old_unit else None,
            "mapped_units": serialize_docs(split_matches),
            "resolved": True,
            "note": (
                f"Xã/phường '{ward_name}' không có bản ghi sáp nhập trực tiếp (merged_into_code) — có thể đã bị "
                f"TÁCH một phần vào {len(split_matches)} đơn vị mới, suy ra từ nội dung mô tả sáp nhập "
                "(administrative_boundaries.merge_info)."
            ),
        }

    # Vẫn không tìm thấy gì -> fallback cuối: liệt kê toàn bộ xã/phường mới hình
    # thành từ việc sáp nhập những xã/phường thuộc quận/huyện cũ này.
    mapped_units = await _district_merge_candidates(db, province_pattern, district_pattern)
    await _attach_legal_documents(db, mapped_units)

    return {
        "match_type": "district_candidates",
        "matched_unit": None,
        "mapped_units": serialize_docs(mapped_units),
        "resolved": len(mapped_units) > 0,
        "note": (
            f"Không tìm thấy chính xác xã/phường '{ward_name}' trong quận/huyện cũ '{district_name}'. "
            f"Đây là danh sách {len(mapped_units)} xã/phường mới có thể tương ứng, suy ra từ các xã/phường "
            "cũ cùng quận/huyện đã sáp nhập (administrative_boundaries.merged_into_code)."
            if mapped_units
            else f"Không tìm thấy xã/phường '{ward_name}' lẫn dữ liệu sáp nhập nào cho quận/huyện cũ '{district_name}'."
        ),
    }


async def _district_merge_candidates(
    db: AsyncIOMotorDatabase, province_pattern: re.Pattern, district_pattern: re.Pattern
) -> list[dict]:
    """Toàn bộ xã/phường mới hình thành từ việc sáp nhập các xã/phường thuộc 1 quận/huyện cũ.

    Quận/huyện tự nó không có "quận/huyện mới" kế thừa (cấp huyện đã bị xoá hẳn theo
    dữ liệu — 0 bản ghi administrative_boundaries level=2 có merged_into_code), nên
    đây là thông tin gần nhất có thể suy ra: gộp merged_into_code của mọi xã/phường
    cũ từng thuộc quận/huyện đó.
    """
    district_boundaries = await db[BOUNDARIES].find(
        {
            "province_name": province_pattern,
            "district_name": district_pattern,
            "era": "pre_reform",
            "legal_document_id": {"$exists": False},
            "merged_into_code": {"$ne": None},
        },
        {"geometry": 0},
    ).to_list(length=500)
    new_codes = sorted({b["merged_into_code"] for b in district_boundaries if b.get("merged_into_code")})
    if not new_codes:
        return []
    return await (
        db[BOUNDARIES]
        .find({"unit_code": {"$in": new_codes}, "era": "post_reform"}, {"geometry": 0})
        .to_list(length=500)
    )


_MERGE_INFO_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")


def _parse_merge_info_names(merge_info: str) -> list[str]:
    """Tách `merge_info` (VD "Khâm Thiên, Điện Biên (1 phần), ...") thành tên trần từng xã.

    Chỉ tách theo dấu phẩy (tên xã có thể chứa dấu gạch ngang, VD "Văn Miếu - Quốc Tử
    Giám", không được tách nhầm) và bỏ hậu tố ghi chú dạng "(...)" ở cuối mỗi tên
    (VD "(1 phần)", "(huyện Chư Sê)").
    """
    names = []
    for part in merge_info.split(","):
        bare = _MERGE_INFO_SUFFIX_RE.sub("", part).strip()
        if bare:
            names.append(bare)
    return names


async def _resolve_orphan_old_ward(db: AsyncIOMotorDatabase, province: dict, name: str) -> Optional[dict]:
    """Tìm xã/phường cũ theo tên trong `administrative_units` khi không có bản ghi
    `administrative_boundaries` nào cho nó (bị tách hết, giống trường hợp Kim Phú).

    Khoanh vùng theo toàn bộ quận/huyện của tỉnh (không biết trước quận/huyện cụ thể).
    Chỉ loại 1 candidate nếu mã của nó trùng với 1 bản ghi boundary CÙNG TÊN (bản sao/
    trùng mã của chính nó, giống trường hợp administrative_units gán sai level/tỉnh) —
    nếu mã trùng nhưng tên hoàn toàn khác (VD "Lê Đại Hành" trùng mã với "Hai Bà Trưng")
    thì đó chỉ là trùng mã ngẫu nhiên giữa 2 thực thể không liên quan trong dữ liệu lỗi,
    vẫn nhận candidate vì bỏ sót còn tệ hơn (thiếu hẳn 1 xã cũ trong kết quả tách/nhập).
    """
    district_codes = await db[UNITS].distinct("code", {"level": 2, "parent_code": province["code"]})
    if not district_codes:
        return None
    candidates = await db[UNITS].find(
        {"level": 3, "parent_code": {"$in": district_codes}, "name": _name_pattern(name)}
    ).to_list(length=10)
    if not candidates:
        return None

    codes = [c["code"] for c in candidates]
    boundary_docs = await db[BOUNDARIES].find({"unit_code": {"$in": codes}}, {"geometry": 0}).to_list(length=50)
    boundary_names_by_code: dict[str, set[str]] = {}
    for b in boundary_docs:
        boundary_names_by_code.setdefault(b["unit_code"], set()).add((b.get("unit_name") or "").strip().lower())

    name_lower = name.strip().lower()
    for c in candidates:
        colliding_names = boundary_names_by_code.get(c["code"])
        if not colliding_names:
            return c
        if not any(name_lower in n or n in name_lower for n in colliding_names):
            return c
    return None


async def _convert_ward_new_to_old(db: AsyncIOMotorDatabase, province: dict, ward_name: str) -> dict:
    """Tỉnh mới + xã/phường mới -> danh sách xã/phường cũ đã sáp nhập vào đó.

    Quận/huyện không còn tồn tại ở địa chỉ mới nên chỉ khoanh vùng theo tỉnh.
    Lọc theo `province_name` (không phải `province_code`, xem lý do ở
    `_convert_ward_old_to_new`) và `era=post_reform` để chỉ khớp bản ghi mới.
    """
    province_pattern = _name_pattern(province["name"])
    ward_pattern = _name_pattern(ward_name)
    matches = await db[BOUNDARIES].find(
        {
            "province_name": province_pattern,
            "$or": [{"unit_name": ward_pattern}, {"unit_name_with_type": ward_pattern}],
            "era": "post_reform",
        },
        {"geometry": 0},
    ).to_list(length=50)

    if len(matches) > 1:
        raise HTTPException(
            422,
            detail={
                "message": f"Tên xã/phường '{ward_name}' khớp nhiều đơn vị trong '{province['name']}', vui lòng nhập chính xác hơn",
                "candidates": serialize_docs(matches),
            },
        )
    if not matches:
        return {
            "match_type": "not_found",
            "matched_unit": None,
            "mapped_units": [],
            "resolved": False,
            "note": f"Không tìm thấy xã/phường '{ward_name}' đang hoạt động trong '{province['name']}'.",
        }

    new_boundary = matches[0]
    code = new_boundary["unit_code"]

    old_boundaries = await db[BOUNDARIES].find(
        {"merged_into_code": code, "era": "pre_reform", "legal_document_id": {"$exists": False}},
        {"geometry": 0},
    ).to_list(length=200)
    for b in old_boundaries:
        b["contribution"] = "full"
    found_names = {b["unit_name"].strip().lower() for b in old_boundaries if b.get("unit_name")}

    # merged_into_code chỉ trỏ về ĐÍCH CHÍNH của mỗi xã cũ — xã bị TÁCH và chỉ góp
    # "1 phần" vào đơn vị này thường có merged_into_code trỏ sang nơi khác, hoặc
    # không còn bản ghi boundary nào (như Kim Phú). merge_info trên chính bản ghi
    # mới lại liệt kê ĐẦY ĐỦ mọi xã cũ đã góp phần -> dò thêm để không bị thiếu.
    partial_units: list[dict] = []
    for raw_name in _parse_merge_info_names(new_boundary.get("merge_info") or ""):
        if raw_name.strip().lower() in found_names:
            continue
        name_pattern = _name_pattern(raw_name)
        extra_boundary = await db[BOUNDARIES].find_one(
            {
                "province_name": province_pattern,
                "era": "pre_reform",
                "legal_document_id": {"$exists": False},
                "$or": [{"unit_name": name_pattern}, {"unit_name_with_type": name_pattern}],
            },
            {"geometry": 0},
        )
        found = extra_boundary or await _resolve_orphan_old_ward(db, province, raw_name)
        if found:
            found["contribution"] = "partial"
            partial_units.append(found)
            found_names.add(raw_name.strip().lower())

    mapped_units = old_boundaries + partial_units
    if mapped_units:
        if partial_units:
            note = (
                f"Đã sáp nhập từ {len(mapped_units)} đơn vị cũ vào mã {code}: {len(old_boundaries)} đơn vị gộp "
                f"toàn bộ (administrative_boundaries.merged_into_code) và {len(partial_units)} đơn vị chỉ góp "
                "một phần (suy ra từ administrative_boundaries.merge_info)."
            )
        else:
            note = (
                f"Đã sáp nhập từ {len(mapped_units)} đơn vị cũ vào mã {code} "
                "(theo administrative_boundaries.merged_into_code)."
            )
    else:
        mapped_units = [new_boundary]
        note = "Đơn vị vẫn còn hiệu lực, không có thay đổi."

    await _attach_legal_documents(db, [new_boundary])

    return {
        "match_type": "exact",
        "matched_unit": serialize_doc(new_boundary),
        "mapped_units": serialize_docs(mapped_units),
        "resolved": len(mapped_units) > 0,
        "note": note,
    }


async def list_old_districts(db: AsyncIOMotorDatabase, province_name: str) -> list[str]:
    """Danh sách quận/huyện cũ (trước sáp nhập) của 1 tỉnh — để đổ vào dropdown bước 2."""
    province = await _resolve_province(db, province_name)
    pattern = _name_pattern(province["name"])
    names = await db[BOUNDARIES].distinct(
        "district_name",
        {
            "province_name": pattern,
            "era": "pre_reform",
            "legal_document_id": {"$exists": False},
            "district_name": {"$ne": None},
        },
    )
    return sorted(n for n in names if n)


async def list_old_wards(db: AsyncIOMotorDatabase, province_name: str, district_name: str) -> list[dict]:
    """Danh sách xã/phường cũ của 1 quận/huyện — để đổ vào dropdown bước 3 (chiều old_to_new).

    Nguồn chính là administrative_boundaries (era=pre_reform, sạch). Bổ sung thêm các
    xã/phường KHÔNG có bản ghi boundary nào (bị TÁCH hết, không còn polygon riêng —
    VD Kim Phú ở Tuyên Quang) từ administrative_units, chỉ lấy mã nào chưa từng xuất
    hiện ở administrative_boundaries (tránh trùng mã do lỗi dữ liệu giữa 2 kỳ cũ/mới).
    """
    province = await _resolve_province(db, province_name)
    province_pattern = _name_pattern(province["name"])
    district = await _resolve_one(db, 2, "quận/huyện", district_name, parent_code=province["code"])
    district_pattern = _name_pattern(_strip_admin_prefix(district_name))

    boundary_wards = await db[BOUNDARIES].find(
        {
            "province_name": province_pattern,
            "district_name": district_pattern,
            "era": "pre_reform",
            "legal_document_id": {"$exists": False},
        },
        {"geometry": 0},
    ).to_list(length=500)
    result = [
        {"code": b["unit_code"], "name": b["unit_name"], "name_with_type": b.get("unit_name_with_type")}
        for b in boundary_wards
    ]
    seen_codes = {b["unit_code"] for b in boundary_wards}

    unit_wards = await db[UNITS].find({"level": 3, "parent_code": district["code"]}).to_list(length=500)
    candidate_codes = [u["code"] for u in unit_wards if u["code"] not in seen_codes]
    codes_with_boundary = set(
        await db[BOUNDARIES].distinct("unit_code", {"unit_code": {"$in": candidate_codes}})
    )
    for u in unit_wards:
        if u["code"] in seen_codes or u["code"] in codes_with_boundary:
            continue
        result.append({"code": u["code"], "name": u["name"], "name_with_type": u.get("name_with_type")})
        seen_codes.add(u["code"])

    result.sort(key=lambda x: x["name"])
    return result


async def list_new_wards(db: AsyncIOMotorDatabase, province_name: str) -> list[dict]:
    """Danh sách xã/phường mới (sau sáp nhập) của 1 tỉnh — để đổ vào dropdown bước 2 (chiều new_to_old)."""
    province = await _resolve_province(db, province_name)
    pattern = _name_pattern(province["name"])
    docs = await db[BOUNDARIES].find(
        {"province_name": pattern, "era": "post_reform"},
        {"geometry": 0},
    ).to_list(length=500)
    result = [
        {"code": d["unit_code"], "name": d["unit_name"], "name_with_type": d.get("unit_name_with_type")}
        for d in docs
    ]
    result.sort(key=lambda x: x["name"])
    return result


async def convert_address_by_name(db: AsyncIOMotorDatabase, payload: AddressConvertByNameRequest) -> dict:
    province = await _resolve_province(db, payload.province_name)

    if payload.ward_name:
        if payload.direction == "old_to_new":
            result = await _convert_ward_old_to_new(db, province, payload.district_name, payload.ward_name)
        else:
            result = await _convert_ward_new_to_old(db, province, payload.ward_name)
    elif payload.district_name:
        district = await _resolve_one(
            db, 2, "quận/huyện", payload.district_name, parent_code=province["code"], parent_label=f" trong '{province['name']}'"
        )
        code = district["code"]
        if district.get("status") == "active":
            result = {
                "match_type": "exact",
                "matched_unit": serialize_doc(district),
                "mapped_units": serialize_docs([district]),
                "resolved": True,
                "note": "Đơn vị vẫn còn hiệu lực, không có thay đổi.",
            }
        else:
            mapped_units = await _district_merge_candidates(
                db, _name_pattern(province["name"]), _name_pattern(district["name"])
            )
            await _attach_legal_documents(db, mapped_units)
            result = {
                "match_type": "district_candidates",
                "matched_unit": serialize_doc(district),
                "mapped_units": serialize_docs(mapped_units),
                "resolved": len(mapped_units) > 0,
                "note": (
                    f"Quận/huyện '{district['name']}' (mã {code}) đã bị giải thể sau sáp nhập, không có đơn vị "
                    f"kế thừa trực tiếp. Đây là danh sách {len(mapped_units)} xã/phường mới hình thành từ các "
                    "xã/phường cũ từng thuộc quận/huyện này (administrative_boundaries.merged_into_code)."
                    if mapped_units
                    else (
                        f"Quận/huyện '{district['name']}' (mã {code}) đã bị giải thể sau sáp nhập và không có "
                        "dữ liệu sáp nhập xã/phường nào cho quận/huyện này."
                    )
                ),
            }
    else:
        result = {
            "match_type": "exact",
            "matched_unit": serialize_doc(province),
            "mapped_units": serialize_docs([province]),
            "resolved": True,
            "note": "Đơn vị vẫn còn hiệu lực, không có thay đổi.",
        }

    return {
        "input": {
            "province_name": payload.province_name,
            "district_name": payload.district_name,
            "ward_name": payload.ward_name,
        },
        "direction": payload.direction,
        **result,
    }

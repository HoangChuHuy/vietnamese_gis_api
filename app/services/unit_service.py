import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.collections import AUDIT_LOGS, UNITS
from app.schemas.unit import RestructureRequest, UnitBulkCreate, UnitCreate
from app.utils.pagination import Pagination
from app.utils.serialization import serialize_doc, serialize_docs


def _build_unit_filter(
    level: Optional[int] = None,
    type_: Optional[str] = None,
    status: Optional[str] = None,
    parent_code: Optional[str] = None,
    q: Optional[str] = None,
) -> dict:
    query: dict = {}
    if level is not None:
        query["level"] = level
    if type_ is not None:
        query["type"] = type_
    if status is not None:
        query["status"] = status
    if parent_code is not None:
        query["parent_code"] = parent_code
    if q:
        pattern = re.compile(re.escape(q), re.IGNORECASE)
        query["$or"] = [
            {"name": pattern},
            {"name_with_type": pattern},
            {"slug": pattern},
        ]
    return query


async def list_units(
    db: AsyncIOMotorDatabase,
    pagination: Pagination,
    level: Optional[int] = None,
    type_: Optional[str] = None,
    status: Optional[str] = None,
    parent_code: Optional[str] = None,
    q: Optional[str] = None,
) -> tuple[list[dict], int]:
    query = _build_unit_filter(level, type_, status, parent_code, q)
    collection = db[UNITS]
    total = await collection.count_documents(query)
    cursor = (
        collection.find(query)
        .sort("code", 1)
        .skip(pagination.skip)
        .limit(pagination.limit)
    )
    docs = await cursor.to_list(length=pagination.limit)
    return serialize_docs(docs), total


async def get_unit_by_code(db: AsyncIOMotorDatabase, code: str) -> dict:
    doc = await db[UNITS].find_one({"code": code})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn vị hành chính với code={code}")
    return serialize_doc(doc)


async def get_children(
    db: AsyncIOMotorDatabase, code: str, pagination: Pagination, status: Optional[str] = None
) -> tuple[list[dict], int]:
    query: dict = {"parent_code": code}
    if status is not None:
        query["status"] = status
    collection = db[UNITS]
    total = await collection.count_documents(query)
    cursor = (
        collection.find(query)
        .sort("code", 1)
        .skip(pagination.skip)
        .limit(pagination.limit)
    )
    docs = await cursor.to_list(length=pagination.limit)
    return serialize_docs(docs), total


async def search_units(db: AsyncIOMotorDatabase, q: str, pagination: Pagination) -> tuple[list[dict], int]:
    return await list_units(db, pagination, q=q)


async def create_unit(db: AsyncIOMotorDatabase, payload: UnitCreate) -> dict:
    collection = db[UNITS]
    if await collection.find_one({"code": payload.code}):
        raise HTTPException(status_code=409, detail=f"code={payload.code} đã tồn tại")

    doc = payload.model_dump()
    now = datetime.now(timezone.utc)
    doc["created_at"] = now
    doc["updated_at"] = now
    result = await collection.insert_one(doc)
    created = await collection.find_one({"_id": result.inserted_id})
    return serialize_doc(created)


async def bulk_create_units(db: AsyncIOMotorDatabase, payload: UnitBulkCreate) -> dict:
    collection = db[UNITS]
    codes = [u.code for u in payload.units]

    existing_docs = await collection.find({"code": {"$in": codes}}, {"code": 1}).to_list(length=len(codes))
    existing_codes = {d["code"] for d in existing_docs}

    now = datetime.now(timezone.utc)
    to_insert = []
    skipped = []
    seen = set()
    for unit in payload.units:
        if unit.code in existing_codes or unit.code in seen:
            skipped.append(unit.code)
            continue
        seen.add(unit.code)
        doc = unit.model_dump()
        doc["created_at"] = now
        doc["updated_at"] = now
        to_insert.append(doc)

    inserted_count = 0
    if to_insert:
        result = await collection.insert_many(to_insert)
        inserted_count = len(result.inserted_ids)

    return {
        "requested": len(payload.units),
        "inserted": inserted_count,
        "skipped": skipped,
        "skipped_reason": "code đã tồn tại hoặc trùng lặp trong request"
        if skipped
        else None,
    }


async def restructure_unit(db: AsyncIOMotorDatabase, code: str, payload: RestructureRequest) -> dict:
    units = db[UNITS]
    audit_logs = db[AUDIT_LOGS]

    unit = await units.find_one({"code": code})
    if not unit:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đơn vị hành chính với code={code}")

    effective_date = payload.effective_date or datetime.now(timezone.utc)
    before_state = serialize_doc(unit)
    after_state: Optional[dict] = None

    if payload.action == "rename":
        if not payload.new_name:
            raise HTTPException(status_code=422, detail="new_name là bắt buộc khi action=rename")
        update = {"name": payload.new_name, "updated_at": datetime.now(timezone.utc)}
        await units.update_one({"_id": unit["_id"]}, {"$set": update})
        after_state = {**before_state, **{k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in update.items()}}

    elif payload.action in ("merge", "split", "dissolve"):
        if payload.action != "dissolve" and not payload.target_codes:
            raise HTTPException(
                status_code=422, detail="target_codes là bắt buộc khi action=merge hoặc split"
            )
        await units.update_one(
            {"_id": unit["_id"]},
            {"$set": {"status": "inactive", "updated_at": datetime.now(timezone.utc)}},
        )
        after_state = {"target_codes": payload.target_codes} if payload.target_codes else None

    await audit_logs.insert_one(
        {
            "entity_type": "unit",
            "action": payload.action,
            "valid_from": effective_date,
            "valid_to": None,
            "system_from": datetime.now(timezone.utc),
            "system_to": None,
            "created_by": "api",
            "legal_document_id": payload.legal_document_id,
            "before_state": {**before_state, "code": before_state.get("code")},
            "after_state": after_state,
            "change_summary": payload.reason
            or f"Unit '{unit.get('name')}' ({code}): {payload.action}",
        }
    )

    updated = await units.find_one({"_id": unit["_id"]})
    return serialize_doc(updated)

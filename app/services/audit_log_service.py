from datetime import datetime
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.collections import AUDIT_LOGS
from app.utils.pagination import Pagination
from app.utils.serialization import serialize_docs


async def list_audit_logs(
    db: AsyncIOMotorDatabase,
    pagination: Pagination,
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> tuple[list[dict], int]:
    query: dict = {}
    if entity_type is not None:
        query["entity_type"] = entity_type
    if action is not None:
        query["action"] = action
    if date_from or date_to:
        date_range: dict = {}
        if date_from:
            date_range["$gte"] = date_from
        if date_to:
            date_range["$lte"] = date_to
        query["valid_from"] = date_range

    collection = db[AUDIT_LOGS]
    total = await collection.count_documents(query)
    cursor = (
        collection.find(query)
        .sort("valid_from", -1)
        .skip(pagination.skip)
        .limit(pagination.limit)
    )
    docs = await cursor.to_list(length=pagination.limit)
    return serialize_docs(docs), total


async def get_unit_history(
    db: AsyncIOMotorDatabase, code: str, pagination: Pagination
) -> tuple[list[dict], int]:
    query = {
        "$or": [
            {"before_state.code": code},
            {"after_state.code": code},
        ]
    }
    collection = db[AUDIT_LOGS]
    total = await collection.count_documents(query)
    cursor = (
        collection.find(query)
        .sort("valid_from", -1)
        .skip(pagination.skip)
        .limit(pagination.limit)
    )
    docs = await cursor.to_list(length=pagination.limit)
    return serialize_docs(docs), total

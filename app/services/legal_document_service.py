from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.collections import LEGAL_DOCUMENTS, UNITS
from app.schemas.legal_document import LegalDocumentCreate
from app.utils.pagination import Pagination
from app.utils.serialization import serialize_doc, serialize_docs


def _parse_object_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except InvalidId:
        raise HTTPException(status_code=422, detail=f"id không hợp lệ: {id_str}")


async def list_legal_documents(
    db: AsyncIOMotorDatabase,
    pagination: Pagination,
    province_code: Optional[str] = None,
    doc_type: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> tuple[list[dict], int]:
    query: dict = {}
    if province_code is not None:
        query["scope.province_code"] = province_code
    if doc_type is not None:
        query["doc_type"] = doc_type
    if date_from or date_to:
        date_range: dict = {}
        if date_from:
            date_range["$gte"] = date_from
        if date_to:
            date_range["$lte"] = date_to
        query["effective_date"] = date_range

    collection = db[LEGAL_DOCUMENTS]
    total = await collection.count_documents(query)
    cursor = (
        collection.find(query)
        .sort("effective_date", -1)
        .skip(pagination.skip)
        .limit(pagination.limit)
    )
    docs = await cursor.to_list(length=pagination.limit)
    return serialize_docs(docs), total


async def get_legal_document(db: AsyncIOMotorDatabase, doc_id: str) -> dict:
    doc = await db[LEGAL_DOCUMENTS].find_one({"_id": _parse_object_id(doc_id)})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy văn bản pháp lý id={doc_id}")
    return serialize_doc(doc)


async def get_units_affected_by_document(
    db: AsyncIOMotorDatabase, doc_id: str, pagination: Pagination
) -> tuple[list[dict], int]:
    _parse_object_id(doc_id)  # validate format
    query = {"legal_document_id": doc_id}
    collection = db[UNITS]
    total = await collection.count_documents(query)
    cursor = collection.find(query).skip(pagination.skip).limit(pagination.limit)
    docs = await cursor.to_list(length=pagination.limit)
    return serialize_docs(docs), total


async def create_legal_document(db: AsyncIOMotorDatabase, payload: LegalDocumentCreate) -> dict:
    collection = db[LEGAL_DOCUMENTS]
    if await collection.find_one({"doc_number": payload.doc_number}):
        raise HTTPException(status_code=409, detail=f"doc_number={payload.doc_number} đã tồn tại")

    doc = payload.model_dump()
    doc["created_at"] = datetime.now(timezone.utc)
    result = await collection.insert_one(doc)
    created = await collection.find_one({"_id": result.inserted_id})
    return serialize_doc(created)

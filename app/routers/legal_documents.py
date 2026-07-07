from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.schemas.legal_document import LegalDocumentCreate
from app.services import legal_document_service
from app.utils.pagination import Pagination, paginated_response, pagination_params

router = APIRouter(prefix="/legal-documents", tags=["legal-documents"])


@router.get("")
async def list_legal_documents(
    province_code: Optional[str] = Query(None),
    doc_type: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    pagination: Pagination = Depends(pagination_params),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    items, total = await legal_document_service.list_legal_documents(
        db, pagination, province_code=province_code, doc_type=doc_type, date_from=date_from, date_to=date_to
    )
    return paginated_response(items, total, pagination)


@router.get("/{doc_id}")
async def get_legal_document(doc_id: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    return await legal_document_service.get_legal_document(db, doc_id)


@router.get("/{doc_id}/units")
async def get_units_affected(
    doc_id: str,
    pagination: Pagination = Depends(pagination_params),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    items, total = await legal_document_service.get_units_affected_by_document(db, doc_id, pagination)
    return paginated_response(items, total, pagination)


@router.post("", status_code=201)
async def create_legal_document(
    payload: LegalDocumentCreate, db: AsyncIOMotorDatabase = Depends(get_database)
):
    return await legal_document_service.create_legal_document(db, payload)

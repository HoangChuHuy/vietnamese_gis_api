from typing import Optional

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.schemas.unit import RestructureRequest, UnitBulkCreate, UnitCreate
from app.services import audit_log_service, unit_service
from app.utils.pagination import Pagination, paginated_response, pagination_params

router = APIRouter(prefix="/units", tags=["units"])


@router.get("")
async def list_units(
    level: Optional[int] = Query(None, ge=1, le=3),
    type: Optional[str] = Query(None, alias="type"),
    status: Optional[str] = Query(None),
    parent_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Tìm theo tên/slug"),
    pagination: Pagination = Depends(pagination_params),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    items, total = await unit_service.list_units(
        db, pagination, level=level, type_=type, status=status, parent_code=parent_code, q=q
    )
    return paginated_response(items, total, pagination)


@router.get("/search")
async def search_units(
    q: str = Query(..., min_length=1),
    pagination: Pagination = Depends(pagination_params),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    items, total = await unit_service.search_units(db, q, pagination)
    return paginated_response(items, total, pagination)


@router.get("/{code}")
async def get_unit(code: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    return await unit_service.get_unit_by_code(db, code)


@router.get("/{code}/children")
async def get_unit_children(
    code: str,
    status: Optional[str] = Query(None),
    pagination: Pagination = Depends(pagination_params),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    items, total = await unit_service.get_children(db, code, pagination, status=status)
    return paginated_response(items, total, pagination)


@router.get("/{code}/history")
async def get_unit_history(
    code: str,
    pagination: Pagination = Depends(pagination_params),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    items, total = await audit_log_service.get_unit_history(db, code, pagination)
    return paginated_response(items, total, pagination)


@router.post("", status_code=201)
async def create_unit(payload: UnitCreate, db: AsyncIOMotorDatabase = Depends(get_database)):
    return await unit_service.create_unit(db, payload)


@router.post("/bulk", status_code=201)
async def bulk_create_units(payload: UnitBulkCreate, db: AsyncIOMotorDatabase = Depends(get_database)):
    return await unit_service.bulk_create_units(db, payload)


@router.post("/{code}/restructure")
async def restructure_unit(
    code: str, payload: RestructureRequest, db: AsyncIOMotorDatabase = Depends(get_database)
):
    return await unit_service.restructure_unit(db, code, payload)

from typing import Optional

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.schemas.boundary import BoundaryBulkCreate, BoundaryCreate, IntersectRequest
from app.services import boundary_service
from app.utils.pagination import Pagination, pagination_params

router = APIRouter(prefix="/boundaries", tags=["boundaries"])


@router.get("")
async def list_boundaries(
    province_code: Optional[str] = Query(None),
    level: Optional[int] = Query(None, ge=1, le=3),
    era: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    pagination: Pagination = Depends(pagination_params),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await boundary_service.list_boundaries(
        db, pagination, province_code=province_code, level=level, era=era, status=status
    )


@router.get("/{unit_code}")
async def get_boundary(
    unit_code: str,
    era: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await boundary_service.get_boundary_by_unit_code(db, unit_code, era=era)


@router.post("", status_code=201)
async def create_boundary(payload: BoundaryCreate, db: AsyncIOMotorDatabase = Depends(get_database)):
    return await boundary_service.create_boundary(db, payload)


@router.post("/bulk", status_code=201)
async def bulk_create_boundaries(
    payload: BoundaryBulkCreate, db: AsyncIOMotorDatabase = Depends(get_database)
):
    return await boundary_service.bulk_create_boundaries(db, payload)


@router.post("/intersect")
async def intersect_boundaries(
    payload: IntersectRequest, db: AsyncIOMotorDatabase = Depends(get_database)
):
    return await boundary_service.intersect_boundaries(db, payload)

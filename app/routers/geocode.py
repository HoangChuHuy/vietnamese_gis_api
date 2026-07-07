from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.schemas.geocode import ReverseGeocodeBatchRequest
from app.services import boundary_service, geocode_service

router = APIRouter(prefix="/geocode", tags=["geocode"])


@router.get("/reverse")
async def reverse_geocode(
    lng: float = Query(..., ge=-180, le=180),
    lat: float = Query(..., ge=-90, le=90),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    feature = await boundary_service.reverse_geocode(db, lng, lat)
    if feature is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn vị hành chính chứa điểm này")
    return feature


@router.post("/reverse/batch")
async def reverse_geocode_batch(
    payload: ReverseGeocodeBatchRequest, db: AsyncIOMotorDatabase = Depends(get_database)
):
    return await geocode_service.reverse_geocode_batch(db, payload)

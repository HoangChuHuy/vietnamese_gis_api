from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.schemas.address import AddressConvertByNameRequest, AddressConvertRequest
from app.services import address_service

router = APIRouter(prefix="/address", tags=["address"])


@router.post("/convert")
async def convert_address(payload: AddressConvertRequest, db: AsyncIOMotorDatabase = Depends(get_database)):
    return await address_service.convert_address(db, payload)


@router.post("/convert-by-name")
async def convert_address_by_name(
    payload: AddressConvertByNameRequest, db: AsyncIOMotorDatabase = Depends(get_database)
):
    return await address_service.convert_address_by_name(db, payload)


@router.get("/old-districts")
async def get_old_districts(
    province_name: str = Query(..., min_length=1), db: AsyncIOMotorDatabase = Depends(get_database)
):
    return await address_service.list_old_districts(db, province_name)


@router.get("/old-wards")
async def get_old_wards(
    province_name: str = Query(..., min_length=1),
    district_name: str = Query(..., min_length=1),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await address_service.list_old_wards(db, province_name, district_name)


@router.get("/new-wards")
async def get_new_wards(
    province_name: str = Query(..., min_length=1), db: AsyncIOMotorDatabase = Depends(get_database)
):
    return await address_service.list_new_wards(db, province_name)

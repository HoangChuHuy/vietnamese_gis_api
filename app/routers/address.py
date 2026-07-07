from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.schemas.address import AddressConvertRequest
from app.services import address_service

router = APIRouter(prefix="/address", tags=["address"])


@router.post("/convert")
async def convert_address(payload: AddressConvertRequest, db: AsyncIOMotorDatabase = Depends(get_database)):
    return await address_service.convert_address(db, payload)

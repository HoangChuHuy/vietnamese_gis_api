from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.geocode import ReverseGeocodeBatchRequest
from app.services.boundary_service import reverse_geocode


async def reverse_geocode_batch(db: AsyncIOMotorDatabase, payload: ReverseGeocodeBatchRequest) -> list[dict]:
    results = []
    for point in payload.points:
        feature = await reverse_geocode(db, point.lng, point.lat)
        results.append(
            {
                "lng": point.lng,
                "lat": point.lat,
                "found": feature is not None,
                "feature": feature,
            }
        )
    return results

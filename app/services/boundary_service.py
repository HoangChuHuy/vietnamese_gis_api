from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.collections import BOUNDARIES
from app.schemas.boundary import BoundaryBulkCreate, BoundaryCreate, IntersectRequest
from app.utils.geometry import fix_self_intersection, validate_geojson_geometry
from app.utils.pagination import Pagination
from app.utils.serialization import serialize_doc, serialize_docs


def _to_feature(doc: dict) -> dict:
    doc = serialize_doc(doc)
    geometry = doc.pop("geometry", None)
    return {"type": "Feature", "geometry": geometry, "properties": doc}


def _prepare_geometry(geometry: dict, auto_fix: bool) -> tuple[Optional[dict], Optional[str]]:
    """Trả về (geometry_hop_le, None) hoặc (None, error_message)."""
    is_valid, error = validate_geojson_geometry(geometry)
    if is_valid:
        return geometry, None
    if not auto_fix:
        return None, error
    return fix_self_intersection(geometry), None


async def get_boundary_by_unit_code(
    db: AsyncIOMotorDatabase, unit_code: str, era: Optional[str] = None
) -> dict:
    query: dict = {"unit_code": unit_code}
    if era is not None:
        query["era"] = era
    collection = db[BOUNDARIES]
    doc = await collection.find_one(query, sort=[("recorded_at", -1)])
    if not doc:
        raise HTTPException(
            status_code=404, detail=f"Không tìm thấy ranh giới cho unit_code={unit_code}"
        )
    return _to_feature(doc)


async def list_boundaries(
    db: AsyncIOMotorDatabase,
    pagination: Pagination,
    province_code: Optional[str] = None,
    level: Optional[int] = None,
    era: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    query: dict = {}
    if province_code is not None:
        query["province_code"] = province_code
    if level is not None:
        query["level"] = level
    if era is not None:
        query["era"] = era
    if status is not None:
        query["status"] = status

    collection = db[BOUNDARIES]
    total = await collection.count_documents(query)
    cursor = collection.find(query).skip(pagination.skip).limit(pagination.limit)
    docs = await cursor.to_list(length=pagination.limit)
    features = [_to_feature(doc) for doc in docs]
    return {
        "type": "FeatureCollection",
        "features": features,
        "page": pagination.page,
        "limit": pagination.limit,
        "total": total,
    }


async def create_boundary(db: AsyncIOMotorDatabase, payload: BoundaryCreate) -> dict:
    geometry, error = _prepare_geometry(payload.geometry.model_dump(), payload.auto_fix)
    if error:
        raise HTTPException(
            status_code=422,
            detail=f"Geometry không hợp lệ (topology): {error}. "
            "Gửi lại với auto_fix=true để tự sửa bằng buffer(0), hoặc sửa geometry thủ công.",
        )

    doc = payload.model_dump(exclude={"geometry", "auto_fix"})
    doc["geometry"] = geometry
    doc["recorded_at"] = datetime.now(timezone.utc)

    collection = db[BOUNDARIES]
    result = await collection.insert_one(doc)
    created = await collection.find_one({"_id": result.inserted_id})
    return _to_feature(created)


async def bulk_create_boundaries(db: AsyncIOMotorDatabase, payload: BoundaryBulkCreate) -> dict:
    now = datetime.now(timezone.utc)
    to_insert = []
    failed = []

    for index, item in enumerate(payload.boundaries):
        geometry, error = _prepare_geometry(item.geometry.model_dump(), item.auto_fix)
        if error:
            failed.append({"index": index, "unit_code": item.unit_code, "error": error})
            continue
        doc = item.model_dump(exclude={"geometry", "auto_fix"})
        doc["geometry"] = geometry
        doc["recorded_at"] = now
        to_insert.append(doc)

    inserted_count = 0
    if to_insert:
        result = await db[BOUNDARIES].insert_many(to_insert)
        inserted_count = len(result.inserted_ids)

    return {
        "requested": len(payload.boundaries),
        "inserted": inserted_count,
        "failed": failed,
    }


async def intersect_boundaries(db: AsyncIOMotorDatabase, payload: IntersectRequest) -> dict:
    query: dict = {
        "geometry": {
            "$geoIntersects": {"$geometry": payload.geometry.model_dump()}
        }
    }
    if payload.province_code is not None:
        query["province_code"] = payload.province_code
    if payload.level is not None:
        query["level"] = payload.level
    if payload.status is not None:
        query["status"] = payload.status

    docs = await db[BOUNDARIES].find(query).to_list(length=1000)
    return {
        "type": "FeatureCollection",
        "features": [_to_feature(doc) for doc in docs],
        "total": len(docs),
    }


async def reverse_geocode(db: AsyncIOMotorDatabase, lng: float, lat: float) -> Optional[dict]:
    collection = db[BOUNDARIES]
    doc = await collection.find_one(
        {
            "geometry": {
                "$geoIntersects": {
                    "$geometry": {"type": "Point", "coordinates": [lng, lat]}
                }
            },
            "status": "active",
        }
    )
    if not doc:
        return None
    return _to_feature(doc)

from pydantic import BaseModel, Field


class GeoPoint(BaseModel):
    lng: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)


class ReverseGeocodeBatchRequest(BaseModel):
    points: list[GeoPoint] = Field(..., min_length=1, max_length=500)

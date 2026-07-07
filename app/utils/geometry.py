from shapely.geometry import shape, mapping
from shapely.validation import explain_validity


def validate_geojson_geometry(geometry: dict) -> tuple[bool, str | None]:
    """Kiểm tra geometry (Polygon/MultiPolygon) có hợp lệ về topology không.

    Dùng shapely (bindings của GEOS, cùng họ thuật toán với PostGIS ST_IsValid)
    để bắt các lỗi tự cắt (self-intersection) trước khi ghi vào MongoDB —
    tránh lặp lại sự cố "Can't extract geo keys" khi build 2dsphere index.
    """
    try:
        geom = shape(geometry)
    except Exception as exc:  # geometry malformed structurally
        return False, f"GeoJSON không hợp lệ: {exc}"

    if not geom.is_valid:
        return False, explain_validity(geom)

    return True, None


def fix_self_intersection(geometry: dict) -> dict:
    """Sửa polygon tự cắt bằng kỹ thuật buffer(0) chuẩn GIS (tương đương ST_Buffer(geom,0))."""
    geom = shape(geometry)
    fixed = geom.buffer(0)
    return mapping(fixed)

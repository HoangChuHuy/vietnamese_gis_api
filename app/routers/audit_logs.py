from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.services import audit_log_service
from app.utils.pagination import Pagination, paginated_response, pagination_params

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("")
async def list_audit_logs(
    entity_type: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    pagination: Pagination = Depends(pagination_params),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    items, total = await audit_log_service.list_audit_logs(
        db, pagination, entity_type=entity_type, action=action, date_from=date_from, date_to=date_to
    )
    return paginated_response(items, total, pagination)

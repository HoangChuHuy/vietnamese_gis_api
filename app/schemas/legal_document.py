from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LegalDocumentScope(BaseModel):
    level: Optional[str] = None
    province_code: Optional[str] = None
    province_name: Optional[str] = None


class LegalDocumentCreate(BaseModel):
    doc_number: str
    number: Optional[str] = None
    serial: Optional[str] = None
    doc_type: str
    issuing_body_code: Optional[str] = None
    issuing_body: str
    issue_date: datetime
    effective_date: datetime
    title: str
    scope: Optional[LegalDocumentScope] = None
    units_affected: Optional[int] = None
    raw_reference: Optional[str] = None

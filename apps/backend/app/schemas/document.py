from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DocumentBase(BaseModel):
    original_filename: str
    mime_type: Optional[str] = None
    file_size: Optional[int] = None


class DocumentResponse(DocumentBase):
    id: int
    organization_id: int
    matter_id: int
    uploaded_by_user_id: int
    storage_path: Optional[str] = None
    file_hash: Optional[str] = None
    status: str
    extracted_text: Optional[str] = None
    page_count: Optional[int] = None
    detected_document_type: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

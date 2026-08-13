from datetime import datetime

from pydantic import BaseModel


class DocumentBase(BaseModel):
    original_filename: str
    mime_type: str | None = None
    file_size: int | None = None


class DocumentResponse(DocumentBase):
    id: int
    organization_id: int
    matter_id: int
    uploaded_by_user_id: int
    storage_path: str | None = None
    file_hash: str | None = None
    status: str
    extracted_text: str | None = None
    page_count: int | None = None
    detected_document_type: str | None = None
    created_at: datetime
    processed_at: datetime | None = None

    class Config:
        from_attributes = True

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def get_client_ip(request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def record_audit_log(
    db: Session,
    organization_id: int | None,
    user_id: int | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict | None = None
):
    audit_log = AuditLog(
        organization_id=organization_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        ip_address=ip_address,
        user_agent=user_agent,
        # `extra` is the Python attribute; the DB column is `metadata` (JSONB).
        # We pass the dict directly so SQLAlchemy serialises it as JSONB
        # rather than coercing a string into a JSONB column.
        extra=metadata,
    )
    db.add(audit_log)
    db.commit()
    return audit_log


class AuditLogger:
    def __init__(self, db: Session, user_id: int | None = None, organization_id: int | None = None):
        self.db = db
        self.user_id = user_id
        self.organization_id = organization_id

    def log(self, action: str, entity_type: str = None, entity_id: int = None, ip_address: str = None, user_agent: str = None, metadata: dict = None):
        record_audit_log(
            db=self.db,
            organization_id=self.organization_id,
            user_id=self.user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata
        )

    def log_login(self, ip_address: str = None, user_agent: str = None):
        self.log("login", metadata={"timestamp": datetime.utcnow().isoformat()}, ip_address=ip_address, user_agent=user_agent)

    def log_logout(self, ip_address: str = None, user_agent: str = None):
        self.log("logout", metadata={"timestamp": datetime.utcnow().isoformat()}, ip_address=ip_address, user_agent=user_agent)

    def log_document_upload(self, document_id: int, matter_id: int, filename: str, ip_address: str = None):
        self.log("document_upload", "document", document_id, ip_address, metadata={"matter_id": matter_id, "filename": filename})

    def log_document_view(self, document_id: int, ip_address: str = None):
        self.log("document_view", "document", document_id, ip_address)

    def log_document_delete(self, document_id: int, ip_address: str = None):
        self.log("document_delete", "document", document_id, ip_address)

    def log_analysis_generate(self, report_id: int, matter_id: int, ip_address: str = None):
        self.log("analysis_generate", "analysis_report", report_id, ip_address, metadata={"matter_id": matter_id})

    def log_report_view(self, report_id: int, ip_address: str = None):
        self.log("report_view", "analysis_report", report_id, ip_address)

    def log_report_export(self, report_id: int, ip_address: str = None):
        self.log("report_export", "analysis_report", report_id, ip_address)

    def log_matter_create(self, matter_id: int, matter_title: str, ip_address: str = None):
        self.log("matter_create", "matter", matter_id, ip_address, metadata={"title": matter_title})

    def log_matter_status_change(self, matter_id: int, old_status: str, new_status: str, ip_address: str = None):
        self.log("matter_status_change", "matter", matter_id, ip_address, metadata={"old_status": old_status, "new_status": new_status})

    def log_user_invite(self, invited_user_id: int, role: str, ip_address: str = None):
        self.log("user_invite", "user", invited_user_id, ip_address, metadata={"role": role})

    def log_role_change(self, target_user_id: int, old_role: str, new_role: str, ip_address: str = None):
        self.log("role_change", "user", target_user_id, ip_address, metadata={"old_role": old_role, "new_role": new_role})

    # S3-03: trace every chat turn so legal/forensic audits can reconstruct
    # exactly who asked what and when. We deliberately store a SHA-256
    # prefix of the content rather than the full text to keep audit rows
    # small — the full text remains in the chat_messages table.
    def log_chat_message(
        self,
        session_id: int,
        message_id: int,
        role: str,
        content_preview: str,
        ip_address: str = None,
    ):
        import hashlib
        digest = hashlib.sha256((content_preview or "").encode("utf-8")).hexdigest()
        self.log(
            "chat_message",
            "chat_session",
            session_id,
            ip_address,
            metadata={
                "message_id": message_id,
                "role": role,
                "content_sha256": digest,
                "content_length": len(content_preview or ""),
            },
        )

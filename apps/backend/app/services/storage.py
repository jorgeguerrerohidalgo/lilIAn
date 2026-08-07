import os
import uuid
import hashlib
import logging
from typing import Optional, Tuple
from abc import ABC, abstractmethod
from enum import Enum

logger = logging.getLogger(__name__)

STORAGE_ROOT = os.path.realpath(os.environ.get("STORAGE_PATH", "/app/storage/documents"))


def _safe_join(relative_path: str) -> Optional[str]:
    """Resolve ``relative_path`` against STORAGE_ROOT and ensure the result stays
    inside the storage sandbox. Returns ``None`` if the path would escape.
    """
    if not relative_path or os.path.isabs(relative_path):
        return None
    candidate = os.path.realpath(os.path.join(STORAGE_ROOT, relative_path))
    if candidate != STORAGE_ROOT and not candidate.startswith(STORAGE_ROOT + os.sep):
        return None
    return candidate


class StorageBackend(str, Enum):
    LOCAL = "local"
    SUPABASE = "supabase"


class StorageService(ABC):
    """Interface abstracta para storage."""

    @abstractmethod
    def save_file(self, content: bytes, original_filename: str, organization_id: int, matter_id: int) -> Tuple[str, str, int]:
        """Guarda archivo y retorna (relative_path, file_hash, size)"""
        pass

    @abstractmethod
    def get_file_path(self, relative_path: str) -> Optional[str]:
        """Retorna path local del archivo o None si no existe"""
        pass

    @abstractmethod
    def delete_file(self, relative_path: str) -> bool:
        """Elimina archivo, retorna True si éxito"""
        pass

    @abstractmethod
    def get_file_content(self, relative_path: str) -> Optional[bytes]:
        """Retorna contenido del archivo o None"""
        pass


# =============================================================================
# Implementación LOCAL (filesystem)
# =============================================================================

STORAGE_PATH = STORAGE_ROOT


class LocalStorage(StorageService):
    """Storage local usando filesystem."""

    def save_file(self, content: bytes, original_filename: str, organization_id: int, matter_id: int) -> Tuple[str, str, int]:
        os.makedirs(STORAGE_PATH, exist_ok=True)

        file_hash = hashlib.sha256(content).hexdigest()
        ext = os.path.splitext(original_filename)[1].lower()
        unique_filename = f"{uuid.uuid4()}{ext}"

        org_dir = os.path.join(STORAGE_PATH, str(organization_id))
        os.makedirs(org_dir, exist_ok=True)

        matter_dir = os.path.join(org_dir, str(matter_id))
        os.makedirs(matter_dir, exist_ok=True)

        file_path = os.path.join(matter_dir, unique_filename)

        with open(file_path, "wb") as f:
            f.write(content)

        relative_path = f"{organization_id}/{matter_id}/{unique_filename}"
        return relative_path, file_hash, len(content)

    def get_file_path(self, relative_path: str) -> Optional[str]:
        full_path = _safe_join(relative_path)
        if full_path and os.path.exists(full_path):
            return full_path
        return None

    def delete_file(self, relative_path: str) -> bool:
        full_path = _safe_join(relative_path)
        if full_path and os.path.exists(full_path):
            os.remove(full_path)
            return True
        return False

    def get_file_content(self, relative_path: str) -> Optional[bytes]:
        full_path = _safe_join(relative_path)
        if full_path and os.path.exists(full_path):
            with open(full_path, "rb") as f:
                return f.read()
        return None


# =============================================================================
# Implementación SUPABASE STORAGE
# =============================================================================

class SupabaseStorage(StorageService):
    """Storage usando Supabase."""

    def __init__(self):
        from supabase import create_client
        from app.core.config import settings

        self.bucket_name = os.environ.get("SUPABASE_STORAGE_BUCKET", "documents")
        self.client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY
        )

    def _get_storage_path(self, organization_id: int, matter_id: int, filename: str) -> str:
        return f"{organization_id}/{matter_id}/{filename}"

    def save_file(self, content: bytes, original_filename: str, organization_id: int, matter_id: int) -> Tuple[str, str, int]:
        file_hash = hashlib.sha256(content).hexdigest()
        ext = os.path.splitext(original_filename)[1].lower()
        unique_filename = f"{uuid.uuid4()}{ext}"

        storage_path = self._get_storage_path(organization_id, matter_id, unique_filename)

        self.client.storage.from_(self.bucket_name).upload(
            path=storage_path,
            file=content,
            file_options={"content-type": self._get_mime_type(original_filename)}
        )

        return storage_path, file_hash, len(content)

    def get_file_path(self, relative_path: str) -> Optional[str]:
        """Para Supabase, retorna URL签署 del archivo."""
        try:
            url = self.client.storage.from_(self.bucket_name).create_signed_url(
                relative_path,
                3600  # 1 hora
            )
            return url if url else None
        except Exception:
            return None

    def delete_file(self, relative_path: str) -> bool:
        try:
            self.client.storage.from_(self.bucket_name).remove(relative_path)
            return True
        except Exception:
            return False

    def get_file_content(self, relative_path: str) -> Optional[bytes]:
        try:
            response = self.client.storage.from_(self.bucket_name).download(relative_path)
            return response
        except Exception:
            return None

    def _get_mime_type(self, filename: str) -> str:
        ext = os.path.splitext(filename)[1].lower()
        mime_types = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".doc": "application/msword",
            ".txt": "text/plain",
        }
        return mime_types.get(ext, "application/octet-stream")


# =============================================================================
# Factory: obtener implementación según configuración
# =============================================================================

def get_storage_backend() -> StorageBackend:
    return StorageBackend(os.environ.get("STORAGE_BACKEND", "local"))


def get_storage() -> StorageService:
    backend = get_storage_backend()
    if backend == StorageBackend.SUPABASE:
        return SupabaseStorage()
    return LocalStorage()


# =============================================================================
# Funciones legacy para backward compatibility
# =============================================================================

def save_file(content: bytes, original_filename: str, organization_id: int, matter_id: int) -> Tuple[str, str, int]:
    return get_storage().save_file(content, original_filename, organization_id, matter_id)


def get_file_path(relative_path: str) -> Optional[str]:
    return get_storage().get_file_path(relative_path)


def delete_file(relative_path: str) -> bool:
    return get_storage().delete_file(relative_path)


def get_file_content(relative_path: str) -> Optional[bytes]:
    return get_storage().get_file_content(relative_path)

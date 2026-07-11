import os
import uuid
import hashlib
from typing import Optional, Tuple

STORAGE_PATH = "/app/storage/documents"


def ensure_storage_dir():
    os.makedirs(STORAGE_PATH, exist_ok=True)


def save_file(content: bytes, original_filename: str, organization_id: int, matter_id: int) -> Tuple[str, str, int]:
    ensure_storage_dir()

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


def get_file_path(relative_path: str) -> Optional[str]:
    full_path = os.path.join(STORAGE_PATH, relative_path)
    if os.path.exists(full_path):
        return full_path
    return None


def delete_file(relative_path: str) -> bool:
    full_path = os.path.join(STORAGE_PATH, relative_path)
    if os.path.exists(full_path):
        os.remove(full_path)
        return True
    return False


def get_file_content(relative_path: str) -> Optional[bytes]:
    full_path = os.path.join(STORAGE_PATH, relative_path)
    if os.path.exists(full_path):
        with open(full_path, "rb") as f:
            return f.read()
    return None

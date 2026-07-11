from typing import Optional
import fitz
from docx import Document as DocxDocument


def extract_text_from_file(file_path: str, mime_type: Optional[str]) -> str:
    if not file_path or not mime_type:
        return ""

    try:
        if mime_type == "application/pdf":
            return extract_text_from_pdf(file_path)
        elif mime_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"]:
            return extract_text_from_docx(file_path)
        elif mime_type == "text/plain":
            return extract_text_from_txt(file_path)
        else:
            return ""
    except Exception as e:
        return f"Error extracting text: {str(e)}"


def extract_text_from_pdf(file_path: str) -> str:
    text_parts = []
    try:
        doc = fitz.open(file_path)
        for page_num, page in enumerate(doc):
            text_parts.append(page.get_text())
        doc.close()
    except Exception:
        return ""
    return "\n\n".join(text_parts)


def extract_text_from_docx(file_path: str) -> str:
    try:
        doc = DocxDocument(file_path)
        return "\n\n".join([para.text for para in doc.paragraphs])
    except Exception:
        return ""


def extract_text_from_txt(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        try:
            with open(file_path, "r", encoding="latin-1") as f:
                return f.read()
        except Exception:
            return ""

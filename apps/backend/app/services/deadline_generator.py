"""
Deadline Generator Service

Extracts deadline alerts from contract_timeline and creates DeadlineAlert records.
"""
import json
from datetime import date, datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.deadline_alert import DeadlineAlert
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.models.matter import Matter


# Urgency classification based on days remaining
URGENCY_RULES = {
    "prescripcion": {"critical": 7, "high": 30, "medium": 90},
    "vencimiento": {"critical": 7, "high": 30, "medium": 90},
    "aviso_previo": {"high": 7, "medium": 30, "low": 90},
    "renovacion": {"high": 7, "medium": 30, "low": 90},
    "pago": {"high": 7, "medium": 30, "low": 90},
    "garantia": {"medium": 7, "low": 30, "low": 90},
    "firma": {"high": 7, "medium": 14, "low": 30},
    "plazo_sin_penalidad": {"medium": 7, "low": 30, "low": 60},
}

DEFAULT_URGENCY = {"critical": 7, "high": 30, "medium": 90, "low": 180}


def classify_urgency(event_type: str, days_remaining: int) -> str:
    """Classify urgency based on event type and days remaining."""
    rules = URGENCY_RULES.get(event_type, DEFAULT_URGENCY)

    if days_remaining <= rules.get("critical", 7):
        return "critical"
    elif days_remaining <= rules.get("high", 30):
        return "high"
    elif days_remaining <= rules.get("medium", 90):
        return "medium"
    return "low"


def calculate_importance_score(urgency: str, days_remaining: int) -> int:
    """Calculate importance score 0-100 based on urgency and time."""
    base_scores = {"critical": 90, "high": 70, "medium": 50, "low": 30}

    base = base_scores.get(urgency, 50)

    # Increase score if very urgent (few days left)
    if urgency == "critical" and days_remaining <= 3:
        base = 100
    elif urgency == "high" and days_remaining <= 5:
        base = min(100, base + 10)

    return base


def parse_timeline_item(item: dict) -> Optional[dict]:
    """Parse a single timeline item and extract alert data.

    Handles both naming conventions from the LLM output.
    """
    # LLM output uses: event, date, days_from_signing, type, description, consequence, legal_reference
    # Legacy format used: evento, fecha_contrato, plazo_dias, fecha_limite, etc.
    evento = (item.get("event") or item.get("evento") or "").strip()
    date_str = item.get("date") or item.get("fecha_contrato") or item.get("fecha_limite")
    plazo_dias = item.get("days_from_signing") or item.get("plazo_dias")
    consecuencia = item.get("consequence") or item.get("consecuencia") or ""
    articulo = item.get("legal_reference") or item.get("articulo_legal") or ""

    # Use type from LLM directly if available and valid
    llm_type = (item.get("type") or item.get("event_type") or "").lower()
    valid_types = ["firma", "inicio", "vencimiento", "aviso_previo", "renovacion", "prescripcion", "pago", "garantia", "plazo_sin_penalidad", "aviso"]
    event_type = llm_type if llm_type in valid_types else None

    # If no valid type from LLM, detect from event text
    evento_lower = evento.lower()
    if not event_type:
        if any(word in evento_lower for word in ["vencimient", "vencer", "tmino", "expira"]):
            event_type = "vencimiento"
        elif any(word in evento_lower for word in ["prescripci", "prescribir"]):
            event_type = "prescripcion"
        elif any(word in evento_lower for word in ["aviso", "notificaci", "comunicaci"]):
            event_type = "aviso_previo"
        elif any(word in evento_lower for word in ["renovaci", "renovar"]):
            event_type = "renovacion"
        elif any(word in evento_lower for word in ["pago", "cancelaci", "abono"]):
            event_type = "pago"
        elif any(word in evento_lower for word in ["garant", "aval"]):
            event_type = "garantia"
        elif any(word in evento_lower for word in ["firma", "suscribir"]):
            event_type = "firma"
        elif any(word in evento_lower for word in ["plazo", "limite", "sin penalidad", "sin penalización", "duraci"]):
            event_type = "plazo_sin_penalidad"
        else:
            event_type = "pago"

    # Parse date - try multiple formats
    due_date = None
    days_remaining = None

    if date_str:
        # Try ISO format first
        try:
            due_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

        if not due_date:
            # Try Spanish date format "10 de julio de 2026"
            try:
                import re
                match = re.match(r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})', date_str)
                if match:
                    day, month_name, year = match.groups()
                    months = {
                        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
                        'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
                        'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
                    }
                    month = months.get(month_name.lower(), 1)
                    due_date = date(int(year), month, int(day))
            except Exception:
                pass

        if not due_date:
            # Try DD/MM/YYYY
            try:
                due_date = datetime.strptime(date_str, "%d/%m/%Y").date()
            except ValueError:
                pass

    # If we have days_from_signing but no due_date, estimate from today
    if not due_date and plazo_dias and int(plazo_dias) > 0:
        due_date = date.today() + timedelta(days=int(plazo_dias))

    # If we still don't have a due_date, use today for immediate items or estimate
    if not due_date:
        if event_type in ["firma", "inicio"]:
            # These should have dates - skip if no date found
            return None
        # For others, use a placeholder date (today + some days based on type)
        due_date = date.today() + timedelta(days=30)

    days_remaining = (due_date - date.today()).days

    urgency = classify_urgency(event_type, days_remaining or 0)
    importance = calculate_importance_score(urgency, days_remaining or 0)

    return {
        "title": evento if evento else f"Alerta de {event_type}",
        "description": consecuencia if consecuencia and consecuencia != "Ninguna." else None,
        "event_type": event_type,
        "due_date": due_date,
        "days_remaining": days_remaining,
        "is_overdue": days_remaining < 0 if days_remaining else False,
        "urgency": urgency,
        "importance_score": importance,
        "source_event": evento,
        "legal_reference": articulo if articulo else None,
        "consequence": consecuencia if consecuencia else None,
    }


def generate_alerts_from_document(document_id: int) -> List[int]:
    """Generate deadline alerts from a document's contract_timeline.

    Returns list of created alert IDs.
    """
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return []

        analysis = db.query(DocumentAnalysis).filter(
            DocumentAnalysis.document_id == document_id
        ).first()

        if not analysis or not analysis.contract_timeline:
            return []

        # Parse contract_timeline JSON
        try:
            timeline = json.loads(analysis.contract_timeline)
        except (json.JSONDecodeError, TypeError):
            return []

        if not isinstance(timeline, list):
            return []

        created_ids = []

        for item in timeline:
            alert_data = parse_timeline_item(item)
            if not alert_data:
                continue

            # Check for duplicate
            existing = db.query(DeadlineAlert).filter(
                DeadlineAlert.document_id == document_id,
                DeadlineAlert.source_event == alert_data["source_event"],
                DeadlineAlert.status != "dismissed"
            ).first()

            if existing:
                continue

            alert = DeadlineAlert(
                organization_id=doc.organization_id,
                matter_id=doc.matter_id,
                document_id=document_id,
                title=alert_data["title"],
                description=alert_data.get("description"),
                event_type=alert_data["event_type"],
                due_date=alert_data["due_date"],
                days_remaining=alert_data["days_remaining"],
                is_overdue=alert_data["is_overdue"],
                urgency=alert_data["urgency"],
                importance_score=alert_data["importance_score"],
                source_event=alert_data.get("source_event"),
                legal_reference=alert_data.get("legal_reference"),
                consequence=alert_data.get("consequence"),
            )
            db.add(alert)
            created_ids.append(alert)

        if created_ids:
            db.commit()
            return [a.id for a in created_ids]

        return []

    finally:
        db.close()


def update_overdue_status(matter_id: int, organization_id: int) -> int:
    """Update is_overdue flag for all alerts in a matter.

    Returns number of alerts updated.
    """
    db = SessionLocal()
    try:
        today = date.today()
        alerts = db.query(DeadlineAlert).filter(
            DeadlineAlert.matter_id == matter_id,
            DeadlineAlert.organization_id == organization_id,
            DeadlineAlert.status.in_(["pending", "acknowledged"])
        ).all()

        count = 0
        for alert in alerts:
            if alert.due_date < today and not alert.is_overdue:
                alert.is_overdue = True
                count += 1
            elif alert.due_date >= today and alert.is_overdue:
                alert.is_overdue = False
                count += 1

            # Update days_remaining
            alert.days_remaining = (alert.due_date - today).days

        if count > 0:
            db.commit()

        return count

    finally:
        db.close()

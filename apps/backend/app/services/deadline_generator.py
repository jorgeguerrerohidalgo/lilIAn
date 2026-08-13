"""
Deadline Generator Service

Extracts deadline alerts from contract_timeline and creates DeadlineAlert records.
"""
import json
from datetime import date, datetime, timedelta

from app.core.database import SessionLocal
from app.models.deadline_alert import DeadlineAlert
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis

# Urgency classification based on days remaining
URGENCY_RULES = {
    "prescripcion": {"critical": 7, "high": 30, "medium": 90},
    "vencimiento": {"critical": 7, "high": 30, "medium": 90},
    "aviso_previo": {"high": 7, "medium": 30, "low": 90},
    "renovacion": {"high": 7, "medium": 30, "low": 90},
    "pago": {"high": 7, "medium": 30, "low": 90},
    "garantia": {"medium": 7, "low": 30, "high": 90},
    "firma": {"high": 7, "medium": 14, "low": 30},
    "plazo_sin_penalidad": {"medium": 7, "low": 30, "high": 60},
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


def parse_timeline_item(item: dict) -> dict | None:
    """Parse a single timeline item and extract alert data.

    Handles both naming conventions from the LLM output.

    S4-09: previously this 109-line function inlined four concerns —
    field extraction, event-type inference, date parsing, and fallback
    resolution. Each concern is now extracted into its own helper so
    the top-level reads as a pipeline of intent.
    """
    fields = _extract_event_fields(item)
    event_type = _infer_event_type(fields["evento"], fields["llm_type"])
    due_date = _parse_due_date(fields["date_str"], fields["plazo_dias"])

    # If we have days_from_signing but no due_date, estimate from today.
    if due_date is None and fields["plazo_dias"] and int(fields["plazo_dias"]) > 0:
        due_date = date.today() + timedelta(days=int(fields["plazo_dias"]))

    # If we still don't have a due_date, use a placeholder based on type.
    if due_date is None:
        if event_type in ("firma", "inicio"):
            return None
        due_date = date.today() + timedelta(days=30)

    days_remaining = (due_date - date.today()).days
    urgency = classify_urgency(event_type, days_remaining or 0)
    importance = calculate_importance_score(urgency, days_remaining or 0)

    return {
        "title": fields["evento"] if fields["evento"] else f"Alerta de {event_type}",
        "description": (
            fields["consecuencia"]
            if fields["consecuencia"] and fields["consecuencia"] != "Ninguna."
            else None
        ),
        "event_type": event_type,
        "due_date": due_date,
        "days_remaining": days_remaining,
        "is_overdue": days_remaining < 0 if days_remaining else False,
        "urgency": urgency,
        "importance_score": importance,
        "source_event": fields["evento"],
        "legal_reference": fields["articulo"] if fields["articulo"] else None,
        "consequence": fields["consecuencia"] if fields["consecuencia"] else None,
    }


_VALID_EVENT_TYPES = (
    "firma",
    "inicio",
    "vencimiento",
    "aviso_previo",
    "renovacion",
    "prescripcion",
    "pago",
    "garantia",
    "plazo_sin_penalidad",
    "aviso",
)

# Substrings (in order) that imply an event type when the LLM did not
# give us a valid one. Order matters — the longest/most specific match
# appears first.
_TYPE_HEURISTICS = (
    ("vencimiento", ("vencimient", "vencer", "tmino", "expira")),
    ("prescripcion", ("prescripci", "prescribir")),
    ("aviso_previo", ("aviso", "notificaci", "comunicaci")),
    ("renovacion", ("renovaci", "renovar")),
    ("pago", ("pago", "cancelaci", "abono")),
    ("garantia", ("garant", "aval")),
    ("firma", ("firma", "suscribir")),
    ("plazo_sin_penalidad", ("plazo", "limite", "sin penalidad", "sin penalización", "duraci")),
)


def _extract_event_fields(item: dict) -> dict[str, object]:
    """Normalize both naming conventions (LLM + legacy) into a uniform dict.

    The legacy format used Spanish keys (evento, fecha_contrato, etc.)
    while the current LLM output uses English. We accept either.
    """
    return {
        "evento": (item.get("event") or item.get("evento") or "").strip(),
        "date_str": (
            item.get("date")
            or item.get("fecha_contrato")
            or item.get("fecha_limite")
        ),
        "plazo_dias": item.get("days_from_signing") or item.get("plazo_dias"),
        "consecuencia": item.get("consequence") or item.get("consecuencia") or "",
        "articulo": item.get("legal_reference") or item.get("articulo_legal") or "",
        "llm_type": (item.get("type") or item.get("event_type") or "").lower(),
    }


def _infer_event_type(evento: str, llm_type: str) -> str:
    """Prefer a valid LLM-provided type; otherwise infer from event text.

    Defaults to ``pago`` when nothing matches (legacy behavior).
    """
    if llm_type in _VALID_EVENT_TYPES:
        return llm_type
    evento_lower = evento.lower()
    for type_name, substrings in _TYPE_HEURISTICS:
        if any(word in evento_lower for word in substrings):
            return type_name
    return "pago"


def _parse_due_date(date_str: object, plazo_dias: object) -> object | None:
    """Try several common date formats; return None when no input is parseable.

    Tries in order: ISO (YYYY-MM-DD), Spanish ("10 de julio de 2026"),
    DD/MM/YYYY. Each parser is independent — failures are silent.
    """
    if not date_str or not isinstance(date_str, str):
        return None
    if due_date := _try_iso_date(date_str):
        return due_date
    if due_date := _try_spanish_date(date_str):
        return due_date
    if due_date := _try_dmy_date(date_str):
        return due_date
    return None


def _try_iso_date(date_str: str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


_SPANISH_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def _try_spanish_date(date_str: str):
    match = re.match(
        r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})",
        date_str,
    )
    if not match:
        return None
    day, month_name, year = match.groups()
    month = _SPANISH_MONTHS.get(month_name.lower(), 1)
    try:
        return date(int(year), month, int(day))
    except ValueError:
        return None


def _try_dmy_date(date_str: str):
    try:
        return datetime.strptime(date_str, "%d/%m/%Y").date()
    except ValueError:
        return None

def generate_alerts_from_document(document_id: int) -> list[int]:
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

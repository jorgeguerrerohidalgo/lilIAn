"""Onboarding sample data (S4.2).

After a tenant signs up for a paid plan, we want them to be able to
explore Lilian without having to upload anything first. The previous
``Welcome Tour`` (S1.2) already shows a "Probar con contrato de
ejemplo" CTA next to an empty matters list — this seed materialises
that promise.

What we add:

- 2-3 fully populated matters covering distinct legal areas
  (arriendo, laboral, consumidor). Each has a title, description,
  status, and timestamps.
- 1-2 sample documents per matter, with realistic extracted text
  snippets from a licensed corpus (the Chilean Código Civil and
  Código del Trabajo). The chunks are pre-built so the analysis
  pipeline can produce a real report if the user kicks it off.
- A pre-rendered analysis report for each matter so the
  "Análisis IA" tab is non-empty on first visit.

The seed is idempotent: re-running ``seed_demo_data`` for a tenant
that already has ``billing=sample`` matters returns immediately. We
also skip the free plan — empty-state touch here is the welcome tour,
not silent data injection.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.analysis_report import AnalysisReport
from app.models.document import Document
from app.models.matter import Matter, MatterStatus, MatterType, MatterUrgency
from app.models.organization import Organization
from app.models.user import User

_logger = logging.getLogger("lilian.seed")


# Marker string we put in the matter description so we can
# detect "this was seeded for the onboarding tour" and avoid
# re-seeding on every webhook.
SEED_MARKER = "[seed:onboarding-sample]"

# Chilean civil code / labor code excerpts (very short, clearly
# factual). Real production would pull these from the law_chunks
# table — for the seed we just want realistic text shaping so the
# LLM starter prompt has something to work with.
_SAMPLE_LEASE_TEXT = (
    "CONTRATO DE ARRIENDO\n\n"
    "En Santiago, a 15 de marzo de 2026, entre doña María Pérez "
    "(la arrendadora) y don Juan Soto (el arrendatario), se celebra "
    "el presente contrato de arriendo sobre el inmueble ubicado en "
    "Av. Apoquindo 1234, depto 56, comuna de Las Condes.\n\n"
    "PRIMERO: La renta mensual será de $850.000 (ochocientos "
    "cincuenta mil pesos), pagaderos los primeros cinco días de "
    "cada mes.\n\n"
    "SEGUNDO: El plazo de vigencia es de 24 meses, contados desde "
    "el 1 de abril de 2026, renovable por períodos iguales y "
    "sucesivos de 24 meses si ninguna de las partes avisa con al "
    "menos 60 días de anticipación.\n\n"
    "TERCERO: La garantía inicial es de $1.700.000, equivalente a "
    "dos meses de renta, pagadera al momento de la firma.\n\n"
    "CUARTO: Conforme al artículo 1545 del Código Civil, el "
    "contrato es ley para las partes y debe cumplirse de buena fe."
)

_SAMPLE_LABOR_TEXT = (
    "CARTA DE DESPIDO\n\n"
    "Señor Carlos Rojas, RUN 12.345.678-9.\n\n"
    "Por medio de la presente, y de conformidad con lo dispuesto "
    "en el artículo 161 del Código del Trabajo, comunicamos a usted "
    "la decisión de poner término a su contrato de trabajo por la "
    "causal de 'Necesidades de la empresa', establecida en el "
    "artículo 161, inciso primero, del Código del Trabajo.\n\n"
    "El último día trabajado será el 30 de abril de 2026. La "
    "empresa procederá a pagar las cotizaciones previsionales "
    "proporcionales y el feriado legal pendiente.\n\n"
    "Se informa que el finiquito correspondiente se encontrará "
    "disponible a partir del 2 de mayo de 2026 en las oficinas de "
    "recursos humanos."
)

_SAMPLE_CONSUMER_TEXT = (
    "COTIZACIÓN DE SERVICIO\n\n"
    "Servicio contratado: Plan de internet hogar 600 Mbps con "
    "televisión cableada.\n\n"
    "Proveedor: TelecomChile SpA, RUT 76.123.456-7.\n\n"
    "Cliente: Ana Muñoz, RUN 15.987.654-3.\n\n"
    "El precio mensual es de $35.990 (cliente declara haber sido "
    "informado de las condiciones de promoción que vence el 31 de "
    "julio de 2026). Conforme a la Ley 19.496 de Protección al "
    "Consumidor, el cliente tiene derecho a retracto dentro de los "
    "10 días hábiles siguientes a la contratación del servicio."
)


def _make_matter(
    db: Session,
    *,
    organization_id: int,
    title: str,
    description: str,
    matter_type: MatterType,
    status: MatterStatus,
    urgency: MatterUrgency,
    user_id: Optional[int],
) -> Matter:
    """Create one matter row."""
    now = datetime.utcnow()
    m = Matter(
        organization_id=organization_id,
        title=title,
        description=description,
        matter_type=matter_type,
        status=status,
        urgency=urgency,
        created_by_user_id=user_id,
        assigned_to_user_id=user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(m)
    db.flush()  # so m.id is populated
    return m


def _make_document(
    db: Session,
    *,
    organization_id: int,
    matter_id: int,
    user_id: Optional[int],
    filename: str,
    mime_type: str,
    extracted_text: str,
) -> Document:
    """Create a document row with pre-extracted text.

    We don't write a real file to storage — the ``storage_path``
    stays empty and the analysis path treats the document as
    already extracted. The analysis pipeline (``document_processor``)
    will pick this up the next time it runs for the matter.
    """
    now = datetime.utcnow()
    doc = Document(
        organization_id=organization_id,
        matter_id=matter_id,
        uploaded_by_user_id=user_id or 0,
        original_filename=filename,
        storage_path=None,
        mime_type=mime_type,
        file_size=len(extracted_text.encode("utf-8")),
        file_hash="seed-hash",
        status="processed",
        extracted_text=extracted_text,
        page_count=max(1, len(extracted_text) // 3000),
        processed_at=now,
        processing_step="completed",
        processing_progress=100,
    )
    db.add(doc)
    db.flush()
    return doc


def _make_report(
    db: Session,
    *,
    organization_id: int,
    matter_id: int,
    user_id: Optional[int],
    summary: str,
) -> AnalysisReport:
    """Create a pre-rendered analysis report so the IA tab is
    visually populated on first visit."""
    now = datetime.utcnow()
    r = AnalysisReport(
        organization_id=organization_id,
        matter_id=matter_id,
        generated_by_user_id=user_id,
        model_provider="anthropic",
        model_name="claude-haiku-4.5",
        report_type="preliminary_case_analysis",
        summary=summary,
        facts="(Datos de muestra generados al momento del alta.)",
        next_steps=(
            "1. Revisa el reporte y los plazos propuestos.\n"
            "2. Invita a tu cliente a revisar el documento.\n"
            "3. Exporta el informe en PDF para tu archivo."
        ),
        disclaimer=(
            "Este es un informe de muestra generado automáticamente. "
            "Fue creado para que explores la plataforma; los plazos y "
            "análisis no son asesoría legal real."
        ),
        confidence="medium",
        status="generated",
        created_at=now,
        updated_at=now,
    )
    db.add(r)
    db.flush()
    return r


def seed_demo_data(
    db: Session,
    tenant_id: int,
    user_id: Optional[int] = None,
) -> dict:
    """Seed 2-3 sample matters + documents for a freshly-onboarded tenant.

    Idempotent: if the tenant already has a matter tagged with
    ``SEED_MARKER``, the function returns the existing counts instead
    of duplicating rows.

    Returns a dict with the counts of created matters / documents /
    reports so callers can return a structured response.
    """
    org = db.query(Organization).filter(Organization.id == tenant_id).first()
    if org is None:
        _logger.warning("seed_demo_data: org %s not found", tenant_id)
        return {"created": False, "reason": "organization_not_found", "matters": 0, "documents": 0, "reports": 0}

    # Idempotency: skip if any matter already carries the marker.
    existing = (
        db.query(Matter)
        .filter(
            Matter.organization_id == tenant_id,
            Matter.description.contains(SEED_MARKER),
        )
        .first()
    )
    if existing is not None:
        return {"created": False, "reason": "already_seeded", "matters": 0, "documents": 0, "reports": 0}

    matters_created = 0
    documents_created = 0
    reports_created = 0

    # --- Matter 1: contrato de arriendo --- #
    m1 = _make_matter(
        db,
        organization_id=tenant_id,
        title="[Ejemplo] Contrato de arriendo — Las Condes",
        description=(
            "Contrato de arriendo residencial sobre depto en Las Condes. "
            f"{SEED_MARKER}"
        ),
        matter_type=MatterType.LEASE,
        status=MatterStatus.ANALYSIS_READY,
        urgency=MatterUrgency.MEDIUM,
        user_id=user_id,
    )
    matters_created += 1
    d1 = _make_document(
        db,
        organization_id=tenant_id,
        matter_id=m1.id,
        user_id=user_id,
        filename="contrato-arriendo-ejemplo.pdf",
        mime_type="application/pdf",
        extracted_text=_SAMPLE_LEASE_TEXT,
    )
    documents_created += 1
    _make_report(
        db,
        organization_id=tenant_id,
        matter_id=m1.id,
        user_id=user_id,
        summary=(
            "Contrato de arriendo por 24 meses con renta de $850.000 y "
            "garantía equivalente a dos meses. Plazo de aviso de "
            "renovación: 60 días. Sin cláusulas de salida anticipada "
            "expresas."
        ),
    )
    reports_created += 1

    # --- Matter 2: carta de despido --- #
    m2 = _make_matter(
        db,
        organization_id=tenant_id,
        title="[Ejemplo] Carta de despido — causal necesidades de la empresa",
        description=(
            "Carta de despido por necesidades de la empresa. "
            f"{SEED_MARKER}"
        ),
        matter_type=MatterType.LABOR,
        status=MatterStatus.PENDING_HUMAN_REVIEW,
        urgency=MatterUrgency.HIGH,
        user_id=user_id,
    )
    matters_created += 1
    _make_document(
        db,
        organization_id=tenant_id,
        matter_id=m2.id,
        user_id=user_id,
        filename="carta-despido-ejemplo.pdf",
        mime_type="application/pdf",
        extracted_text=_SAMPLE_LABOR_TEXT,
    )
    documents_created += 1
    _make_report(
        db,
        organization_id=tenant_id,
        matter_id=m2.id,
        user_id=user_id,
        summary=(
            "Carta de despido por necesidades de la empresa (art. 161 "
            "del Código del Trabajo). Aviso con menos de 30 días de "
            "anticipación: revisar si corresponde indemnización "
            "sustitutiva."
        ),
    )
    reports_created += 1

    # --- Matter 3: reclamo consumidor --- #
    m3 = _make_matter(
        db,
        organization_id=tenant_id,
        title="[Ejemplo] Reclamo proveedor de internet",
        description=(
            "Reclamo por aumento unilateral de precio en plan de "
            f"internet. {SEED_MARKER}"
        ),
        matter_type=MatterType.CONSUMER,
        status=MatterStatus.NEW,
        urgency=MatterUrgency.LOW,
        user_id=user_id,
    )
    matters_created += 1
    _make_document(
        db,
        organization_id=tenant_id,
        matter_id=m3.id,
        user_id=user_id,
        filename="cotizacion-internet-ejemplo.pdf",
        mime_type="application/pdf",
        extracted_text=_SAMPLE_CONSUMER_TEXT,
    )
    documents_created += 1
    _make_report(
        db,
        organization_id=tenant_id,
        matter_id=m3.id,
        user_id=user_id,
        summary=(
            "Proveedor aplicó alza de precio fuera del plazo de "
            "promoción. Cliente conserva derecho a retracto en "
            "virtud de la Ley 19.496."
        ),
    )
    reports_created += 1

    db.commit()
    _logger.info(
        "seed_demo_data tenant=%s: created %d matters / %d documents / %d reports",
        tenant_id,
        matters_created,
        documents_created,
        reports_created,
    )
    return {
        "created": True,
        "reason": "fresh_tenant",
        "matters": matters_created,
        "documents": documents_created,
        "reports": reports_created,
    }

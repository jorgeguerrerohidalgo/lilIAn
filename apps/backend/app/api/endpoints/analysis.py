
import logging as _logging
import threading
from contextlib import suppress

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user, require_organization
from app.core.database import SessionLocal, get_db
from app.core.plan_limits import enforce_analysis_limit
from app.models.analysis_report import AnalysisReport
from app.models.matter import Matter
from app.models.organization_member import OrganizationMember
from app.models.risk_item import RiskItem
from app.models.user import User
from app.schemas.analysis import (
    AnalysisReportDetailResponse,
    AnalysisReportResponse,
    GenerateAnalysisRequest,
    RiskItemResponse,
)

router = APIRouter(prefix="/analysis", tags=["analysis"])

_logger = _logging.getLogger("lilian.analysis")

# Per-matter in-process lock so two concurrent POSTs for the same case do
# not race each other and corrupt the matter's status / DB rows.
_analysis_locks: dict[int, threading.Lock] = {}
_analysis_locks_guard = threading.Lock()


def _get_analysis_lock(matter_id: int) -> threading.Lock:
    with _analysis_locks_guard:
        lock = _analysis_locks.get(matter_id)
        if lock is None:
            lock = threading.Lock()
            _analysis_locks[matter_id] = lock
        return lock


def run_analysis_task(matter_id: int, organization_id: int, user_id: int):
    """Background-task entry point.

    Wraps the real orchestrator with a per-matter lock and a hard
    top-level ``try/except`` so a crash inside the analysis pipeline
    never bubbles back into the FastAPI threadpool as an unhandled
    exception (which is what was poisoning subsequent requests).
    """
    lock = _get_analysis_lock(matter_id)
    if not lock.acquire(blocking=False):
        _logger.warning(
            "analysis for matter %s already running, skipping duplicate dispatch",
            matter_id,
        )
        return
    try:
        from app.services.analysis import generate_analysis_for_matter
        try:
            generate_analysis_for_matter(matter_id, organization_id, user_id)
        except Exception:
            # Belt-and-braces: generate_analysis_for_matter already
            # swallows + persists the failure, but if a future change
            # leaks an exception we still must NOT let it bubble.
            _logger.exception(
                "background analysis task leaked exception for matter %s",
                matter_id,
            )
            with suppress(Exception):
                from app.services.analysis import _set_matter_error_status
                _set_matter_error_status(
                    matter_id, "background task crashed"
                )
    finally:
        lock.release()


@router.post("", status_code=202)
def generate_analysis(
    analysis_request: GenerateAnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    # S2-03: plan-limit guard — 402 Payment Required when the org has hit
    # its analyses_limit. Runs after auth so unauthenticated requests
    # still get 401.
    membership: OrganizationMember = Depends(enforce_analysis_limit),
    db: Session = Depends(get_db)
):
    matter = db.query(Matter).filter(
        Matter.id == analysis_request.matter_id,
        Matter.organization_id == membership.organization_id
    ).first()

    if not matter:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    # Pre-flight checks surface common failures immediately so the user
    # does not have to wait for the background task to discover them.
    from app.models.document import Document
    doc_count = (
        db.query(Document)
        .filter(
            Document.matter_id == analysis_request.matter_id,
            Document.organization_id == membership.organization_id,
            Document.status.in_(["processed", "analyzed"]),
        )
        .count()
    )
    if doc_count == 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "No hay documentos procesados para analizar. Sube al menos "
                "un PDF/DOCX, espera a que se procese y vuelve a intentar."
            ),
        )

    background_tasks.add_task(
        run_analysis_task,
        analysis_request.matter_id,
        membership.organization_id,
        current_user.id
    )

    # S2-06: usage event for analytics + future usage-based billing.
    # The service swallows errors so a failed write never blocks the
    # 202 we are about to return to the user.
    from app.services.usage import EVENT_ANALYSIS_RUN, record_event

    record_event(
        organization_id=membership.organization_id,
        event_type=EVENT_ANALYSIS_RUN,
        quantity=1,
        user_id=current_user.id,
        metadata={
            "matter_id": analysis_request.matter_id,
            "documents_to_analyze": doc_count,
        },
    )

    return {
        "message": "Análisis iniciado en segundo plano",
        "matter_id": analysis_request.matter_id,
        "status": "processing",
        "documents_to_analyze": doc_count,
    }


@router.post("/stream")
async def generate_analysis_stream(
    analysis_request: GenerateAnalysisRequest,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
):
    """S3.4: streaming analysis endpoint.

    Returns a Server-Sent Events stream of the same structured analysis
    that ``POST /analysis`` would generate, but with the LLM response
    streamed token-by-token so the frontend can render the report
    progressively instead of waiting for the full call to finish.

    Wire format (text/event-stream):

        data: {"type":"start","matter_id":42}
        data: {"type":"delta","content":"..."}    # repeated as tokens arrive
        data: {"type":"done","report_id":123,"status":"analysis_ready"}

    The existing ``POST /analysis`` endpoint (background task) is left
    untouched — this is a parallel path for clients that want lower
    time-to-first-token. The full structured result is NOT persisted
    on the streaming path; callers should continue to use ``POST
    /analysis`` to write to the DB. ``POST /analysis/stream`` is best
    for live preview / interactive exploration.
    """
    import json

    from app.models.document import Document

    # Synchronous pre-flight: matter lookup + document count. Use a
    # short-lived session so the streaming generator does not hold a
    # long-lived ORM session.
    def preflight() -> tuple[int, str]:
        sync_db = SessionLocal()
        try:
            matter = (
                sync_db.query(Matter)
                .filter(
                    Matter.id == analysis_request.matter_id,
                    Matter.organization_id == membership.organization_id,
                )
                .first()
            )
            if not matter:
                raise HTTPException(status_code=404, detail="Caso no encontrado")

            doc_count = (
                sync_db.query(Document)
                .filter(
                    Document.matter_id == analysis_request.matter_id,
                    Document.organization_id == membership.organization_id,
                    Document.status.in_(["processed", "analyzed"]),
                )
                .count()
            )
            if doc_count == 0:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "No hay documentos procesados para analizar. "
                        "Sube al menos un PDF/DOCX, espera a que se "
                        "procese y vuelve a intentar."
                    ),
                )

            matter_type_value = (
                matter.matter_type.value
                if hasattr(matter.matter_type, "value")
                else matter.matter_type
            )
            return analysis_request.matter_id, matter_type_value
        finally:
            sync_db.close()

    try:
        matter_id, matter_type_value = await run_in_threadpool(preflight)
    except HTTPException:
        raise

    async def event_generator():
        from app.services.analysis import (
            analyze_contract,
            get_chunks_text_for_analysis,
        )
        from app.services.llm import get_llm_provider

        yield f"data: {json.dumps({'type': 'start', 'matter_id': matter_id})}\n\n"

        def prep() -> str:
            return get_chunks_text_for_analysis(
                matter_id, membership.organization_id
            )

        documents_text = await run_in_threadpool(prep)
        if not documents_text or len(documents_text.strip()) < 100:
            yield f"data: {json.dumps({'type': 'error', 'message': 'No hay texto suficiente para analizar'})}\n\n"
            return

        # Build the same prompt the blocking path would build. We do not
        # have streaming JSON-mode, so we stream the LLM's free-text
        # continuation after the ``{`` prefill and let the frontend
        # render it as it arrives.
        from app.services.analysis import (
            SECTION_TIMELINE_CITAS,
            get_system_prompt_for_matter_type,
        )

        def build_prompt() -> tuple[str, str]:
            system_prompt = get_system_prompt_for_matter_type(matter_type_value)
            system_prompt += SECTION_TIMELINE_CITAS

            prompt = (
                "Analiza el siguiente documento legal y proporciona un "
                "informe estructurado en JSON.\n\n"
                f"DOCUMENTO:\n{documents_text[:80000]}\n\n"
                "Responde SOLO con el JSON solicitado."
            )
            return system_prompt, prompt

        system_prompt, prompt = await run_in_threadpool(build_prompt)

        provider = get_llm_provider()
        full_content_parts: list[str] = []
        try:
            async for chunk in provider.generate_stream(
                prompt=prompt,
                system_prompt=system_prompt,
                task_complexity="complex",
                max_tokens=8192,
                temperature=0.3,
            ):
                if not chunk:
                    continue
                full_content_parts.append(chunk)
                yield f"data: {json.dumps({'type': 'delta', 'content': chunk})}\n\n"
        except Exception as exc:
            _logger.exception("streaming analysis failed: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
            return

        full_content = "".join(full_content_parts)
        yield f"data: {json.dumps({'type': 'done', 'status': 'analysis_ready', 'content': full_content})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/matters/{matter_id}", response_model=list[AnalysisReportResponse])
def list_matter_analyses(
    matter_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    matter = db.query(Matter).filter(
        Matter.id == matter_id,
        Matter.organization_id == membership.organization_id
    ).first()

    if not matter:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    reports = db.query(AnalysisReport).filter(
        AnalysisReport.matter_id == matter_id,
        AnalysisReport.organization_id == membership.organization_id
    ).order_by(AnalysisReport.created_at.desc()).all()

    return reports


@router.get("/reports/{report_id}", response_model=AnalysisReportDetailResponse)
def get_analysis_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    report = db.query(AnalysisReport).filter(
        AnalysisReport.id == report_id,
        AnalysisReport.organization_id == membership.organization_id
    ).first()

    if not report:
        raise HTTPException(status_code=404, detail="Informe no encontrado")

    risks = db.query(RiskItem).filter(
        RiskItem.analysis_report_id == report_id
    ).all()

    risk_responses = [RiskItemResponse.model_validate(r) for r in risks]

    response_data = AnalysisReportResponse.model_validate(report).model_dump()
    response_data["risks"] = risk_responses

    return AnalysisReportDetailResponse(**response_data)


@router.get("/matters/{matter_id}/status")
def get_matter_analysis_status(
    matter_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    """Lightweight status endpoint so the frontend can detect analysis
    failures without waiting for the polling to time out. Returns
    ``{status, error}`` where ``status`` is the matter's current
    lifecycle status and ``error`` carries the failure message when
    the last attempt set ``status = "failed"``.
    """
    matter = db.query(Matter).filter(
        Matter.id == matter_id,
        Matter.organization_id == membership.organization_id,
    ).first()
    if not matter:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    status = matter.status or "new"
    error_message = getattr(matter, "last_error", None) if status == "failed" else None
    return {
        "matter_id": matter_id,
        "status": status,
        "error": error_message,
        "updated_at": matter.updated_at.isoformat() if getattr(matter, "updated_at", None) else None,
    }


@router.get("/matters/{matter_id}/latest", response_model=AnalysisReportDetailResponse)
def get_latest_analysis(
    matter_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    # S3.5: read-through Redis cache. Cache key is scoped to the
    # matter + organization so a tenant cannot read another tenant's
    # cached analysis.
    from app.services.cache import get_cached, set_cached

    cache_key = f"analysis:matter:{membership.organization_id}:{matter_id}:latest"
    cached = get_cached(cache_key)
    if cached:
        return AnalysisReportDetailResponse(**cached)

    matter = db.query(Matter).filter(
        Matter.id == matter_id,
        Matter.organization_id == membership.organization_id
    ).first()

    if not matter:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    report = db.query(AnalysisReport).filter(
        AnalysisReport.matter_id == matter_id,
        AnalysisReport.organization_id == membership.organization_id
    ).order_by(AnalysisReport.created_at.desc()).first()

    if not report:
        raise HTTPException(status_code=404, detail="No existe análisis para este caso")

    risks = db.query(RiskItem).filter(
        RiskItem.analysis_report_id == report.id
    ).all()

    risk_responses = [RiskItemResponse.model_validate(r) for r in risks]

    response_data = AnalysisReportResponse.model_validate(report).model_dump()

    # Deserialize validation_summary from JSON if present
    if report.validation_summary:
        import json
        try:
            response_data["validation_summary"] = json.loads(report.validation_summary)
        except (ValueError, TypeError):
            response_data["validation_summary"] = None

    response_data["risks"] = risk_responses

    # S3.5: 1-hour TTL — long enough for a single work session of
    # re-opens, short enough that a freshly re-run analysis supersedes
    # the cached value the next day. When the cache is unreachable the
    # call below is a no-op (returns False) so the response still works.
    set_cached(cache_key, response_data, ttl=3600)

    return AnalysisReportDetailResponse(**response_data)


@router.get("/matters/{matter_id}/risks", response_model=list[RiskItemResponse])
def list_matter_risks(
    matter_id: int,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    matter = db.query(Matter).filter(
        Matter.id == matter_id,
        Matter.organization_id == membership.organization_id
    ).first()

    if not matter:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    risks = db.query(RiskItem).filter(
        RiskItem.matter_id == matter_id,
        RiskItem.organization_id == membership.organization_id
    ).order_by(
        RiskItem.level.desc(),
        RiskItem.created_at.desc()
    ).all()

    return risks


@router.patch("/risks/{risk_id}/review")
def update_risk_review_status(
    risk_id: int,
    review_status: str,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMember = Depends(require_organization),
    db: Session = Depends(get_db)
):
    if review_status not in ["pending", "reviewed", "accepted", "dismissed"]:
        raise HTTPException(status_code=400, detail="Estado de revisión no válido")

    risk = db.query(RiskItem).filter(
        RiskItem.id == risk_id,
        RiskItem.organization_id == membership.organization_id
    ).first()

    if not risk:
        raise HTTPException(status_code=404, detail="Riesgo no encontrado")

    risk.review_status = review_status
    db.commit()

    return {"message": "Estado actualizado", "risk_id": risk_id, "review_status": review_status}

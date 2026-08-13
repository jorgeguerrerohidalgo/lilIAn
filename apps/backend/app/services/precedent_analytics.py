"""
Precedent Analytics Service

Provides aggregated statistics and trends for precedents.
"""
from collections import Counter

from sqlalchemy import func

from app.core.database import SessionLocal
from app.models.precedent import Precedent

_TOP_LIMIT = 15
_TOP_VOCES = 20
_TOP_COURTS_HEATMAP = 8
_TEXT_ANALYSIS_SAMPLE = 500

_STOP_WORDS_ES = frozenset({
    "el", "la", "los", "las", "de", "del", "en", "y", "a", "que",
    "es", "por", "para", "con", "su", "una", "se", "no", "lo",
    "como", "más", "pero", "este", "esta", "estos", "estas",
})

_MIN_WORD_LENGTH = 4


def get_precedent_analytics(
    organization_id: int,
    legal_area: str | None = None,
    court: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    matter_type: str | None = None,
    include_text_analysis: bool = False
) -> dict:
    """Get aggregated analytics for precedents.

    S4-18: previously this 213-line function held nine numbered sections
    inline. Each section is now its own helper so the top-level reads as
    a list of intent, and individual sections are independently
    testable.
    """
    db = SessionLocal()
    try:
        base_query = _build_base_query(
            db, organization_id, legal_area, court, year_from, year_to, matter_type
        )

        volume_by_year = _volume_by_year(db, organization_id)
        volume_by_court = _volume_by_court(db, organization_id)
        volume_by_legal_area = _volume_by_legal_area(db, organization_id)
        top_voces = _top_voces(base_query)
        top_ponentes = _top_ponentes(db, organization_id)
        temporal_evolution = _temporal_evolution_by_legal_area(db, organization_id)
        court_matter_heatmap = _court_matter_heatmap(
            db, organization_id, [c["court"] for c in volume_by_court[:_TOP_COURTS_HEATMAP]]
        )
        summary = _summary_stats(db, organization_id, volume_by_court, volume_by_legal_area)
        text_analysis = (
            _text_analysis(base_query)
            if include_text_analysis
            else {}
        )

        return {
            "summary": summary,
            "volume_by_year": volume_by_year,
            "volume_by_court": volume_by_court,
            "volume_by_legal_area": volume_by_legal_area,
            "court_matter_heatmap": court_matter_heatmap,
            "top_voces": top_voces,
            "top_ponentes": top_ponentes,
            "temporal_evolution": temporal_evolution,
            "text_analysis": text_analysis,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# S4-18: per-section analytics helpers
# ---------------------------------------------------------------------------
def _build_base_query(
    db, organization_id: int, legal_area, court, year_from, year_to, matter_type
):
    """Build the precedents query applying each filter in turn."""
    query = db.query(Precedent).filter(Precedent.organization_id == organization_id)
    if legal_area:
        query = query.filter(Precedent.legal_area == legal_area)
    if court:
        query = query.filter(Precedent.court.ilike(f"%{court}%"))
    if year_from:
        query = query.filter(Precedent.year >= year_from)
    if year_to:
        query = query.filter(Precedent.year <= year_to)
    if matter_type:
        query = query.filter(Precedent.matter_type.ilike(f"%{matter_type}%"))
    return query


def _volume_by_year(db, organization_id: int) -> list[dict]:
    """Histogram of precedent counts grouped by year."""
    rows = (
        db.query(Precedent.year, func.count(Precedent.id))
        .filter(Precedent.organization_id == organization_id)
        .group_by(Precedent.year)
        .order_by(Precedent.year)
        .all()
    )
    return [{"year": year, "count": count} for year, count in rows]


def _volume_by_court(db, organization_id: int) -> list[dict]:
    """Top courts by precedent count, ordered descending."""
    rows = (
        db.query(Precedent.court, func.count(Precedent.id))
        .filter(Precedent.organization_id == organization_id)
        .group_by(Precedent.court)
        .order_by(func.count(Precedent.id).desc())
        .limit(_TOP_LIMIT)
        .all()
    )
    return [{"court": c, "count": count} for c, count in rows]


def _volume_by_legal_area(db, organization_id: int) -> list[dict]:
    """Per-legal-area totals, ordered descending."""
    rows = (
        db.query(Precedent.legal_area, func.count(Precedent.id))
        .filter(Precedent.organization_id == organization_id)
        .group_by(Precedent.legal_area)
        .order_by(func.count(Precedent.id).desc())
        .all()
    )
    return [{"legal_area": area, "count": count} for area, count in rows]


def _top_voces(base_query) -> list[dict]:
    """Count voice occurrences across precedents, top-N by frequency."""
    counter: Counter = Counter()
    for precedent in base_query.all():
        if precedent.voces:
            for voice in (v.strip() for v in precedent.voces.split(",")):
                counter[voice] += 1
    return [
        {"voice": voice, "count": count}
        for voice, count in counter.most_common(_TOP_VOCES)
    ]


def _top_ponentes(db, organization_id: int) -> list[dict]:
    """Top ponentes (judges) by precedent count."""
    rows = (
        db.query(Precedent.ponente, func.count(Precedent.id))
        .filter(
            Precedent.organization_id == organization_id,
            Precedent.ponente.isnot(None),
            Precedent.ponente != "",
        )
        .group_by(Precedent.ponente)
        .order_by(func.count(Precedent.id).desc())
        .limit(_TOP_LIMIT)
        .all()
    )
    return [{"ponente": p, "count": count} for p, count in rows if p]


def _temporal_evolution_by_legal_area(db, organization_id: int) -> dict[str, list[dict]]:
    """Per-area timelines of precedent counts by year."""
    rows = (
        db.query(
            Precedent.year, Precedent.legal_area, func.count(Precedent.id)
        )
        .filter(Precedent.organization_id == organization_id)
        .group_by(Precedent.year, Precedent.legal_area)
        .all()
    )
    evolution: dict[str, list[dict]] = {}
    for year, area, count in rows:
        evolution.setdefault(area, []).append({"year": year, "count": count})
    for area in evolution:
        evolution[area].sort(key=lambda x: x["year"])
    return evolution


def _court_matter_heatmap(
    db, organization_id: int, top_courts: list[str]
) -> list[dict]:
    """Precedent counts per (court, legal_area) pair across the top courts."""
    if not top_courts:
        return []
    rows = (
        db.query(
            Precedent.court, Precedent.legal_area, func.count(Precedent.id)
        )
        .filter(
            Precedent.organization_id == organization_id,
            Precedent.court.in_(top_courts),
        )
        .group_by(Precedent.court, Precedent.legal_area)
        .all()
    )
    return [
        {"court": c, "legal_area": area, "count": count}
        for c, area, count in rows
    ]


def _summary_stats(
    db, organization_id: int, volume_by_court: list[dict], volume_by_legal_area: list[dict]
) -> dict:
    """Aggregate totals + year range + diversity metrics."""
    total = (
        db.query(func.count(Precedent.id))
        .filter(Precedent.organization_id == organization_id)
        .scalar()
    )
    year_range = (
        db.query(func.min(Precedent.year), func.max(Precedent.year))
        .filter(Precedent.organization_id == organization_id)
        .first()
    )
    return {
        "total_precedents": total or 0,
        "year_range": {
            "min": year_range[0] if year_range else None,
            "max": year_range[1] if year_range else None,
        },
        "unique_courts": len(volume_by_court),
        "unique_areas": len(volume_by_legal_area),
    }


def _text_analysis(base_query) -> dict:
    """Optional word-frequency analysis over a sample of decisions."""
    precedents = base_query.all()[:_TEXT_ANALYSIS_SAMPLE]
    counter: Counter = Counter()
    for precedent in precedents:
        if not precedent.decision:
            continue
        words = precedent.decision.lower().split()
        counter.update(
            w for w in words
            if len(w) > _MIN_WORD_LENGTH and w not in _STOP_WORDS_ES
        )
    if not precedents:
        return {"top_keywords": []}
    denominator = len(precedents)
    top_keywords = [
        {
            "word": word,
            "frequency": count / denominator,
        }
        for word, count in counter.most_common(30)
    ]
    return {"top_keywords": top_keywords}

def get_available_filters(organization_id: int) -> dict:
    """Get available filter options based on existing data.

    Returns lists of unique courts, legal_areas, and year range.
    """
    db = SessionLocal()
    try:
        courts = db.query(Precedent.court).filter(
            Precedent.organization_id == organization_id,
            Precedent.court.isnot(None)
        ).distinct().all()

        legal_areas = db.query(Precedent.legal_area).filter(
            Precedent.organization_id == organization_id,
            Precedent.legal_area.isnot(None)
        ).distinct().all()

        years = db.query(
            func.min(Precedent.year),
            func.max(Precedent.year)
        ).filter(
            Precedent.organization_id == organization_id
        ).first()

        return {
            "courts": [c[0] for c in courts if c[0]],
            "legal_areas": [a[0] for a in legal_areas if a[0]],
            "year_range": {
                "min": years[0] if years else None,
                "max": years[1] if years else None
            }
        }
    finally:
        db.close()

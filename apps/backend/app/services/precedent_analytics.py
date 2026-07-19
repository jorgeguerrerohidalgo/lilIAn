"""
Precedent Analytics Service

Provides aggregated statistics and trends for precedents.
"""
from typing import List, Dict, Optional, Any
from collections import Counter
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.precedent import Precedent


def get_precedent_analytics(
    organization_id: int,
    legal_area: Optional[str] = None,
    court: Optional[str] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    matter_type: Optional[str] = None,
    include_text_analysis: bool = False
) -> dict:
    """Get aggregated analytics for precedents.

    Args:
        organization_id: Organization ID for data isolation
        legal_area: Filter by legal area
        court: Filter by court name
        year_from: Filter from year
        year_to: Filter to year
        matter_type: Filter by matter type
        include_text_analysis: Whether to include expensive text analysis

    Returns:
        dict with analytics data
    """
    db = SessionLocal()
    try:
        # Base query with filters
        base_query = db.query(Precedent).filter(
            Precedent.organization_id == organization_id
        )

        if legal_area:
            base_query = base_query.filter(Precedent.legal_area == legal_area)
        if court:
            base_query = base_query.filter(Precedent.court.ilike(f"%{court}%"))
        if year_from:
            base_query = base_query.filter(Precedent.year >= year_from)
        if year_to:
            base_query = base_query.filter(Precedent.year <= year_to)
        if matter_type:
            base_query = base_query.filter(Precedent.matter_type.ilike(f"%{matter_type}%"))

        # 1. Volume by year
        year_counts = db.query(
            Precedent.year,
            func.count(Precedent.id)
        ).filter(
            Precedent.organization_id == organization_id
        ).group_by(Precedent.year).order_by(Precedent.year).all()

        volume_by_year = [
            {"year": year, "count": count}
            for year, count in year_counts
        ]

        # 2. Volume by court
        court_counts = db.query(
            Precedent.court,
            func.count(Precedent.id)
        ).filter(
            Precedent.organization_id == organization_id
        ).group_by(Precedent.court).order_by(
            func.count(Precedent.id).desc()
        ).limit(15).all()

        volume_by_court = [
            {"court": c, "count": count}
            for c, count in court_counts
        ]

        # 3. Volume by legal area
        area_counts = db.query(
            Precedent.legal_area,
            func.count(Precedent.id)
        ).filter(
            Precedent.organization_id == organization_id
        ).group_by(Precedent.legal_area).order_by(
            func.count(Precedent.id).desc()
        ).all()

        volume_by_legal_area = [
            {"legal_area": area, "count": count}
            for area, count in area_counts
        ]

        # 4. Top voces (extract and count)
        voces_counter = Counter()
        all_precedents_for_voces = base_query.all()
        for p in all_precedents_for_voces:
            if p.voces:
                # Split by comma and clean
                voices = [v.strip() for v in p.voces.split(",")]
                voces_counter.update(voices)

        top_voces = [
            {"voice": voice, "count": count}
            for voice, count in voces_counter.most_common(20)
        ]

        # 5. Top ponentes
        ponente_counts = db.query(
            Precedent.ponente,
            func.count(Precedent.id)
        ).filter(
            Precedent.organization_id == organization_id,
            Precedent.ponente.isnot(None),
            Precedent.ponente != ""
        ).group_by(Precedent.ponente).order_by(
            func.count(Precedent.id).desc()
        ).limit(15).all()

        top_ponentes = [
            {"ponente": p, "count": count}
            for p, count in ponente_counts if p
        ]

        # 6. Temporal evolution by legal area
        temporal_data = db.query(
            Precedent.year,
            Precedent.legal_area,
            func.count(Precedent.id)
        ).filter(
            Precedent.organization_id == organization_id
        ).group_by(Precedent.year, Precedent.legal_area).all()

        # Group by legal_area
        temporal_evolution = {}
        for year, area, count in temporal_data:
            if area not in temporal_evolution:
                temporal_evolution[area] = []
            temporal_evolution[area].append({"year": year, "count": count})

        # Sort each area's timeline
        for area in temporal_evolution:
            temporal_evolution[area].sort(key=lambda x: x["year"])

        # 7. Court × Matter heatmap (top courts only)
        top_courts = [c["court"] for c in volume_by_court[:8]]

        heatmap_query = db.query(
            Precedent.court,
            Precedent.legal_area,
            func.count(Precedent.id)
        ).filter(
            Precedent.organization_id == organization_id,
            Precedent.court.in_(top_courts)
        ).group_by(Precedent.court, Precedent.legal_area).all()

        # Build heatmap as list of dicts
        court_matter_heatmap = []
        for c, area, count in heatmap_query:
            court_matter_heatmap.append({
                "court": c,
                "legal_area": area,
                "count": count
            })

        # 8. Summary stats
        total_count = db.query(func.count(Precedent.id)).filter(
            Precedent.organization_id == organization_id
        ).scalar()

        year_range = db.query(
            func.min(Precedent.year),
            func.max(Precedent.year)
        ).filter(
            Precedent.organization_id == organization_id
        ).first()

        # 9. Text analysis (optional, expensive)
        text_analysis = {}
        if include_text_analysis:
            # Simple word frequency from decisions
            word_counter = Counter()
            stop_words = {
                "el", "la", "los", "las", "de", "del", "en", "y", "a", "que",
                "es", "por", "para", "con", "su", "una", "se", "no", "lo",
                "como", "más", "pero", "este", "esta", "estos", "estas"
            }

            for p in all_precedents_for_voces[:500]:  # Limit sample for performance
                if p.decision:
                    words = p.decision.lower().split()
                    filtered = [w for w in words if len(w) > 4 and w not in stop_words]
                    word_counter.update(filtered)

            top_keywords = [
                {"word": word, "frequency": count / len(all_precedents_for_voces[:500])}
                for word, count in word_counter.most_common(30)
            ]
            text_analysis = {"top_keywords": top_keywords}

        return {
            "summary": {
                "total_precedents": total_count or 0,
                "year_range": {
                    "min": year_range[0] if year_range else None,
                    "max": year_range[1] if year_range else None
                },
                "unique_courts": len(volume_by_court),
                "unique_areas": len(volume_by_legal_area)
            },
            "volume_by_year": volume_by_year,
            "volume_by_court": volume_by_court,
            "volume_by_legal_area": volume_by_legal_area,
            "court_matter_heatmap": court_matter_heatmap,
            "top_voces": top_voces,
            "top_ponentes": top_ponentes,
            "temporal_evolution": temporal_evolution,
            "text_analysis": text_analysis
        }

    finally:
        db.close()


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

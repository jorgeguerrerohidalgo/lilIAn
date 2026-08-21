"""S5.3 — Sembrador de PRECEDENTES SINTÉTICOS para la galería de demos.

================================================================
IMPORTANTE — LEE ESTO ANTES DE EJECUTAR:
================================================================
Los registros que siembra este script son **ejemplos ilustrativos
sintéticos**, NO sentencias reales de la Corte Suprema de Chile:

  - Los ``roll_number`` empiezan en ``SYNTH-`` para que sean
    inequívocamente identificables en la base de datos.
  - Los nombres de ministros son ficticios (combinaciones de
    magistraturas y oficinas reales del Poder Judicial).
  - El resumen y considerandos reproducen la doctrina y la
    estructura típica de una sentencia SCJ, pero el caso concreto
    NO existe en los registros oficiales del Poder Judicial.
  - El script marca cada fila con ``type="sintetico"`` y el
    ``disposition`` con el disclaimer ``SYNTHETIC``.

Esto es una versión de "first cut" mientras se negocia el
convenio de datos con la Biblioteca del Congreso Nacional o con
el portal del Poder Judicial para cargar el corpus real.
Ver ``docs/TODO_S5.3_REAL_CORPUS.md`` para los pasos pendientes.

=========================================================================
USO LOCAL:

    cd apps/backend
    python -m scripts.seed_synth_precedents --dry-run
    python -m scripts.seed_synth_precedents --only labor --confirm-synthetic

USO PROGRAMÁTICO:

    from scripts.seed_synth_precedents import seed_precedents, seed_status
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _THIS_DIR.parent
sys.path.insert(0, str(_BACKEND_DIR))

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.models.precedent import Precedent  # noqa: E402
from app.services.precedent_rag import index_precedent  # noqa: E402

logger = logging.getLogger("lilian.seed_synth_precedents")


SYNTHETIC_DISCLAIMER = (
    "SYNTHETIC: ejemplo ilustrativo, no es una sentencia real "
    "del Poder Judicial de Chile. Ver scripts/seed_synth_precedents.py."
)


# -----------------------------------------------------------------------------
# Catálogo de ejemplos sintéticos.
#
# Cada item reproduce la ESTRUCTURA típica de una sentencia SCJ (roles, año,
# materia, extracto de considerandos, decisión, dispositiva, voces) y
# cubre un área legal o tema del catálogo de los agentes de S5.1. El
# contenido se apoya en doctrina y jurisprudencia consolidada pero NO
# representa casos individuales identificables del Poder Judicial.
# -----------------------------------------------------------------------------


def _build_catalog() -> list[dict]:
    """Construye el catálogo de precedentes sintéticos.

    Mantenido como función para que cada ``summary`` incluya el
    disclaimer como primer párrafo, garantizando consistencia incluso si
    algún ítem se modifica a mano.
    """
    raw: list[dict] = [
        {
            "court": "Corte Suprema (sintético)",
            "year": 2021,
            "roll_number": "SYNTH-LAB-2021-01",
            "full_citation": "CS, 28.09.2021, Rol SYNTH-LAB-2021-01 (sintético)",
            "legal_area": "labor",
            "matter_type": "Despido injustificado",
            "summary_text": (
                "ILUSTRATIVO. Caso de síntesis: despido por necesidades de la "
                "empresa (art. 159 N°4 del Código del Trabajo) y mes de aviso "
                "previo. Resume la línea jurisprudencial predominante."
            ),
            "reasoning": (
                "Considerando primero: que el artículo 159 N°4 del Código del "
                "Trabajo exige que las necesidades de la empresa sean graves y "
                "calificadas, no resultando suficiente su mera invocación. "
                "Considerando segundo: que el onus probandi recae en el "
                "empleador. Considerando tercero: que la falta de comunicación "
                "con 30 días de anticipación genera el derecho al mes de aviso "
                "previo del artículo 162."
            ),
            "decision": (
                "Se declara injustificado el despido y se condena al pago de "
                "las indemnizaciones de los artículos 162 y 163 del Código "
                "del Trabajo, con los recargos del artículo 168 cuando no se "
                "paga oportunamente."
            ),
            "disposition": "Se confirma en lo apelado.",
            "voces": "Despido - Necesidades de la empresa - Indemnización sustitutiva",
            "ponente": "Ministro redactor (sintético)",
        },
        {
            "court": "Corte Suprema (sintético)",
            "year": 2020,
            "roll_number": "SYNTH-LAB-2020-02",
            "full_citation": "CS, 12.05.2020, Rol SYNTH-LAB-2020-02 (sintético)",
            "legal_area": "labor",
            "matter_type": "Finiquito",
            "summary_text": (
                "ILUSTRATIVO. Cosa juzgada del finiquito ratificado ante "
                "ministro de fe. Cubre la fuerza liberatoria del art. 177 "
                "y el vicio del consentimiento."
            ),
            "reasoning": (
                "Considerando primero: que el artículo 177 del Código del "
                "Trabajo establece la fuerza liberatoria del finiquito una "
                "vez ratificado ante ministro de fe. Considerando segundo: "
                "que la suscripción sin reserva de acciones extingue las "
                "acciones por remuneraciones y prestaciones del período, "
                "salvo vicio del consentimiento. Considerando tercero: que "
                "la acción de nulidad del despido del artículo 168 no "
                "queda cubierta por el finiquito."
            ),
            "decision": (
                "Se confirma la sentencia de base que rechazó una nueva "
                "demanda por diferencias de remuneración, por estar cubierta "
                "por el finiquito válidamente celebrado."
            ),
            "disposition": "Se confirma.",
            "voces": "Finiquito - Cosa juzgada - Ministro de fe",
            "ponente": "Ministro redactor (sintético)",
        },
        {
            "court": "Corte Suprema (sintético)",
            "year": 2019,
            "roll_number": "SYNTH-LAB-2019-03",
            "full_citation": "CS, 30.10.2019, Rol SYNTH-LAB-2019-03 (sintético)",
            "legal_area": "labor",
            "matter_type": "Tutela laboral",
            "summary_text": (
                "ILUSTRATIVO. Causal de despido del artículo 160 N°7 "
                "(incumplimiento grave). Cubre proporcionalidad y "
                "procedimiento del artículo 160."
            ),
            "reasoning": (
                "Considerando: que la gravedad de la infracción debe "
                "evaluarse considerando la antigüedad del trabajador, la "
                "reiteración de la conducta y la proporcionalidad de la "
                "medida. La aplicación automática de la causal máxima puede "
                "constituir despido injustificado."
            ),
            "decision": (
                "Se declara injustificado el despido y se condena al pago "
                "de indemnización por años de servicio, mes de aviso y "
                "recargo del artículo 168."
            ),
            "disposition": "Se confirma con costas.",
            "voces": "Tutela laboral - Despido - Proporcionalidad",
            "ponente": "Ministro redactor (sintético)",
        },
        {
            "court": "Corte Suprema (sintético)",
            "year": 2018,
            "roll_number": "SYNTH-LAB-2018-04",
            "full_citation": "CS, 22.06.2018, Rol SYNTH-LAB-2018-04 (sintético)",
            "legal_area": "labor",
            "matter_type": "Autodespido",
            "summary_text": (
                "ILUSTRATIVO. Autodespido por incumplimiento del empleador "
                "del artículo 171. Cubre recargo del 50% por incumplimiento "
                "grave y reiterado."
            ),
            "reasoning": (
                "Considerando: que el artículo 171 del Código del Trabajo "
                "permite al trabajador poner término al contrato invocando "
                "el incumplimiento del empleador, teniendo derecho a las "
                "mismas indemnizaciones del artículo 168 más el recargo del "
                "50% si el incumplimiento es de carácter grave y reiterado."
            ),
            "decision": "Se confirma la declaración de autodespido justificado.",
            "disposition": "Se confirma.",
            "voces": "Autodespido - Artículo 171",
            "ponente": "Ministro redactor (sintético)",
        },
        {
            "court": "Corte Suprema (sintético)",
            "year": 2022,
            "roll_number": "SYNTH-LAB-2022-05",
            "full_citation": "CS, 15.11.2022, Rol SYNTH-LAB-2022-05 (sintético)",
            "legal_area": "labor",
            "matter_type": "Contrato de trabajo",
            "summary_text": (
                "ILUSTRATIVO. Cláusula de no competencia post-contractual. "
                "Requisitos copulativos del artículo 22 inciso 2°."
            ),
            "reasoning": (
                "Considerando: que la jurisprudencia reiterada exige la "
                "concurrencia simultánea de los tres requisitos del "
                "artículo 22 inciso 2°. La falta de uno cualquiera "
                "determina la nulidad de la cláusula."
            ),
            "decision": "Se declara la nulidad de la cláusula de exclusividad.",
            "disposition": "Se confirma.",
            "voces": "No competencia - Exclusividad - Artículo 22",
            "ponente": "Ministro redactor (sintético)",
        },
        {
            "court": "Corte Suprema (sintético)",
            "year": 2020,
            "roll_number": "SYNTH-CIV-2020-06",
            "full_citation": "CS, 18.08.2020, Rol SYNTH-CIV-2020-06 (sintético)",
            "legal_area": "civil",
            "matter_type": "Arriendo urbano",
            "summary_text": (
                "ILUSTRATIVO. Garantía de arriendo del art. 6 Ley 18.101: "
                "carácter real y no imputabilidad a rentas."
            ),
            "reasoning": (
                "Considerando: que el artículo 6 de la Ley 18.101 "
                "establece el carácter real y no convencional de la "
                "garantía, el cual no puede ser alterado por la sola "
                "voluntad de las partes. La cláusula que autoriza la "
                "imputación a rentas requiere la manifestación expresa "
                "del arrendatario."
            ),
            "decision": "Se declara abusiva la cláusula de imputación automática.",
            "disposition": "Se confirma con costas.",
            "voces": "Arriendo - Garantía - Ley 18.101",
            "ponente": "Ministro redactor (sintético)",
        },
        {
            "court": "Corte Suprema (sintético)",
            "year": 2021,
            "roll_number": "SYNTH-CIV-2021-07",
            "full_citation": "CS, 10.06.2021, Rol SYNTH-CIV-2021-07 (sintético)",
            "legal_area": "civil",
            "matter_type": "Arriendo comercial",
            "summary_text": (
                "ILUSTRATIVO. Aviso de terminación del artículo 12 de la "
                "Ley 18.101: 60 días (vivienda) y 90 días (comercio)."
            ),
            "reasoning": (
                "Considerando: que el artículo 12 de la Ley 18.101 "
                "distingue entre el desahucio del contrato de vivienda "
                "(60 días) y el destinado a comercio, taller o industria "
                "(90 días), siempre que el contrato hubiere durado más "
                "de un año."
            ),
            "decision": "Se condena al pago de las rentas del período de preaviso.",
            "disposition": "Se confirma.",
            "voces": "Desahucio - Arriendo comercial - Preaviso",
            "ponente": "Ministro redactor (sintético)",
        },
        {
            "court": "Corte Suprema (sintético)",
            "year": 2019,
            "roll_number": "SYNTH-CIV-2019-08",
            "full_citation": "CS, 25.03.2019, Rol SYNTH-CIV-2019-08 (sintético)",
            "legal_area": "civil",
            "matter_type": "Contrato de compraventa",
            "summary_text": (
                "ILUSTRATIVO. Condición resolutoria tácita del artículo "
                "1489 del Código Civil: efectos sobre el contrato "
                "bilateral conmutativo."
            ),
            "reasoning": (
                "Considerando: que la condición resolutoria tácita del "
                "artículo 1489 del Código Civil opera ipso iure en los "
                "contratos bilateralmente conmutativos, no siendo "
                "necesario pacto expreso. La parte cumplidora puede "
                "optar entre la ejecución forzada o la resolución con "
                "indemnización de perjuicios."
            ),
            "decision": "Se declara la resolución del contrato de compraventa.",
            "disposition": "Se confirma.",
            "voces": "Condición resolutoria tácita - Compraventa",
            "ponente": "Ministro redactor (sintético)",
        },
        {
            "court": "Corte Suprema (sintético)",
            "year": 2022,
            "roll_number": "SYNTH-CIV-2022-09",
            "full_citation": "CS, 22.04.2022, Rol SYNTH-CIV-2022-09 (sintético)",
            "legal_area": "civil",
            "matter_type": "Generación de hipoteca",
            "summary_text": (
                "ILUSTRATIVO. Constitución de hipoteca: solemnidades del "
                "artículo 2409 del Código Civil (escritura pública e "
                "inscripción)."
            ),
            "reasoning": (
                "Considerando: que la solemnidad de la hipoteca del "
                "artículo 2409 del Código Civil exige escritura pública "
                "e inscripción, sin las cuales el gravamen no nace a la "
                "vida jurídica. La hipoteca legal queda sujeta al "
                "procedimiento de los artículos 2428 y siguientes."
            ),
            "decision": "Se declara la nulidad de la hipoteca por falta de solemnidades.",
            "disposition": "Se confirma.",
            "voces": "Hipoteca - Solemnidades - Inscripción",
            "ponente": "Ministro redactor (sintético)",
        },
        {
            "court": "Corte Suprema (sintético)",
            "year": 2018,
            "roll_number": "SYNTH-CIV-2018-10",
            "full_citation": "CS, 08.11.2018, Rol SYNTH-CIV-2018-10 (sintético)",
            "legal_area": "civil",
            "matter_type": "Responsabilidad extracontractual",
            "summary_text": (
                "ILUSTRATIVO. Responsabilidad extracontractual del "
                "artículo 2314 del Código Civil: prueba de la culpa o "
                "negligencia."
            ),
            "reasoning": (
                "Considerando: que la doctrina de la responsabilidad "
                "extracontractual en Chile se rige por el artículo 2314 "
                "del Código Civil, correspondiendo al actor probar la "
                "culpa o negligencia del demandado, salvo en los casos "
                "de responsabilidad objetiva del artículo 2329."
            ),
            "decision": "Se condena al pago de indemnización por daño moral.",
            "disposition": "Se confirma con costas.",
            "voces": "Responsabilidad extracontractual - Culpa - Daño",
            "ponente": "Ministro redactor (sintético)",
        },
    ]
    return raw


PRECEDENTS: list[dict] = _build_catalog()


# -----------------------------------------------------------------------------
# Carga, idempotencia, y resumen
# -----------------------------------------------------------------------------


@dataclass
class SeedReport:
    inserted: int = 0
    skipped_existing: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> dict:
        return {
            "inserted": self.inserted,
            "skipped_existing": self.skipped_existing,
            "failed": self.failed,
            "errors": self.errors,
            "dry_run": self.dry_run,
            "total_in_catalog": len(PRECEDENTS),
            "synthetic": True,
            "disclaimer": SYNTHETIC_DISCLAIMER,
        }


def _existing_citations(db) -> set[str]:
    rows = (
        db.query(Precedent.full_citation)
        .filter(Precedent.full_citation.isnot(None))
        .all()
    )
    return {row[0] for row in rows if row[0]}


def seed_precedents(
    *,
    only: str | None = None,
    dry_run: bool = False,
) -> SeedReport:
    """Sembrar el catálogo de precedentes sintéticos en la tabla ``precedents``.

    Args:
        only: filtro por ``legal_area`` (``labor``, ``civil``, etc.).
        dry_run: si es True, no escribe.
    """
    report = SeedReport(dry_run=dry_run)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = set() if dry_run else _existing_citations(db)
        catalog = PRECEDENTS
        if only:
            only = only.lower()
            catalog = [p for p in PRECEDENTS if p["legal_area"] == only]

        for data in catalog:
            citation = data["full_citation"]
            if citation in existing:
                report.skipped_existing += 1
                continue
            try:
                if not dry_run:
                    row = Precedent(
                        organization_id=None,
                        court=data["court"],
                        tribunal=data["court"],
                        year=data["year"],
                        roll_number=data["roll_number"],
                        full_citation=data["full_citation"],
                        legal_area=data["legal_area"],
                        matter_type=data["matter_type"],
                        summary=data["summary_text"],
                        reasoning=data.get("reasoning"),
                        decision=data.get("decision"),
                        disposition=SYNTHETIC_DISCLAIMER,
                        voces=data.get("voces"),
                        ponente=data.get("ponente"),
                        type="sintetico",
                    )
                    db.add(row)
                    db.flush()  # populate row.id
                    # Index the embedding via the existing precedent_rag
                    # helper. Failures are logged but do not block the seed.
                    try:
                        index_precedent(row.id, db)
                    except Exception as exc:
                        logger.warning(
                            "index_precedent failed for %s: %s",
                            citation, exc,
                        )
                report.inserted += 1
                existing.add(citation)
            except Exception as exc:
                logger.exception("seed_precedents: failed %s", citation)
                report.failed += 1
                report.errors.append(f"{citation}: {exc}")

        if not dry_run:
            db.commit()
    finally:
        db.close()

    return report


def seed_status() -> dict:
    """Resumen del estado actual de los precedentes indexados."""
    db = SessionLocal()
    try:
        from sqlalchemy import func

        total = db.query(func.count(Precedent.id)).scalar() or 0
        synth_total = (
            db.query(func.count(Precedent.id))
            .filter(Precedent.type == "sintetico")
            .scalar()
            or 0
        )
        rows = (
            db.query(
                Precedent.legal_area,
                func.count(Precedent.id).label("count"),
            )
            .filter(Precedent.type == "sintetico")
            .group_by(Precedent.legal_area)
            .all()
        )
        return {
            "total_precedents": total,
            "synthetic_precedents": synth_total,
            "by_legal_area": {r.legal_area: r.count for r in rows},
            "catalog_size": len(PRECEDENTS),
            "synthetic": True,
            "disclaimer": SYNTHETIC_DISCLAIMER,
        }
    finally:
        db.close()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "S5.3 — Sembrador de precedentes SINTÉTICOS (no usar como "
            "fuente de citas reales)."
        )
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        choices=["labor", "civil", "commerce", "family", "consumer", "penal", "other"],
        help="Sembrar sólo los precedentes de un área legal.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No escribe en la base de datos, sólo reporta.",
    )
    parser.add_argument(
        "--confirm-synthetic",
        action="store_true",
        help=(
            "Confirma que entiendes que este seed crea ejemplos "
            "ilustrativos sintéticos, no sentencias reales del "
            "Poder Judicial de Chile. Sin este flag el script "
            "se niega a correr."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    if not args.confirm_synthetic and not args.dry_run:
        logger.error(
            "Refusing to run: --confirm-synthetic is required to write "
            "to the database. This seed creates ILUSTRATIVE examples "
            "(roll numbers start with SYNTH-) and must not be confused "
            "with real SCJ jurisprudence. Re-run with --confirm-synthetic "
            "or --dry-run."
        )
        return 2
    logger.warning(
        "Sembrando precedentes SINTÉTICOS. Estos roll numbers no "
        "corresponden a sentencias reales del Poder Judicial."
    )
    report = seed_precedents(only=args.only, dry_run=args.dry_run)
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    return 0 if not report.errors else 1


if __name__ == "__main__":
    sys.exit(main())

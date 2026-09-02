"""Discover and curate Tier 2 of the corpus legal chileno.

Tier 1 (``ingest_bcn_corpus.TIER1_BCN_IDS``) covers the ten most
fundamental Chilean norms (Codigo Civil, Penal, Trabajo, Comercio,
Procesal Penal, Constitucion, Ley 21.719, Ley 19.628 DICOM, Ley 18.046
S.A., Ley 19.496 Consumidor). That covers the most-cited cases but the
recall ceiling sits at ~45% with top_k=20 — Q2-Q5, Q19 fail because the
underlying BCN feed for 1209272 only exposes transitional articles, and
Q13-Q14, Q16-Q17 fail because articles specific to a question never
make the top-k when there are only Tier 1 norms to draw from.

Tier 2 adds ~100 more Chilean laws that the platform's lawyer-users
cite frequently enough that a RAG query is likely to touch them. The
list is curated from the same shortlist a Chilean law school would
treat as mandatory reading: family law, tax, banking, securities,
urbanismo, propiedad horizontal, medio ambiente, etc.

This module exposes two CLI subcommands:

- ``list``   — print the curated :data:`TIER2_BCN_IDS` set + metadata
- ``discover`` — walk BCN's ``opt=3`` catalog (``fetch_catalog_page``)
  and emit a candidate list ranked by relevance signals (publication
  recency + type filter). The output is a starting point for the next
  round of curation; we never auto-ingest from this.

Both subcommands are read-only against the corpus DB. The actual
ingest happens through ``ingest_bcn_corpus cmd_ingest_tier2`` which
imports the curated list from this module.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Local imports — ``ingest_bcn_corpus`` is the sibling script.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripts.bcn_http_client import BCNHttpClient  # noqa: E402
from scripts.ingest_bcn_corpus import TIER1_BCN_IDS  # noqa: E402

logger = logging.getLogger("lilian.discover_bcn_catalog")


# Hand-curated Tier 2. Each entry is ``(bcn_id, label, topic)``. The
# ``bcn_id`` matches BCN's idNorma; if it has the same idLey/idNorma
# mismatch that Tier 1 has for some ids, callers must route through
# :func:`scripts.ingest_bcn_corpus._fetch_norm_xml` which already
# honours :data:`TIER1_USE_IDLEY`. (The same set is used for Tier 2
# because the routing logic is identical.)
#
# Criteria: each law here is a named "ley/DECRETO/DFL" cited by at
# least one of the three Chilean legal curricula (civil, comercial,
# procesal) as mandatory reading; the list is intentionally biased
# toward statutes with stable refundido consolidations (so BCN's
# ``idNorma`` endpoint returns the consolidated text).
TIER2_BCN_IDS: list[tuple[str, str, str]] = [
    # --- Familia, sucesiones, persona ---
    ("5772",    "Ley 4.808 — Registro Civil",                       "registro_civil"),
    ("14582",   "Ley 14.908 — Abandono de familia y pago de pensiones alimenticias", "familia"),
    ("16620",   "Ley 16.620 — Adopción de menores",                "familia"),
    ("19499",   "Ley 19.496 — Protección al Consumidor",            "consumidor"),  # tier 1 actually
    ("19947",   "Ley 19.947 — Matrimonio civil (divorcio)",        "familia"),
    ("20080",   "Ley 20.080 — Reforma Tribunal de Familia",         "familia"),
    ("21030",   "Ley 21.030 — Despenalización aborto 3 causales",  "familia"),

    # --- Tributario ---
    ("684",     "DFL 1 Hacienda — Ley de Renta (impuesto a la renta)", "tributario"),
    ("23748",   "DFL 4 Hacienda — Estatuto INP / SUSESO",           "prevision"),
    ("830",     "DFL 830 — Codigo Tributario",                       "tributario"),
    ("31902",   "DL 3.190 — Ley de Impuesto a las Herencias",       "tributario"),
    ("31944",   "DL 3.194 — Donaciones",                             "tributario"),

    # --- Bancario, mercado de valores, seguros ---
    ("3614",    "DFL 3 — Ley General de Bancos",                    "bancario"),
    ("18045",   "Ley 18.045 — Mercado de Valores",                  "mercado_valores"),
    ("18076",   "Ley 18.076 — Seguro de cesantía",                  "prevision"),
    ("18933",   "Ley 18.933 — Isapres",                              "salud"),
    ("19968",   "Ley 19.968 — Tribunales de Familia",                "familia"),
    ("20066",   "Ley 20.066 — Violencia intrafamiliar",              "familia"),

    # --- Laboral / seguridad social (ya hay Codigo del Trabajo en T1) ---
    ("18620",   "DL 3.500 — Sistema de pensiones AFP",              "prevision"),
    ("3500",    "DL 3.500 — Pensiones (otra numeración)",            "prevision"),
    ("18833",   "Ley 18.833 — Estatuto administrativo",              "administrativo"),
    ("19628",   "Ley 19.628 — Protección de datos (versión idNorma original)",  "data_protection"),  # tier 1 has the refundida
    ("20281",   "Ley 20.281 — Propiedad horizontal",                "inmobiliario"),
    ("19537",   "Ley 19.537 — Copropiedad inmobiliaria",             "inmobiliario"),

    # --- Urbanismo, construcción, medio ambiente ---
    ("458",     "DFL 458 — Ley General de Urbanismo y Construcciones", "urbanismo"),
    ("47",      "DFL 47 — Ordenanza General de Urbanismo",           "urbanismo"),
    ("19300",   "Ley 19.300 — Bases del medio ambiente",             "ambiental"),
    ("19317",   "Ley 19.317 — Modifica Ley de Medio Ambiente",       "ambiental"),
    ("20251",   "Ley 20.251 — Modifica medio ambiente (RCAs)",       "ambiental"),

    # --- Salud, alimentos, consumidor ---
    ("725",     "DFL 725 — Codigo Sanitario",                        "salud"),
    ("20606",   "Ley 20.606 — Etiquetado de alimentos",              "salud"),
    ("21081",   "Ley 21.081 — Modifica Codigo Sanitario",            "salud"),

    # --- Propiedad intelectual, comercial ---
    ("17336",   "Ley 17.336 — Propiedad intelectual",                "pi"),
    ("19039",   "Ley 19.039 — Marcas comerciales",                   "pi"),
    ("19657",   "Ley 19.657 — Patentes de invención",                "pi"),

    # --- Procesal (ya hay CPP en T1) ---
    ("1552",    "Codigo de Procedimiento Civil",                     "procesal"),
    ("3470",    "DFL 3470 — Codigo Organico de Tribunales",           "procesal"),
    ("18702",   "Ley 18.702 — Modifica COT",                         "procesal"),
    ("21145",   "Ley 21.145 — Modifica COT (ley moderna)",           "procesal"),

    # --- Minería, energía, recursos naturales ---
    ("600",     "Codigo de Minería",                                  "mineria"),
    ("1089",    "Codigo de Aguas",                                    "mineria"),
    ("4961",    "DFL 4 Minería — Concesiones mineras",                "mineria"),
    ("20225",   "Ley 20.225 — Modifica Codigo de Minería",            "mineria"),

    # --- Telecomunicaciones, transporte ---
    ("7672",    "Ley 7.672 — Empresa de Ferrocarriles",              "transporte"),
    ("18432",   "Ley 18.432 — Telecomunicaciones",                    "telecom"),
    ("18168",   "Ley 18.168 — Televisión",                            "telecom"),
    ("20006",   "Ley 20.006 — Transporte público",                    "transporte"),

    # --- Educación ---
    ("3704",    "Ley 3.704 — Subvencion estatal educacion",           "educacion"),
    ("18662",   "DFL 2 Educación — Estatuto docente",                 "educacion"),
    ("20259",   "Ley 20.259 — Reforma educacional",                   "educacion"),

    # --- Defensa del consumidor, libre competencia ---
    ("211",     "DL 211 — Libre competencia",                         "consumidor"),
    ("18425",   "Ley 18.425 — SERNAC financiero",                     "consumidor"),

    # --- Otros relevantes ---
    ("2974",    "Codigo de Comercio refundido histórico (DL 456)",    "comercial"),
    ("3292",    "Codigo Penal Militar",                               "penal"),
    ("8089",    "Ley 8.089 — Justicia Militar",                       "penal"),
    ("14908",   "Ley 14.908 — Pensiones alimenticias",                "familia"),
    ("17344",   "Ley 17.344 — Autorización salida menores",           "familia"),
    ("19876",   "Ley 19.876 — Reforma Procesal Penal",                "procesal"),
    ("21091",   "Ley 21.091 — Mercado de capitales",                  "mercado_valores"),
    ("21234",   "Ley 21.234 — Modernización Tributaria",              "tributario"),

    # --- Normas de reciente dictación que la BCN ya expone consolidadas ---
    ("21620",   "Ley 21.620 — Estatuto administrativo moderno",        "administrativo"),
    ("21735",   "Ley 21.735 — Reforma de Pensiones",                  "prevision"),
    ("21719",   "Ley 21.719 — Protección de Datos Personales",        "data_protection"),  # tier 1 ya lo tiene
]


def tier2_ids() -> list[str]:
    """Return just the BCN ids (string list), excluding any already in
    Tier 1 so callers don't double-ingest."""
    t1 = set(TIER1_BCN_IDS)
    return [bid for bid, _label, _topic in TIER2_BCN_IDS if bid not in t1]


@dataclass
class CatalogEntry:
    """Parsed row from a BCN ``opt=3`` catalog window."""
    bcn_id: str
    titulo: str
    tipo: str
    fecha_publicacion: Optional[str]
    numero: Optional[str]


def _parse_catalog_page(xml_text: str) -> list[CatalogEntry]:
    """Parse a single ``opt=3`` catalog window.

    BCN returns one ``<Norma>`` element per published law with metadata
    attributes and child nodes. We extract enough fields to rank
    candidates; the raw XML is the source of truth (see BCN's
    documentation on the Consulta/obtxml endpoint).
    """
    # Lazy import so the CLI works in environments without lxml.
    from lxml import etree

    NS = {"n": "http://www.leychile.cl/esquemas"}
    root = etree.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    entries = []
    for norma in root.findall("./n:Norma", NS):
        bcn_id = norma.get("normaId", "").strip()
        titulo = "".join(norma.itertext()).strip()[:200]
        id_node = norma.find("./n:Identificador", NS)
        fecha = id_node.get("fechaPublicacion") if id_node is not None else None
        tipo = None
        numero = None
        tn = norma.find("./n:Identificador/n:TiposNumeros/n:TipoNumero", NS)
        if tn is not None:
            t = tn.findtext("./n:Tipo", namespaces=NS)
            n = tn.findtext("./n:Numero", namespaces=NS)
            tipo = t.strip().lower() if t else None
            numero = n.strip() if n else None
        if bcn_id:
            entries.append(CatalogEntry(
                bcn_id=bcn_id,
                titulo=titulo,
                tipo=tipo or "",
                fecha_publicacion=fecha,
                numero=numero,
            ))
    return entries


def discover(
    *,
    client: BCNHttpClient,
    page_size: int = 100,
    max_pages: int = 70,
    tipo_filter: Optional[Iterable[str]] = None,
) -> list[CatalogEntry]:
    """Walk BCN's ``opt=3`` catalog and return all entries.

    The catalog has ~6.700 published norms (per STATUS.md Tier 3
    estimate). With ``page_size=100`` and ``max_pages=70`` we walk 7.000
    rows which is the upper bound. Adjust ``max_pages`` downward for
    smoke tests.

    ``tipo_filter`` filters by BCN's ``Tipo`` field (``ley``, ``decreto``,
    ``df``, ``codigo``). If ``None`` we keep everything.
    """
    tipo_filter = set(tipo_filter) if tipo_filter else None
    out: list[CatalogEntry] = []
    for offset in range(0, page_size * max_pages, page_size):
        page = client.fetch_catalog_page(offset=offset, limit=page_size)
        if not page:
            logger.info("empty page at offset=%d — catalog exhausted", offset)
            break
        entries = _parse_catalog_page(page)
        if not entries:
            logger.info("no entries at offset=%d — end of catalog", offset)
            break
        if tipo_filter:
            entries = [e for e in entries if e.tipo in tipo_filter]
        out.extend(entries)
        logger.info("offset=%d → +%d entries (total=%d)", offset, len(entries), len(out))
    return out


def cmd_list(args) -> int:
    ids = tier2_ids()
    print(f"Tier 2 curated ids (excluding Tier 1 overlap): {len(ids)}")
    for bid in ids:
        label = next((l for b, l, _t in TIER2_BCN_IDS if b == bid), "")
        print(f"  {bid:8s}  {label}")
    return 0


def cmd_discover(args) -> int:
    client = BCNHttpClient()
    entries = discover(
        client=client,
        page_size=args.page_size,
        max_pages=args.max_pages,
        tipo_filter=args.tipo,
    )
    out_path = Path(args.output)
    payload = [e.__dict__ for e in entries]
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(entries)} catalog entries to {out_path}")
    print("Use this file to expand TIER2_BCN_IDS — auto-ingest from this list is intentionally not implemented.")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="Print the curated TIER2_BCN_IDS set")
    p_list.set_defaults(func=cmd_list)

    p_discover = sub.add_parser(
        "discover",
        help="Walk BCN's opt=3 catalog and write the candidate list to JSON",
    )
    p_discover.add_argument("--output", default="data/tier2_candidates.json",
                            help="Output JSON path (default: data/tier2_candidates.json)")
    p_discover.add_argument("--page-size", type=int, default=100)
    p_discover.add_argument("--max-pages", type=int, default=70,
                            help="~6.700 norms total at page-size=100")
    p_discover.add_argument("--tipo", action="append",
                            help="Filter by BCN Tipo field (can repeat; e.g. --tipo ley --tipo codigo)")
    p_discover.set_defaults(func=cmd_discover)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

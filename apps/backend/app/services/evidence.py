"""
EvidenceBundle - Sistema de trazabilidad línea de respuesta → fuente.

Permite rastrear qué chunk/fuente soporta cada afirmación del análisis,
generando citas navegables con contexto.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import re


@dataclass
class EvidenceSource:
    """Fuente de evidencia (chunk de documento o precedente)."""
    source_id: str           # ID del chunk o precedente
    source_type: str         # "document_chunk", "legal_source", "precedent"
    document_id: Optional[int] = None
    content: str = ""        # Texto del chunk
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    legal_area: Optional[str] = None
    similarity_score: float = 0.0


@dataclass
class EvidenceCitation:
    """Una cita que soporta una afirmación en el análisis."""
    id: str                 # ID único de la cita
    claim: str              # Afirmación que soporta
    evidence_source: EvidenceSource
    quoted_text: str        # Texto exacto citado
    start_pos: int = 0     # Posición inicio en el claim
    end_pos: int = 0       # Posición fin en el claim
    relevance_score: float = 0.0


@dataclass
class EvidenceBundle:
    """
    Colección de citas que soportan un análisis.

    Permite:
    - Agregar citas con fuentes
    - Generar citaciones formateadas para texto
    - Exportar como JSON para el frontend
    - Validar que todas las citas sean navegables
    """
    analysis_id: Optional[int] = None
    citations: List[EvidenceCitation] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def add_citation(
        self,
        claim: str,
        source: EvidenceSource,
        quoted_text: str,
        relevance_score: float = 1.0
    ) -> EvidenceCitation:
        """Agrega una cita al bundle."""
        citation_id = f"cite_{len(self.citations) + 1:03d}"

        # Buscar posición del quoted_text en el claim
        start_pos = claim.find(quoted_text)
        if start_pos == -1:
            # Buscar aproximado
            start_pos = 0
            end_pos = len(claim)
        else:
            end_pos = start_pos + len(quoted_text)

        citation = EvidenceCitation(
            id=citation_id,
            claim=claim,
            evidence_source=source,
            quoted_text=quoted_text,
            start_pos=start_pos,
            end_pos=end_pos,
            relevance_score=relevance_score
        )

        self.citations.append(citation)
        return citation

    def get_citations_for_claim(self, claim: str) -> List[EvidenceCitation]:
        """Obtiene todas las citas que soportan una afirmación específica."""
        return [c for c in self.citations if c.claim == claim]

    def to_markdown(self) -> str:
        """Genera citaciones en formato Markdown."""
        if not self.citations:
            return ""

        lines = ["## Fuentes y Citas\n"]

        for cite in self.citations:
            source = cite.evidence_source
            lines.append(f"### [{cite.id}] {source.source_type.upper()}\n")
            lines.append(f"**Cita:** \"{cite.quoted_text}\"\n")
            lines.append(f"**Contexto:** ...{cite.claim[:100]}...\n")

            if source.document_id:
                lines.append(f"**Documento:** ID {source.document_id}")
            if source.page_number:
                lines.append(f"**Página:** {source.page_number}")
            if source.section_title:
                lines.append(f"**Sección:** {source.section_title}")

            lines.append(f"**Relevancia:** {cite.relevance_score:.2f}\n")
            lines.append("---\n")

        return "\n".join(lines)

    def to_frontend_dict(self) -> Dict[str, Any]:
        """Genera dict para enviar al frontend."""
        return {
            "analysis_id": self.analysis_id,
            "citation_count": len(self.citations),
            "citations": [
                {
                    "id": c.id,
                    "quoted_text": c.quoted_text,
                    "relevance_score": c.relevance_score,
                    "source": {
                        "type": c.evidence_source.source_type,
                        "id": c.evidence_source.source_id,
                        "document_id": c.evidence_source.document_id,
                        "page_number": c.evidence_source.page_number,
                        "section_title": c.evidence_source.section_title,
                        "legal_area": c.evidence_source.legal_area,
                    }
                }
                for c in self.citations
            ],
            "created_at": self.created_at.isoformat()
        }

    def get_navigable_links(self) -> List[Dict[str, Any]]:
        """Genera links navegables para el frontend."""
        links = []
        for cite in self.citations:
            source = cite.evidence_source
            links.append({
                "citation_id": cite.id,
                "text": cite.quoted_text[:50] + "..." if len(cite.quoted_text) > 50 else cite.quoted_text,
                "target": {
                    "type": source.source_type,
                    "id": source.document_id,
                    "page": source.page_number,
                    "section": source.section_title,
                },
                "relevance": cite.relevance_score
            })
        return links


def extract_evidence_from_chunks(
    chunks: List[Dict],
    query: str,
    top_k: int = 5
) -> EvidenceBundle:
    """
    Extrae evidencia de chunks para soportar un análisis.

    Args:
        chunks: Lista de chunks con 'content', 'document_id', etc.
        query: Query/búsqueda que originó los chunks
        top_k: Número máximo de citas a incluir

    Returns:
        EvidenceBundle con las citas más relevantes
    """
    bundle = EvidenceBundle()

    # Ordenar chunks por similarity (si está disponible)
    sorted_chunks = sorted(
        chunks,
        key=lambda x: x.get("similarity", 0),
        reverse=True
    )[:top_k]

    for i, chunk in enumerate(sorted_chunks):
        source = EvidenceSource(
            source_id=str(chunk.get("id", "")),
            source_type="document_chunk",
            document_id=chunk.get("document_id"),
            content=chunk.get("content", ""),
            page_number=chunk.get("page_number"),
            section_title=chunk.get("section_title"),
            legal_area=chunk.get("legal_area"),
            similarity_score=chunk.get("similarity", 0)
        )

        # Usar primeras 200 chars del chunk como cita
        quoted = chunk.get("content", "")[:200]
        if len(chunk.get("content", "")) > 200:
            quoted += "..."

        bundle.add_citation(
            claim=query,
            source=source,
            quoted_text=quoted,
            relevance_score=chunk.get("similarity", 0)
        )

    return bundle


def format_citation_with_link(
    citation: EvidenceCitation,
    base_url: str = "/documents/{document_id}#page={page}"
) -> str:
    """
    Formatea una cita con link navegable.

    Args:
        citation: La cita a formatear
        base_url: Template de URL con placeholders

    Returns:
        String formateado con link markdown
    """
    source = citation.evidence_source

    if source.source_type == "document_chunk" and source.document_id:
        url = base_url.format(
            document_id=source.document_id,
            page=source.page_number or 1
        )
        return f'[{citation.quoted_text}]({url})'

    return citation.quoted_text


def create_citation_context(
    citation: EvidenceCitation,
    context_chars: int = 50
) -> str:
    """
    Crea contexto alrededor de una cita.

    Args:
        citation: La cita
        context_chars: Caracteres de contexto antes/después

    Returns:
        Texto con contexto agregado
    """
    quote = citation.quoted_text
    source = citation.evidence_source

    # Agregar contexto del documento
    context_parts = []

    if source.section_title:
        context_parts.append(f"[{source.section_title}]")

    context_parts.append(f'"{quote}"')

    if source.page_number:
        context_parts.append(f"(pág. {source.page_number})")

    return " ".join(context_parts)

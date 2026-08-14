"use client";

import { useState } from "react";

interface CitationSource {
  type: "document_chunk" | "legal_source" | "precedent";
  id: string;
  document_id?: number;
  page?: number;
  section?: string;
  legal_area?: string;
}

interface Citation {
  id: string;
  quoted_text: string;
  relevance_score: number;
  source: CitationSource;
}

interface CitationLinkProps {
  citation: Citation;
  onNavigate?: (citation: Citation) => void;
}

/**
 * Componente CitationLink - Citación navegable.
 *
 * Muestra una cita con highlight y al hacer click navega al pasaje fuente.
 * Útil para integrar EvidenceBundle del backend.
 */
export function CitationLink({ citation, onNavigate }: CitationLinkProps) {
  const [showTooltip, setShowTooltip] = useState(false);

  const handleClick = () => {
    if (onNavigate) {
      onNavigate(citation);
    } else {
      // Navegación por defecto: ir al documento
      const url = buildNavigationUrl(citation.source);
      window.open(url, "_blank");
    }
  };

  return (
    <span className="citation-inline">
      <button
        type="button"
        onClick={handleClick}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        onFocus={() => setShowTooltip(true)}
        onBlur={() => setShowTooltip(false)}
        className="citation-trigger"
        title="Clic para ver fuente"
      >
        <span className="citation-text">&ldquo;{citation.quoted_text}&rdquo;</span>
        <span className="citation-badge">
          <svg aria-hidden="true"
            className="w-3 h-3"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
            />
          </svg>
        </span>
      </button>

      {showTooltip && (
        <div className="citation-tooltip">
          <div className="tooltip-header">
            <span className="tooltip-type">{citation.source.type.replace("_", " ")}</span>
            <span className="tooltip-relevance">
              {Math.round(citation.relevance_score * 100)}% relevante
            </span>
          </div>
          {citation.source.document_id && (
            <div className="tooltip-detail">Documento #{citation.source.document_id}</div>
          )}
          {citation.source.page && (
            <div className="tooltip-detail">Página {citation.source.page}</div>
          )}
          {citation.source.section && (
            <div className="tooltip-detail">Sección: {citation.source.section}</div>
          )}
          <div className="tooltip-hint">Clic para abrir fuente</div>
        </div>
      )}

      <style jsx>{`
        .citation-inline {
          position: relative;
          display: inline;
        }

        .citation-trigger {
          background: none;
          border: none;
          padding: 0;
          cursor: pointer;
          display: inline-flex;
          align-items: baseline;
          gap: 4px;
        }

        .citation-text {
          color: #1e40af;
          border-bottom: 1px dashed #3b82f6;
          font-style: italic;
        }

        .citation-badge {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 16px;
          height: 16px;
          background: #eff6ff;
          border-radius: 50%;
          color: #3b82f6;
          opacity: 0.7;
          transition: opacity 0.2s;
        }

        .citation-trigger:hover .citation-badge {
          opacity: 1;
        }

        .citation-trigger:hover .citation-text {
          color: #1d4ed8;
          border-bottom-color: #1d4ed8;
        }

        .citation-tooltip {
          position: absolute;
          bottom: 100%;
          left: 50%;
          transform: translateX(-50%);
          margin-bottom: 8px;
          padding: 12px;
          background: white;
          border: 1px solid var(--border);
          border-radius: 8px;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
          z-index: 50;
          min-width: 200px;
          max-width: 300px;
        }

        .tooltip-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
          padding-bottom: 8px;
          border-bottom: 1px solid var(--border);
        }

        .tooltip-type {
          font-size: 11px;
          font-weight: 600;
          text-transform: uppercase;
          color: var(--ink55);
        }

        .tooltip-relevance {
          font-size: 11px;
          color: var(--green);
          font-weight: 500;
        }

        .tooltip-detail {
          font-size: 13px;
          color: var(--ink2);
          margin-bottom: 4px;
        }

        .tooltip-hint {
          margin-top: 8px;
          padding-top: 8px;
          border-top: 1px solid var(--border);
          font-size: 11px;
          color: var(--ink38);
          text-align: center;
        }
      `}</style>
    </span>
  );
}

/**
 * Construye URL de navegación para una fuente de citación.
 */
function buildNavigationUrl(source: CitationSource): string {
  if (source.type === "document_chunk" && source.document_id) {
    const page = source.page || 1;
    return `/documents/${source.document_id}#page=${page}`;
  }
  if (source.type === "precedent" && source.id) {
    return `/precedents/${source.id}`;
  }
  if (source.type === "legal_source" && source.id) {
    return `/legal-sources/${source.id}`;
  }
  return "#";
}

interface CitationListProps {
  citations: Citation[];
  title?: string;
  onNavigate?: (citation: Citation) => void;
}

/**
 * Componente CitationList - Lista de citaciones con navegación.
 *
 * Muestra todas las citaciones del EvidenceBundle con sus fuentes.
 */
export function CitationList({ citations, title = "Fuentes", onNavigate }: CitationListProps) {
  if (!citations || citations.length === 0) {
    return null;
  }

  return (
    <div className="citation-list" aria-live="polite">
      <h4 className="citation-list-title">{title}</h4>
      <div className="citation-list-items">
        {citations.map((citation) => (
          <div key={citation.id} className="citation-item">
            <div className="citation-item-header">
              <span className="citation-item-id">{citation.id}</span>
              <span className="citation-item-type">
                {citation.source.type.replace("_", " ")}
              </span>
              <span className="citation-item-score">
                {Math.round(citation.relevance_score * 100)}%
              </span>
            </div>
            <blockquote className="citation-item-text">
              &ldquo;{citation.quoted_text}&rdquo;
            </blockquote>
            <div className="citation-item-meta">
              {citation.source.document_id && (
                <span>Doc #{citation.source.document_id}</span>
              )}
              {citation.source.page && <span>Pág. {citation.source.page}</span>}
              {citation.source.section && (
                <span>{citation.source.section}</span>
              )}
            </div>
            <button
              type="button"
              onClick={() => onNavigate?.(citation)}
              aria-label={`Abrir fuente: ${citation.source.type} (${Math.round(citation.relevance_score * 100)}% relevante) en nueva pestaña`}
              className="citation-item-link"
            >
              Ver fuente →
            </button>
          </div>
        ))}
      </div>

      <style jsx>{`
        .citation-list {
          margin-top: 24px;
          padding: 16px;
          background: var(--soft);
          border-radius: 8px;
        }

        .citation-list-title {
          font-size: 14px;
          font-weight: 600;
          color: var(--ink2);
          margin: 0 0 16px 0;
        }

        .citation-list-items {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .citation-item {
          padding: 12px;
          background: white;
          border: 1px solid var(--border);
          border-radius: 6px;
        }

        .citation-item-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 8px;
        }

        .citation-item-id {
          font-size: 11px;
          font-weight: 600;
          color: var(--ink55);
          background: #f3f4f6;
          padding: 2px 6px;
          border-radius: 4px;
        }

        .citation-item-type {
          font-size: 11px;
          color: var(--ink38);
          text-transform: capitalize;
        }

        .citation-item-score {
          margin-left: auto;
          font-size: 11px;
          color: var(--green);
          font-weight: 500;
        }

        .citation-item-text {
          font-size: 13px;
          color: var(--ink2);
          font-style: italic;
          margin: 0 0 8px 0;
          padding-left: 12px;
          border-left: 2px solid #d1d5db;
        }

        .citation-item-meta {
          display: flex;
          gap: 12px;
          font-size: 11px;
          color: var(--ink38);
        }

        .citation-item-link {
          margin-top: 8px;
          background: none;
          border: none;
          padding: 0;
          font-size: 12px;
          color: #3b82f6;
          cursor: pointer;
          text-align: left;
        }

        .citation-item-link:hover {
          text-decoration: underline;
        }
      `}</style>
    </div>
  );
}

/**
 * HTML / PDF generator for the document analysis view.
 *
 * Extracted from `components/document-analysis-view.tsx` so the view
 * itself only owns the React UI and this module owns the printable
 * report. The escaping helpers live here too so we don't ship the
 * XSS surface across files.
 */

interface Participant {
  company: string;
  rut?: string;
  representative?: string;
  representative_rut?: string;
  role: string;
}

interface Obligation {
  party: string;
  description: string;
}

interface RiskAssessment {
  risk_level: string;
  clause_type?: string;
  risk_score?: number;
  explanation?: string;
  industry_standard?: string;
  recommendation?: string;
  suggested_clause?: string;
}

interface ContractTimelineItem {
  type: string;
  event?: string;
  date?: string;
  description?: string;
  consequence?: string;
  days_from_signing?: number;
}

export interface AnalysisReportPayload {
  document_type?: string;
  participants?: Participant[];
  obligations?: Obligation[];
  risk_assessment?: RiskAssessment[];
  contract_timeline?: ContractTimelineItem[];
}

// ---------------------------------------------------------------------------
// XSS-safe rendering helpers (S0-05). The legacy `document.write` approach
// trusted any string returned by the LLM / RAG pipeline; both helpers below
// are pure functions of plain inputs so they can be unit-tested without a
// DOM.
// ---------------------------------------------------------------------------

const HTML_ESCAPE_MAP: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

export function escapeHtml(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value).replace(/[&<>"']/g, (ch) => HTML_ESCAPE_MAP[ch] ?? ch);
}

export function escapeColor(value: unknown, fallback: string): string {
  const raw = typeof value === "string" ? value : "";
  return /^#[0-9a-fA-F]{3,8}$/.test(raw) ? raw : fallback;
}

// ---------------------------------------------------------------------------
// Render helpers (S4-02 split out from document-analysis-view.tsx)
// ---------------------------------------------------------------------------

function renderParticipants(participants: Participant[] | undefined): string {
  if (!participants || participants.length === 0) {
    return '<p style="color: #6b7280;">No hay participantes identificados.</p>';
  }
  return participants
    .map((p) => {
      const isContratante = p.role === "contratante";
      const roleBg = isContratante ? "#ede9fe" : "#dbeafe";
      const roleColor = isContratante ? "#6b21a8" : "#1e40af";
      return `
      <div style="padding: 12px; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; margin-bottom: 12px;">
        <div style="display: flex; justify-content: space-between; align-items: start;">
          <div>
            <p style="font-weight: 600; color: #111827; margin: 0 0 4px 0;">${escapeHtml(p.company || "-")}</p>
            ${p.rut ? `<p style="color: #6b7280; font-size: 12px; margin: 0;">RUT: ${escapeHtml(p.rut)}</p>` : ""}
          </div>
          <span style="padding: 4px 12px; font-size: 12px; font-weight: 500; border-radius: 9999px; background: ${escapeColor(roleBg, "#dbeafe")}; color: ${escapeColor(roleColor, "#1e40af")};">${escapeHtml(p.role)}</span>
        </div>
        ${p.representative
          ? `
          <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #e5e7eb;">
            <p style="color: #374151; font-size: 13px; margin: 0;">Representante: ${escapeHtml(p.representative)}</p>
            ${p.representative_rut
              ? `<p style="color: #6b7280; font-size: 11px; margin: 0;">RUT: ${escapeHtml(p.representative_rut)}</p>`
              : ""}
          </div>
        `
          : ""}
      </div>
    `;
    })
    .join("");
}

function renderRisks(risks: RiskAssessment[] | undefined): string {
  if (!risks || risks.length === 0) {
    return '<p style="color: #6b7280;">No hay riesgos evaluados.</p>';
  }
  return risks
    .map((r) => {
      const level = r.risk_level === "high" ? "high" : r.risk_level === "medium" ? "medium" : "low";
      const bg = level === "high" ? "#fef2f2" : level === "medium" ? "#fefce8" : "#f0fdf4";
      const border = level === "high" ? "#dc2626" : level === "medium" ? "#ca8a04" : "#16a34a";
      const score =
        typeof r.risk_score === "number" && Number.isFinite(r.risk_score)
          ? r.risk_score
          : "-";
      return `
      <div style="padding: 16px; background: ${bg}; border-left: 4px solid ${border}; margin-bottom: 16px; border-radius: 0 8px 8px 0;">
        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="padding: 4px 8px; font-size: 11px; font-weight: 700; border-radius: 4px; background: ${border}; color: white;">${escapeHtml(level.toUpperCase())}</span>
            <span style="color: #374151; font-weight: 500;">${escapeHtml(r.clause_type || "-")}</span>
          </div>
          <span style="font-size: 24px; font-weight: 700; color: #111827;">${escapeHtml(score)}<span style="font-size: 14px; color: #6b7280;">/100</span></span>
        </div>
        <p style="color: #4b5563; margin: 0 0 12px 0;">${escapeHtml(r.explanation || "-")}</p>
        ${r.industry_standard
          ? `<p style="color: #374151; font-size: 13px; margin: 0 0 8px 0;"><strong>Estándar del sector:</strong> ${escapeHtml(r.industry_standard)}</p>`
          : ""}
        ${r.recommendation
          ? `<p style="color: #1e40af; font-size: 13px; margin: 0 0 8px 0;"><strong>Recomendación:</strong> ${escapeHtml(r.recommendation)}</p>`
          : ""}
        ${r.suggested_clause
          ? `<div style="background: white; padding: 12px; border-radius: 6px; margin-top: 8px;"><p style="color: #065f46; font-size: 13px; font-style: italic; margin: 0;">&ldquo;${escapeHtml(r.suggested_clause)}&rdquo;</p></div>`
          : ""}
      </div>
    `;
    })
    .join("");
}

function renderTimeline(timeline: ContractTimelineItem[] | undefined): string {
  if (!timeline || timeline.length === 0) {
    return '<p style="color: #6b7280;">No hay timeline disponible.</p>';
  }
  return timeline
    .map((t, idx) => {
      const typeBg = t.type === "inicio" ? "#22c55e" : t.type === "termino" ? "#ef4444" : "#eab308";
      const days =
        typeof t.days_from_signing === "number" && Number.isFinite(t.days_from_signing)
          ? t.days_from_signing
          : null;
      return `
      <div style="display: flex; gap: 16px; margin-bottom: 16px;">
        <div style="display: flex; flex-direction: column; align-items: center;">
          <div style="width: 12px; height: 12px; border-radius: 50%; background: ${escapeColor(typeBg, "#eab308")}; margin-top: 4px;"></div>
          ${idx < (timeline?.length || 0) - 1 ? '<div style="width: 2px; flex: 1; background: #d1d5db; margin-top: 4px;"></div>' : ""}
        </div>
        <div style="flex: 1; padding-bottom: 16px;">
          <div style="display: flex; justify-content: space-between; align-items: start;">
            <p style="font-weight: 600; color: #111827; margin: 0;">${escapeHtml(t.event || "-")}</p>
            ${days !== null
              ? `<span style="padding: 2px 8px; font-size: 11px; font-weight: 500; background: #e0e7ff; color: #3730a3; border-radius: 9999px;">Día ${escapeHtml(days)}</span>`
              : ""}
          </div>
          <p style="color: #4b5563; font-size: 13px; margin: 4px 0 0 0;">${escapeHtml(t.date || "-")}</p>
          ${t.description
            ? `<p style="color: #374151; font-size: 13px; margin: 8px 0 0 0;">${escapeHtml(t.description)}</p>`
            : ""}
          ${t.consequence
            ? `<p style="color: #dc2626; font-size: 12px; font-weight: 500; margin: 8px 0 0 0;">⚠️ ${escapeHtml(t.consequence)}</p>`
            : ""}
        </div>
      </div>
    `;
    })
    .join("");
}

const REPORT_TEMPLATE = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="UTF-8">
        <title>Análisis de Documento - __DOC_TYPE__</title>
        <style>
          * { box-sizing: border-box; }
          body { font-family: 'Segoe UI', Arial, sans-serif; padding: 40px; max-width: 800px; margin: 0 auto; color: #111827; line-height: 1.5; }
          h1 { font-size: 24px; color: #111827; margin: 0 0 8px 0; }
          h2 { font-size: 18px; color: #111827; margin: 32px 0 16px 0; padding-bottom: 8px; border-bottom: 2px solid #e5e7eb; }
          h3 { font-size: 15px; color: #374151; margin: 0 0 12px 0; }
          .header { border-bottom: 2px solid #3b82f6; padding-bottom: 16px; margin-bottom: 24px; }
          .doc-type { display: inline-block; padding: 6px 16px; background: #eff6ff; color: #1d4ed8; border-radius: 9999px; font-size: 14px; font-weight: 500; margin-top: 8px; }
          .section { margin-bottom: 24px; }
          .risk-box { padding: 16px; border-radius: 8px; margin-bottom: 12px; }
          .note { background: #f3f4f6; padding: 16px; border-radius: 8px; font-size: 12px; color: #4b5563; margin-top: 40px; }
          .obligations { margin-top: 12px; }
          .obligation { padding: 12px; background: #f9fafb; border-radius: 8px; margin-bottom: 8px; }
          .obligation-party { font-weight: 600; color: #374151; margin-bottom: 4px; }
          .obligation-desc { color: #6b7280; font-size: 13px; margin: 0; }
          @media print {
            body { padding: 20px; }
            .no-print { display: none; }
          }
        </style>
      </head>
      <body>
        <div class="header">
          <h1>Análisis de Documento</h1>
          <span class="doc-type">__DOC_TYPE__</span>
        </div>

        <div class="section">
          <h2>👥 Participantes Identificados</h2>
          __PARTICIPANTS__
        </div>

        __OBLIGATIONS__

        <div class="section">
          <h2>⚠️ Evaluación de Riesgo por Cláusula</h2>
          __RISKS__
        </div>

        <div class="section">
          <h2>📅 Línea de Tiempo del Contrato</h2>
          __TIMELINE__
        </div>

        <div class="note">
          <strong>Nota legal:</strong> Este análisis es preliminar y basado en IA. No reemplaza la revisión profesional de un abogado habilitado en Chile.
        </div>
      </body>
      </html>
    `;

/** Public entry point used by the React view. */
export function generateStyledHTML(analysis: AnalysisReportPayload): string {
  const docType = escapeHtml(analysis.document_type || "Documento");

  const obligationsHtml = analysis.obligations?.length
    ? `
        <div class="section">
          <h2>📋 Obligaciones</h2>
          <div class="obligations">
            ${analysis.obligations
              .map(
                (o) => `
              <div class="obligation">
                <p class="obligation-party">${escapeHtml(o.party || "-")}</p>
                <p class="obligation-desc">${escapeHtml(o.description || "-")}</p>
              </div>
            `,
              )
              .join("")}
          </div>
        </div>
        `
    : "";

  return REPORT_TEMPLATE
    .replace("__DOC_TYPE__", docType)
    .replace("__DOC_TYPE__", docType)
    .replace("__PARTICIPANTS__", renderParticipants(analysis.participants))
    .replace("__OBLIGATIONS__", obligationsHtml)
    .replace("__RISKS__", renderRisks(analysis.risk_assessment))
    .replace("__TIMELINE__", renderTimeline(analysis.contract_timeline));
}

/**
 * Open a print window with the styled HTML and trigger the system print
 * dialog. Kept here so the React component only owns the trigger button.
 */
export function openPrintableReport(analysis: AnalysisReportPayload): void {
  const content = generateStyledHTML(analysis);
  const printWindow = window.open("", "_blank");
  if (!printWindow) return;
  printWindow.document.write(content);
  printWindow.document.close();
  printWindow.focus();
  printWindow.print();
}
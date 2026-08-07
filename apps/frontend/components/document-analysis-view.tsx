"use client";

import { useState } from "react";

/**
 * HTML-escape user-derived strings before interpolating them into the
 * printable report. This is the S0-05 fix: ``document.write`` would
 * otherwise execute any ``<script>`` or event-handler payload that the
 * upstream document analysis introduced via an injected participant
 * name, risk explanation, or clause text.
 */
const HTML_ESCAPE_MAP: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

function escapeHtml(value: unknown): string {
  if (value === null || value === undefined) return "";
  const str = String(value);
  return str.replace(/[&<>"']/g, (ch) => HTML_ESCAPE_MAP[ch] ?? ch);
}

/** Allow only known-safe CSS color literals or numeric risk scores. */
function escapeColor(value: unknown, fallback: string): string {
  const raw = typeof value === "string" ? value : "";
  return /^#[0-9a-fA-F]{3,8}$/.test(raw) ? raw : fallback;
}

interface Participant {
  company: string;
  rut?: string;
  representative?: string;
  representative_rut?: string;
  role: string;
  verified?: boolean;
}

interface Obligation {
  party: string;
  description: string;
  deadline?: string;
}

interface ClauseGroup {
  clause_type: string;
  summary: string;
  details?: string;
}

interface UnusualClause {
  clause: string;
  risk_level: string;
  explanation: string;
  risk_score?: number;
  recommendation?: string;
}

interface RiskAssessment {
  clause_type: string;
  clause_text: string;
  risk_level: "high" | "medium" | "low";
  risk_score: number;
  explanation: string;
  industry_standard?: string;
  recommendation: string;
  suggested_clause?: string;
}

interface ContractTimelineItem {
  event: string;
  date: string;
  days_from_signing?: number;
  type: string;
  description: string;
  consequence?: string;
  legal_reference?: string;
}

interface DocumentAnalysisViewProps {
  analysis: {
    document_type?: string;
    participants?: Participant[];
    financial_terms?: Record<string, any>;
    obligations?: Obligation[];
    clauses_by_type?: Record<string, ClauseGroup[]>;
    unusual_clauses?: UnusualClause[];
    legal_references?: { article: string; description: string; relevance: string }[];
    risk_assessment?: RiskAssessment[];
    contract_timeline?: ContractTimelineItem[];
  };
}

const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  identity_card: "Cédula de Identidad",
  contract: "Contrato",
  company_certificate: "Certificado de Empresa",
  pay_slip: "Liquidación de Sueldo",
  birth_certificate: "Certificado de Nacimiento",
  family_registry: "Registro de Familia",
  receipt: "Comprobante de Pago",
  legal_proceeding: "Procedimiento Legal",
  property_registry: "Registro de Propiedad",
  consent_form: "Formulario de Consentimiento",
  correspondence: "Correspondencia",
  bylaws: "Estatutos",
  power_of_attorney: "Poder Notarial",
  debt_instrument: "Instrumento de Deuda",
  unknown: "Tipo Desconocido"
};

const RISK_LEVEL_COLORS: Record<string, string> = {
  low: "bg-green-pale text-green",
  medium: "bg-amber-pale text-amber",
  high: "bg-coral-pale text-coral-dark",
  critical: "bg-coral-pale text-coral"
};

const RISK_LEVEL_BAR_COLORS: Record<string, string> = {
  low: "bg-green",
  medium: "bg-amber",
  high: "bg-coral",
  critical: "bg-coral-dark"
};

function RiskScoreBar({ score, level }: { score: number; level: string }) {
  const width = Math.min(100, Math.max(0, score));
  const colorClass = RISK_LEVEL_BAR_COLORS[level] || "bg-ink/40";

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-soft rounded-full overflow-hidden">
        <div
          className={`h-full ${colorClass} transition-all duration-500`}
          style={{ width: `${width}%` }}
        />
      </div>
      <span className="text-sm font-medium text-ink min-w-[3rem] text-right">
        {score}/100
      </span>
    </div>
  );
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className="text-xs flex items-center gap-1 px-2 py-1 bg-soft hover:bg-border rounded transition-colors"
      title="Copiar texto"
    >
      {copied ? (
        <>
          <svg className="w-3 h-3 text-green" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <span className="text-green">Copiado</span>
        </>
      ) : (
        <>
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          <span>{label}</span>
        </>
      )}
    </button>
  );
}

export function DocumentAnalysisView({ analysis }: DocumentAnalysisViewProps) {
  const getDocTypeLabel = (docType: string) => {
    return DOCUMENT_TYPE_LABELS[docType] || docType;
  };

  const handlePrint = () => {
    window.print();
  };

  const handleDownloadPDF = () => {
    // Generate styled HTML for PDF
    const content = generateStyledHTML();
    const printWindow = window.open('', '_blank');
    if (printWindow) {
      printWindow.document.write(content);
      printWindow.document.close();
      printWindow.focus();
      printWindow.print();
    }
  };

  const generateStyledHTML = () => {
    const participantsHTML = analysis.participants?.map((p) => {
      const isContratante = p.role === "contratante";
      const roleBg = isContratante ? "#ede9fe" : "#dbeafe";
      const roleColor = isContratante ? "#6b21a8" : "#1e40af";
      return `
      <div style="padding: 12px; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; margin-bottom: 12px;">
        <div style="display: flex; justify-content: space-between; align-items: start;">
          <div>
            <p style="font-weight: 600; color: #111827; margin: 0 0 4px 0;">${escapeHtml(p.company || '-')}</p>
            ${p.rut ? `<p style="color: #6b7280; font-size: 12px; margin: 0;">RUT: ${escapeHtml(p.rut)}</p>` : ''}
          </div>
          <span style="padding: 4px 12px; font-size: 12px; font-weight: 500; border-radius: 9999px; background: ${escapeColor(roleBg, '#dbeafe')}; color: ${escapeColor(roleColor, '#1e40af')};">${escapeHtml(p.role)}</span>
        </div>
        ${p.representative ? `
          <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #e5e7eb;">
            <p style="color: #374151; font-size: 13px; margin: 0;">Representante: ${escapeHtml(p.representative)}</p>
            ${p.representative_rut ? `<p style="color: #6b7280; font-size: 11px; margin: 0;">RUT: ${escapeHtml(p.representative_rut)}</p>` : ''}
          </div>
        ` : ''}
      </div>
    `;
    }).join('') || '<p style="color: #6b7280;">No hay participantes identificados.</p>';

    const risksHTML = analysis.risk_assessment?.map((r) => {
      const level = r.risk_level === "high" ? "high" : r.risk_level === "medium" ? "medium" : "low";
      const bg = level === "high" ? "#fef2f2" : level === "medium" ? "#fefce8" : "#f0fdf4";
      const border = level === "high" ? "#dc2626" : level === "medium" ? "#ca8a04" : "#16a34a";
      const score = typeof r.risk_score === "number" && Number.isFinite(r.risk_score) ? r.risk_score : "-";
      return `
      <div style="padding: 16px; background: ${bg}; border-left: 4px solid ${border}; margin-bottom: 16px; border-radius: 0 8px 8px 0;">
        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="padding: 4px 8px; font-size: 11px; font-weight: 700; border-radius: 4px; background: ${border}; color: white;">${escapeHtml(level.toUpperCase())}</span>
            <span style="color: #374151; font-weight: 500;">${escapeHtml(r.clause_type || '-')}</span>
          </div>
          <span style="font-size: 24px; font-weight: 700; color: #111827;">${escapeHtml(score)}<span style="font-size: 14px; color: #6b7280;">/100</span></span>
        </div>
        <p style="color: #4b5563; margin: 0 0 12px 0;">${escapeHtml(r.explanation || '-')}</p>
        ${r.industry_standard ? `<p style="color: #374151; font-size: 13px; margin: 0 0 8px 0;"><strong>Estándar del sector:</strong> ${escapeHtml(r.industry_standard)}</p>` : ''}
        ${r.recommendation ? `<p style="color: #1e40af; font-size: 13px; margin: 0 0 8px 0;"><strong>Recomendación:</strong> ${escapeHtml(r.recommendation)}</p>` : ''}
        ${r.suggested_clause ? `<div style="background: white; padding: 12px; border-radius: 6px; margin-top: 8px;"><p style="color: #065f46; font-size: 13px; font-style: italic; margin: 0;">&ldquo;${escapeHtml(r.suggested_clause)}&rdquo;</p></div>` : ''}
      </div>
    `;
    }).join('') || '<p style="color: #6b7280;">No hay riesgos evaluados.</p>';

    const timelineHTML = analysis.contract_timeline?.map((t, idx) => {
      const typeBg = t.type === 'inicio' ? '#22c55e' : t.type === 'termino' ? '#ef4444' : '#eab308';
      const days = typeof t.days_from_signing === 'number' && Number.isFinite(t.days_from_signing)
        ? t.days_from_signing
        : null;
      return `
      <div style="display: flex; gap: 16px; margin-bottom: 16px;">
        <div style="display: flex; flex-direction: column; align-items: center;">
          <div style="width: 12px; height: 12px; border-radius: 50%; background: ${escapeColor(typeBg, '#eab308')}; margin-top: 4px;"></div>
          ${idx < (analysis.contract_timeline?.length || 0) - 1 ? '<div style="width: 2px; flex: 1; background: #d1d5db; margin-top: 4px;"></div>' : ''}
        </div>
        <div style="flex: 1; padding-bottom: 16px;">
          <div style="display: flex; justify-content: space-between; align-items: start;">
            <p style="font-weight: 600; color: #111827; margin: 0;">${escapeHtml(t.event || '-')}</p>
            ${days !== null ? `<span style="padding: 2px 8px; font-size: 11px; font-weight: 500; background: #e0e7ff; color: #3730a3; border-radius: 9999px;">Día ${escapeHtml(days)}</span>` : ''}
          </div>
          <p style="color: #4b5563; font-size: 13px; margin: 4px 0 0 0;">${escapeHtml(t.date || '-')}</p>
          ${t.description ? `<p style="color: #374151; font-size: 13px; margin: 8px 0 0 0;">${escapeHtml(t.description)}</p>` : ''}
          ${t.consequence ? `<p style="color: #dc2626; font-size: 12px; font-weight: 500; margin: 8px 0 0 0;">⚠️ ${escapeHtml(t.consequence)}</p>` : ''}
        </div>
      </div>
    `;
    }).join('') || '<p style="color: #6b7280;">No hay timeline disponible.</p>';

    return `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="UTF-8">
        <title>Análisis de Documento - ${escapeHtml(analysis.document_type || 'Legal')}</title>
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
          <span class="doc-type">${escapeHtml(analysis.document_type || 'Documento')}</span>
        </div>

        <div class="section">
          <h2>👥 Participantes Identificados</h2>
          ${participantsHTML}
        </div>

        ${analysis.obligations?.length ? `
        <div class="section">
          <h2>📋 Obligaciones</h2>
          <div class="obligations">
            ${analysis.obligations.map((o) => `
              <div class="obligation">
                <p class="obligation-party">${escapeHtml(o.party || '-')}</p>
                <p class="obligation-desc">${escapeHtml(o.description || '-')}</p>
              </div>
            `).join('')}
          </div>
        </div>
        ` : ''}

        <div class="section">
          <h2>⚠️ Evaluación de Riesgo por Cláusula</h2>
          ${risksHTML}
        </div>

        <div class="section">
          <h2>📅 Línea de Tiempo del Contrato</h2>
          ${timelineHTML}
        </div>

        <div class="note">
          <strong>Nota legal:</strong> Este análisis es preliminar y basado en IA. No reemplaza la revisión profesional de un abogado habilitado en Chile.
        </div>
      </body>
      </html>
    `;
  };

  return (
    <div className="space-y-6" id="analysis-content">
      {/* Header with Print/PDF buttons */}
      <div className="flex items-center justify-between mb-4">
        <div>
          {analysis.document_type && (
            <div className="p-4 bg-blue-pale rounded-lg border border-blue/20">
              <h3 className="font-semibold text-blue mb-1">Tipo de Documento</h3>
              <p className="text-blue">{getDocTypeLabel(analysis.document_type)}</p>
            </div>
          )}
        </div>
        <div className="flex gap-2 no-print">
          <button
            onClick={handlePrint}
            className="flex items-center gap-2 px-4 py-2 bg-soft hover:bg-border text-ink2 rounded-lg transition-colors text-sm font-medium"
            title="Imprimir análisis"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6m-6-4V9a2 2 0 012-2h2a2 2 0 012 2v8m-6 0h6" />
            </svg>
            Imprimir
          </button>
          <button
            onClick={handleDownloadPDF}
            className="flex items-center gap-2 px-4 py-2 bg-ink hover:bg-ink/90 text-white rounded-lg transition-colors text-sm font-medium"
            title="Descargar como PDF"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Descargar PDF
          </button>
        </div>
      </div>

      {/* Participants */}
      {analysis.participants && analysis.participants.length > 0 && (
        <div>
          <h3 className="font-semibold text-ink mb-3 flex items-center gap-2">
            <svg className="w-5 h-5 text-purple" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
            Participantes Identificados
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {analysis.participants.map((participant, idx) => (
              <div key={idx} className="p-4 bg-soft rounded-lg border border-border">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium text-ink">{participant.company}</p>
                    {participant.rut && (
                      <p className="text-xs text-ink/60">RUT: {participant.rut}</p>
                    )}
                  </div>
                  <span className={`px-2 py-1 text-xs font-medium rounded ${
                    participant.role === 'contratante' ? 'bg-purple-pale text-purple' :
                    participant.role === 'contratista' ? 'bg-blue-pale text-blue' :
                    'bg-soft text-ink'
                  }`}>
                    {participant.role}
                  </span>
                </div>
                {participant.representative && (
                  <div className="mt-2 pt-2 border-t border-border">
                    <p className="text-sm text-ink2">
                      <span className="font-medium">Representante:</span> {participant.representative}
                    </p>
                    {participant.representative_rut && (
                      <p className="text-xs text-ink/60">RUT: {participant.representative_rut}</p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Financial Terms */}
      {analysis.financial_terms && Object.keys(analysis.financial_terms).length > 0 && (
        <div>
          <h3 className="font-semibold text-slate-900 mb-3 flex items-center gap-2">
            <svg className="w-5 h-5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Términos Financieros
          </h3>
          <div className="space-y-2">
            {Object.entries(analysis.financial_terms).map(([key, value]: [string, any]) => (
              <div key={key} className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex justify-between">
                <span className="text-slate-700">{key}</span>
                <span className="font-medium text-slate-900">
                  {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Obligations */}
      {analysis.obligations && analysis.obligations.length > 0 && (
        <div>
          <h3 className="font-semibold text-slate-900 mb-3 flex items-center gap-2">
            <svg className="w-5 h-5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            Obligaciones
          </h3>
          <div className="space-y-3">
            {analysis.obligations.map((obligation, idx) => (
              <div key={idx} className="p-4 bg-amber-50 rounded-lg border border-amber-200">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-amber-900">{obligation.party}</p>
                    <p className="text-sm text-amber-800 mt-1">{obligation.description}</p>
                  </div>
                  {obligation.deadline && (
                    <span className="px-2 py-1 text-xs font-medium rounded bg-amber-200 text-amber-900">
                      {obligation.deadline}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Risk Assessment - Nueva sección principal */}
      {analysis.risk_assessment && analysis.risk_assessment.length > 0 && (
        <div>
          <h3 className="font-semibold text-slate-900 mb-3 flex items-center gap-2">
            <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            Evaluación de Riesgo por Cláusula
          </h3>
          <div className="space-y-4">
            {analysis.risk_assessment.map((risk, idx) => (
              <div key={idx} className={`border rounded-lg overflow-hidden ${
                risk.risk_level === 'high' ? 'border-red-200 bg-red-50' :
                risk.risk_level === 'medium' ? 'border-amber-200 bg-amber-50' :
                'border-emerald-200 bg-emerald-50'
              }`}>
                <div className="p-4">
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                          RISK_LEVEL_COLORS[risk.risk_level] || "bg-slate-100 text-slate-800"
                        }`}>
                          {risk.risk_level?.toUpperCase()}
                        </span>
                        <span className="text-sm font-medium text-slate-700">{risk.clause_type}</span>
                      </div>
                      <p className="text-sm text-ink2 mt-2">{risk.explanation}</p>
                    </div>
                    <div className="text-right">
                      <span className="text-xl font-bold text-ink">{risk.risk_score}</span>
                      <span className="text-sm text-ink/60">/100</span>
                    </div>
                  </div>

                  <RiskScoreBar score={risk.risk_score} level={risk.risk_level} />

                  {risk.industry_standard && (
                    <div className="mt-3 p-2 bg-white rounded border border-slate-200">
                      <p className="text-xs text-slate-500 mb-1">Estándar del sector:</p>
                      <p className="text-sm text-slate-700">{risk.industry_standard}</p>
                    </div>
                  )}

                  {risk.recommendation && (
                    <div className="mt-3 p-2 bg-sky-50 rounded border border-sky-200">
                      <p className="text-xs text-sky-600 font-medium mb-1">Recomendación de negociación:</p>
                      <p className="text-sm text-sky-800">{risk.recommendation}</p>
                    </div>
                  )}

                  {risk.suggested_clause && (
                    <div className="mt-3">
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-xs text-slate-500">Texto alternativo sugerido:</p>
                        <CopyButton text={risk.suggested_clause} label="Copiar" />
                      </div>
                      <div className="p-2 bg-white rounded border border-emerald-200">
                        <p className="text-sm text-slate-700 italic">"{risk.suggested_clause}"</p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Contract Timeline */}
      {analysis.contract_timeline && analysis.contract_timeline.length > 0 && (
        <div>
          <h3 className="font-semibold text-slate-900 mb-3 flex items-center gap-2">
            <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            Línea de Tiempo del Contrato
          </h3>
          <div className="space-y-4">
            {analysis.contract_timeline.map((item, idx) => (
              <div key={idx} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <div className={`w-3 h-3 rounded-full mt-1.5 ${
                    item.type === 'inicio' ? 'bg-emerald-500' :
                    item.type === 'termino' ? 'bg-red-500' :
                    item.type === 'aviso' ? 'bg-amber-500' :
                    item.type === 'pago' ? 'bg-sky-500' :
                    'bg-indigo-500'
                  }`}></div>
                  {idx < (analysis.contract_timeline?.length ?? 0) - 1 && <div className="w-0.5 flex-1 bg-indigo-200 mt-1"></div>}
                </div>
                <div className="flex-1 pb-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium text-slate-900">{item.event}</p>
                      {item.date && <p className="text-sm text-indigo-600">{item.date}</p>}
                    </div>
                    {item.days_from_signing !== undefined && (
                      <span className="px-2 py-1 text-xs font-medium rounded bg-indigo-100 text-indigo-800">
                        Día {item.days_from_signing}
                      </span>
                    )}
                  </div>
                  {item.description && (
                    <p className="text-sm text-slate-600 mt-1">{item.description}</p>
                  )}
                  {item.consequence && (
                    <p className="text-sm text-red-600 mt-2 font-medium">
                      ⚠️ {item.consequence}
                    </p>
                  )}
                  {item.legal_reference && (
                    <p className="text-xs text-slate-500 mt-1 italic">{item.legal_reference}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Unusual Clauses - Ahora con scoring */}
      {analysis.unusual_clauses && analysis.unusual_clauses.length > 0 && (
        <div>
          <h3 className="font-semibold text-slate-900 mb-3 flex items-center gap-2">
            <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            Cláusulas Atípicas Detectadas
          </h3>
          <div className="space-y-3">
            {analysis.unusual_clauses.map((clause, idx) => (
              <div key={idx} className="p-4 bg-red-50 rounded-lg border border-red-200">
                <div className="flex items-start justify-between gap-3 mb-2">
                  <p className="font-medium text-red-900 flex-1">{clause.clause}</p>
                  <div className="flex items-center gap-2">
                    {clause.risk_score && (
                      <span className="text-sm font-medium text-slate-700">{clause.risk_score}/100</span>
                    )}
                    <span className={`px-2 py-1 text-xs font-medium rounded ${RISK_LEVEL_COLORS[clause.risk_level] || "bg-slate-100 text-slate-800"}`}>
                      {clause.risk_level?.toUpperCase()}
                    </span>
                  </div>
                </div>
                <p className="text-sm text-red-800">{clause.explanation}</p>
                {clause.risk_score && (
                  <div className="mt-2">
                    <RiskScoreBar score={clause.risk_score} level={clause.risk_level} />
                  </div>
                )}
                {clause.recommendation && (
                  <p className="text-sm text-sky-700 mt-2">
                    <span className="font-medium">Recomendación:</span> {clause.recommendation}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Legal References */}
      {analysis.legal_references && analysis.legal_references.length > 0 && (
        <div>
          <h3 className="font-semibold text-slate-900 mb-3 flex items-center gap-2">
            <svg className="w-5 h-5 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            Referencias Legales
          </h3>
          <div className="space-y-3">
            {analysis.legal_references.map((ref, idx) => (
              <div key={idx} className="p-4 bg-sky-50 rounded-lg border border-sky-200">
                <p className="font-medium text-sky-900">{ref.article}</p>
                <p className="text-sm text-sky-800 mt-1">{ref.description}</p>
                {ref.relevance && (
                  <p className="text-xs text-sky-600 mt-1">Relevancia: {ref.relevance}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* No analysis data */}
      {!analysis.document_type && !analysis.participants?.length && !analysis.financial_terms && !analysis.obligations?.length && !analysis.clauses_by_type && !analysis.unusual_clauses?.length && !analysis.legal_references?.length && !analysis.risk_assessment?.length && (
        <div className="text-center py-8 text-slate-500">
          <p>No hay datos de análisis disponibles.</p>
        </div>
      )}

      <div className="mt-6 p-4 bg-slate-100 rounded-lg border border-slate-200">
        <p className="text-xs text-slate-600">
          <strong>Nota:</strong> Este análisis es preliminar y basado en IA. No reemplaza la revisión profesional de un abogado habilitado en Chile.
        </p>
      </div>

      {/* Print-only note */}
      <div className="hidden print:block mt-6 p-4 bg-slate-100 rounded-lg border border-slate-200">
        <p className="text-xs text-slate-600">
          <strong>Nota legal:</strong> Este análisis es preliminar y no reemplaza la revisión profesional de un abogado habilitado en Chile.
        </p>
      </div>
    </div>
  );
}


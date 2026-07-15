"use client";

import { useState } from "react";

interface ValidationSummary {
  total_documents: number;
  document_types_found: Record<string, number>;
  required_types: string[];
  required_found: string[];
  required_missing: string[];
  recommended_found: string[];
  recommended_missing: string[];
  total_inconsistencies: number;
  errors: number;
  warnings: number;
}

interface Document {
  id: number;
  original_filename: string;
  detected_document_type: string | null;
  status: string;
  created_at: string;
}

interface DocumentStatusProps {
  documents: Document[];
  validationSummary?: ValidationSummary | null;
  matterType: string;
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

const MATTER_TYPE_LABELS: Record<string, string> = {
  contract_review: "Revisión de Contrato",
  lease: "Arriendo",
  labor: "Laboral",
  company: "Empresas",
  data_protection: "Protección de Datos",
  consumer: "Consumidor",
  family: "Familia",
  debt: "Deudas",
  other: "Otro"
};

export function DocumentStatus({ documents, validationSummary, matterType }: DocumentStatusProps) {
  const [expanded, setExpanded] = useState(false);

  const getLabel = (docType: string | null) => {
    if (!docType) return DOCUMENT_TYPE_LABELS["unknown"];
    return DOCUMENT_TYPE_LABELS[docType] || docType;
  };

  const matterLabel = MATTER_TYPE_LABELS[matterType] || matterType;

  return (
    <div className="bg-white rounded-xl shadow-sm border p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Estado de Documentos</h3>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-sm text-primary-600 hover:text-primary-700"
        >
          {expanded ? "Ocultar detalles" : "Ver detalles"}
        </button>
      </div>

      {validationSummary && (
        <div className="mb-4">
          {/* Summary badges */}
          <div className="flex gap-3 flex-wrap">
            {validationSummary.errors > 0 && (
              <span className="px-3 py-1 text-sm font-medium rounded-full bg-red-100 text-red-800">
                {validationSummary.errors} error{validationSummary.errors !== 1 ? "es" : ""}
              </span>
            )}
            {validationSummary.warnings > 0 && (
              <span className="px-3 py-1 text-sm font-medium rounded-full bg-yellow-100 text-yellow-800">
                {validationSummary.warnings} advertencia{validationSummary.warnings !== 1 ? "s" : ""}
              </span>
            )}
            {validationSummary.required_missing.length > 0 && (
              <span className="px-3 py-1 text-sm font-medium rounded-full bg-orange-100 text-orange-800">
                {validationSummary.required_missing.length} documento{validationSummary.required_missing.length !== 1 ? "s" : ""} requerido{validationSummary.required_missing.length !== 1 ? "s" : ""} faltante{validationSummary.required_missing.length !== 1 ? "s" : ""}
              </span>
            )}
            {validationSummary.errors === 0 && validationSummary.warnings === 0 && validationSummary.required_missing.length === 0 && (
              <span className="px-3 py-1 text-sm font-medium rounded-full bg-green-100 text-green-800">
                ✓ Documentación completa
              </span>
            )}
          </div>
        </div>
      )}

      {/* Document types found */}
      {validationSummary && validationSummary.document_types_found && Object.keys(validationSummary.document_types_found).length > 0 && (
        <div className="mb-4">
          <h4 className="text-sm font-medium text-gray-700 mb-2">Tipos de documentos detectados:</h4>
          <div className="flex gap-2 flex-wrap">
            {Object.entries(validationSummary.document_types_found).map(([docType, count]) => (
              <span
                key={docType}
                className="px-2 py-1 text-xs font-medium rounded bg-gray-100 text-gray-700"
              >
                {getLabel(docType)} ({count})
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Missing required documents */}
      {validationSummary && validationSummary.required_missing.length > 0 && (
        <div className="mb-4 p-3 bg-orange-50 border border-orange-200 rounded-lg">
          <h4 className="text-sm font-medium text-orange-900 mb-2 flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            Documentos requeridos faltantes
          </h4>
          <ul className="text-sm text-orange-800 space-y-1">
            {validationSummary.required_missing.map((docType) => (
              <li key={docType}>• {getLabel(docType)}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Missing recommended documents */}
      {validationSummary && validationSummary.recommended_missing.length > 0 && (
        <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <h4 className="text-sm font-medium text-blue-900 mb-2">Documentos recomendados faltantes</h4>
          <ul className="text-sm text-blue-800 space-y-1">
            {validationSummary.recommended_missing.map((docType) => (
              <li key={docType}>• {getLabel(docType)}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Expanded details */}
      {expanded && validationSummary && (
        <div className="mt-4 pt-4 border-t space-y-4">
          {/* Documents list */}
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-2">
              Documentos subidos ({documents.length})
            </h4>
            {documents.length === 0 ? (
              <p className="text-sm text-gray-500">No hay documentos</p>
            ) : (
              <ul className="space-y-2">
                {documents.map((doc) => (
                  <li key={doc.id} className="flex items-center justify-between text-sm">
                    <span className="text-gray-900">{doc.original_filename}</span>
                    <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                      doc.detected_document_type
                        ? "bg-gray-100 text-gray-700"
                        : "bg-gray-200 text-gray-500"
                    }`}>
                      {getLabel(doc.detected_document_type)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Requirements for this matter type */}
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-2">
              Requisitos para: {matterLabel}
            </h4>
            <div className="text-sm text-gray-600">
              <p className="mb-1">
                <strong>Requeridos:</strong>{" "}
                {validationSummary.required_types.length > 0
                  ? validationSummary.required_types.map(getLabel).join(", ")
                  : "Ninguno"}
              </p>
              <p>
                <strong>Encontrados:</strong>{" "}
                {validationSummary.required_found.length > 0
                  ? validationSummary.required_found.map(getLabel).join(", ")
                  : "Ninguno"}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

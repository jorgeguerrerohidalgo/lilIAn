/**
 * UI constants for the matters detail page.
 *
 * S4-01: extracted from the 1,357-line ``app/matters/[id]/page.tsx``
 * so the main shell stays focused on the orchestration and the
 * four tab components own their visual labels.
 */

export type TabType = "details" | "documents" | "analysis" | "chat" | "deadlines";

export const matterTypeLabels: Record<string, string> = {
  contract_review: "Revisión de contrato",
  lease: "Arriendo",
  labor: "Laboral",
  company: "Empresas",
  data_protection: "Protección de datos",
  consumer: "Consumidor",
  family: "Familia",
  debt: "Deudas",
  other: "Otro",
};

export const statusLabels: Record<string, string> = {
  new: "Nuevo",
  processing: "Procesando",
  analysis_ready: "Análisis listo",
  pending_human_review: "Pendiente revisión",
  missing_information: "Info incompleta",
  contact_client: "Contactar cliente",
  in_progress: "En gestión",
  closed: "Cerrado",
  archived: "Archivado",
};

export const urgencyColors: Record<string, string> = {
  low: "bg-green-100 text-green-800",
  medium: "bg-yellow-100 text-yellow-800",
  high: "bg-orange-100 text-orange-800",
  urgent: "bg-red-100 text-red-800",
};

export const statusColors: Record<string, string> = {
  new: "bg-blue-100 text-blue-800",
  processing: "bg-yellow-100 text-yellow-800",
  analysis_ready: "bg-green-100 text-green-800",
  pending_human_review: "bg-purple-100 text-purple-800",
  missing_information: "bg-orange-100 text-orange-800",
  contact_client: "bg-cyan-100 text-cyan-800",
  in_progress: "bg-indigo-100 text-indigo-800",
  closed: "bg-gray-100 text-gray-800",
  archived: "bg-gray-200 text-gray-600",
};

export const riskLevelColors: Record<string, string> = {
  low: "bg-green-100 text-green-800",
  medium: "bg-yellow-100 text-yellow-800",
  high: "bg-orange-100 text-orange-800",
  critical: "bg-red-100 text-red-800",
};

export const matterTypeToLegalArea: Record<string, string> = {
  labor: "labor",
  contract_review: "civil",
  lease: "civil",
  debt: "civil",
  data_protection: "civil",
  consumer: "consumer",
  family: "family",
  company: "commerce",
  other: "other",
};

export const legalAreaLabels: Record<string, string> = {
  labor: "Laboral",
  civil: "Civil",
  consumer: "Consumidor",
  family: "Familia",
  commerce: "Comercial",
  penal: "Penal",
  other: "General",
};

export const legalAreaColors: Record<string, string> = {
  labor: "bg-blue-100 text-blue-900 border-blue-300",
  civil: "bg-green-100 text-green-900 border-green-300",
  consumer: "bg-yellow-100 text-yellow-900 border-yellow-300",
  family: "bg-purple-100 text-purple-900 border-purple-300",
  commerce: "bg-orange-100 text-orange-900 border-orange-300",
  penal: "bg-red-100 text-red-900 border-red-300",
  other: "bg-gray-100 text-gray-900 border-gray-300",
};
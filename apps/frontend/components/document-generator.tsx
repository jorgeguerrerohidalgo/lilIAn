"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { getApiUrl } from "@/lib/api";
import { logger } from "../lib/logger";


const API_URL = getApiUrl();

interface Template {
  id: string;
  name: string;
  category: string;
  description: string;
  variables: Variable[];
}

interface Variable {
  key: string;
  label: string;
  required: boolean;
  type?: string;
}

interface GeneratedDocument {
  success: boolean;
  content: string | null;
  document_name: string | null;
  errors: string[];
}

interface SuggestedVariables {
  success: boolean;
  suggested_variables: Record<string, string>;
  reasoning: string;
  missing_fields: string[];
}

const categoryLabels: Record<string, string> = {
  comunicacion: "Comunicación",
  administrativo: "Administrativo",
  procesal: "Procesal",
  poderes: "Poderes",
  contratos: "Contratos"
};

export function DocumentGenerator({ matterId }: { matterId?: number }) {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [variables, setVariables] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [suggestedResult, setSuggestedResult] = useState<SuggestedVariables | null>(null);
  const [generatedDoc, setGeneratedDoc] = useState<GeneratedDocument | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [categories, setCategories] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API_URL}/api/v1/doc-templates/templates`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setTemplates(data);

        // Extraer categorías únicas
        const cats = [...new Set<string>(data.map((t: Template) => t.category))];
        setCategories(cats);
      }
    } catch (error) {
      logger.error("Error fetching templates:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectTemplate = (template: Template) => {
    setSelectedTemplate(template);
    setVariables({});
    setGeneratedDoc(null);
    setSuggestedResult(null);
  };

  const handleSuggestVariables = async () => {
    if (!selectedTemplate || !matterId) return;

    setSuggesting(true);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(
        `${API_URL}/api/v1/doc-templates/suggest-variables?template_id=${selectedTemplate.id}`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ matter_id: matterId }),
        }
      );

      if (res.ok) {
        const data: SuggestedVariables = await res.json();
        setSuggestedResult(data);
        if (data.success && data.suggested_variables) {
          setVariables((prev) => ({
            ...prev,
            ...data.suggested_variables,
          }));
        }
      }
    } catch (error) {
      logger.error("Error suggesting variables:", error);
    } finally {
      setSuggesting(false);
    }
  };

  const handleGenerate = async () => {
    if (!selectedTemplate) return;

    setGenerating(true);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API_URL}/api/v1/doc-templates/generate`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          template_id: selectedTemplate.id,
          variables,
          matter_id: matterId,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setGeneratedDoc(data);
        if (data.success) {
          setShowModal(true);
        }
      } else {
        setGeneratedDoc({ success: false, content: null, document_name: null, errors: ["Error al generar documento"] });
      }
    } catch (error) {
      logger.error("Error generating document:", error);
      setGeneratedDoc({ success: false, content: null, document_name: null, errors: ["Error de conexión"] });
    } finally {
      setGenerating(false);
    }
  };

  const handleDownload = () => {
    if (!generatedDoc?.content) return;

    const blob = new Blob([generatedDoc.content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = generatedDoc.document_name || "documento.txt";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const filteredTemplates = selectedCategory
    ? templates.filter((t) => t.category === selectedCategory)
    : templates;

  return (
    <div className="space-y-6">
      <div className="bg-cream rounded-xl border border-border p-6">
        <h2 className="text-lg font-semibold text-ink mb-2">Generador de Documentos Legales</h2>
        <p className="text-ink2 text-sm mb-6">
          Selecciona un tipo de documento y completa los campos para generar un documento personalizado.
        </p>

        {/* Category Filter */}
        <div className="flex flex-wrap gap-2 mb-6">
          <button
            onClick={() => setSelectedCategory(null)}
            className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
              !selectedCategory
                ? "bg-ink text-white border-ink"
                : "bg-cream text-ink2 border-border hover:border-ink/30"
            }`}
          >
            Todos
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                selectedCategory === cat
                  ? "bg-ink text-white border-ink"
                  : "bg-cream text-ink2 border-border hover:border-ink/30"
              }`}
            >
              {categoryLabels[cat] || cat}
            </button>
          ))}
        </div>

        {/* Templates Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          {loading ? (
            <div className="col-span-full text-center py-8">
              <div className="w-8 h-8 border-3 border-soft border-t-ink rounded-full animate-spin mx-auto" />
            </div>
          ) : (
            filteredTemplates.map((template) => (
              <button
                key={template.id}
                onClick={() => handleSelectTemplate(template)}
                className={`p-4 rounded-xl border text-left transition-all ${
                  selectedTemplate?.id === template.id
                    ? "border-ink bg-soft ring-2 ring-ink"
                    : "border-border hover:border-ink/30 hover:shadow-md"
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-lg text-ink/60">
                    {template.category === "comunicacion" && "📧"}
                    {template.category === "administrativo" && "📋"}
                    {template.category === "procesal" && "⚖️"}
                    {template.category === "poderes" && "📜"}
                    {template.category === "contratos" && "📄"}
                  </span>
                  <span className="font-medium text-ink">{template.name}</span>
                </div>
                <p className="text-sm text-ink2 line-clamp-2">{template.description}</p>
                <p className="text-xs text-ink/40 mt-2">
                  {template.variables.filter((v) => v.required).length} campos requeridos
                </p>
              </button>
            ))
          )}
        </div>

        {/* Variable Form */}
        {selectedTemplate && (
          <div className="bg-soft rounded-xl p-6 border border-border">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-ink">
                Completar: {selectedTemplate.name}
              </h3>
              {matterId && (
                <button
                  onClick={handleSuggestVariables}
                  disabled={suggesting}
                  className="px-3 py-1.5 text-sm bg-purple text-white rounded-lg hover:bg-purple/90 disabled:opacity-50 flex items-center gap-2 transition-colors"
                >
                  {suggesting ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Analizando caso...
                    </>
                  ) : (
                    <>
                      <svg aria-hidden="true" className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                      </svg>
                      Sugerir desde caso
                    </>
                  )}
                </button>
              )}
            </div>

            {suggestedResult && suggestedResult.success && (
              <div className="mb-4 p-3 bg-purple-pale border border-purple/20 rounded-lg">
                <p className="text-sm text-purple font-medium mb-1">Variables sugeridas</p>
                <p className="text-xs text-purple/80">{suggestedResult.reasoning}</p>
                {suggestedResult.missing_fields.length > 0 && (
                  <p className="text-xs text-amber mt-1">
                    Campos sin inferir: {suggestedResult.missing_fields.join(", ")}
                  </p>
                )}
              </div>
            )}

            <div className="space-y-4">
              {selectedTemplate.variables.map((variable) => (
                <div key={variable.key}>
                  <label className="block text-sm font-medium text-ink2 mb-1">
                    {variable.label}
                    {variable.required && <span className="text-coral ml-1">*</span>}
                  </label>
                  {variable.type === "textarea" ? (
                    <textarea
                      value={variables[variable.key] || ""}
                      onChange={(e) =>
                        setVariables((prev) => ({
                          ...prev,
                          [variable.key]: e.target.value,
                        }))
                      }
                      rows={3}
                      className="w-full px-3.5 py-2.5 border border-border rounded-lg text-ink placeholder-ink/40 focus:outline-none focus:ring-2 focus:ring-ink/20 focus:border-ink/40 transition-all"
                      placeholder={`Ingrese ${variable.label.toLowerCase()}`}
                    />
                  ) : (
                    <input
                      type="text"
                      value={variables[variable.key] || ""}
                      onChange={(e) =>
                        setVariables((prev) => ({
                          ...prev,
                          [variable.key]: e.target.value,
                        }))
                      }
                      className="w-full px-3.5 py-2.5 border border-border rounded-lg text-ink placeholder-ink/40 focus:outline-none focus:ring-2 focus:ring-ink/20 focus:border-ink/40 transition-all"
                      placeholder={`Ingrese ${variable.label.toLowerCase()}`}
                    />
                  )}
                </div>
              ))}
            </div>

            <div className="mt-6 flex gap-3">
              <button
                onClick={handleGenerate}
                disabled={generating}
                aria-busy={generating}
                aria-live="polite"
                className="px-5 py-2.5 bg-ink text-white rounded-lg font-medium text-sm hover:bg-ink/90 disabled:opacity-50 flex items-center gap-2 transition-colors"
              >
                {generating ? (
                  <>
                    <div
                      className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"
                      aria-hidden="true"
                    />
                    Generando...
                  </>
                ) : (
                  <>Generar Documento</>
                )}
              </button>
              <button
                onClick={() => setSelectedTemplate(null)}
                type="button"
                className="px-4 py-2.5 border border-border text-ink2 rounded-lg font-medium text-sm hover:bg-cream transition-colors"
              >
                Cancelar
              </button>
            </div>

            {generatedDoc && !generatedDoc.success && (
              <div className="mt-4 p-3 bg-coral-pale border border-coral/20 rounded-lg text-coral-dark text-sm">
                {generatedDoc.errors.map((err, i) => (
                  <p key={i}>{err}</p>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Preview Modal */}
      {showModal && generatedDoc && (
        <PreviewModal
          documentName={generatedDoc.document_name ?? "Documento"}
          content={generatedDoc.content}
          onDownload={handleDownload}
          onClose={() => setShowModal(false)}
        />
      )}
    </div>
  );
}

// S5 accessibility: dedicated modal component with focus trap, Escape key
// handler and focus restoration (WCAG 2.4.3 Focus Order).
function PreviewModal({
  documentName,
  content,
  onDownload,
  onClose,
}: {
  documentName: string;
  content: string | null;
  onDownload: () => void;
  onClose: () => void;
}) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
        return;
      }
      // Simple focus trap: cycle Tab between first and last focusable.
      if (e.key === 'Tab' && modalRef.current) {
        const focusable = modalRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    },
    [onClose]
  );

  useEffect(() => {
    previouslyFocusedRef.current = document.activeElement as HTMLElement | null;
    document.addEventListener('keydown', handleKeyDown);
    const id = window.setTimeout(() => closeButtonRef.current?.focus(), 0);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      window.clearTimeout(id);
      previouslyFocusedRef.current?.focus?.();
    };
  }, [handleKeyDown]);

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="doc-preview-title"
        tabIndex={-1}
        className="bg-cream rounded-xl shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col border border-border"
      >
        <div className="flex items-center justify-between p-6 border-b border-border">
          <h2 id="doc-preview-title" className="text-lg font-semibold text-ink">
            {documentName}
          </h2>
          <button
            ref={closeButtonRef}
            onClick={onClose}
            aria-label="Cerrar vista previa del documento"
            className="p-2 hover:bg-soft rounded-lg focus-visible:ring-2 focus-visible:ring-primary transition-colors"
          >
            <svg
              className="h-5 w-5 text-ink/60"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-6">
          <pre className="whitespace-pre-wrap font-mono text-sm text-ink2 bg-soft p-4 rounded-lg border border-border">
            {content}
          </pre>
        </div>
        <div className="p-6 border-t border-border flex gap-3">
          <button
            onClick={onDownload}
            className="px-5 py-2.5 bg-green text-white rounded-lg font-medium text-sm hover:bg-green/90 flex items-center gap-2 focus-visible:ring-2 focus-visible:ring-green transition-colors"
          >
            <svg aria-hidden="true" className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h14a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4v12m-4-4l4-4m0 0l4 4" />
            </svg>
            Descargar
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2.5 border border-border text-ink2 rounded-lg font-medium text-sm hover:bg-cream focus-visible:ring-2 focus-visible:ring-primary transition-colors"
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}

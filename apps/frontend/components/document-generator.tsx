"use client";

import { useState, useEffect } from "react";

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

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
        const cats = [...new Set(data.map((t: Template) => t.category))];
        setCategories(cats);
      }
    } catch (error) {
      console.error("Error fetching templates:", error);
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
      console.error("Error suggesting variables:", error);
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
      console.error("Error generating document:", error);
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
      <div className="bg-white rounded-xl shadow-sm border p-6">
        <h2 className="text-lg font-semibold mb-4">Generador de Documentos Legales</h2>
        <p className="text-gray-600 mb-6">
          Selecciona un tipo de documento y completa los campos para generar un documento personalizado.
        </p>

        {/* Category Filter */}
        <div className="flex flex-wrap gap-2 mb-6">
          <button
            onClick={() => setSelectedCategory(null)}
            className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
              !selectedCategory
                ? "bg-gray-800 text-white border-gray-800"
                : "bg-white text-gray-600 border-gray-300 hover:border-gray-400"
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
                  ? "bg-gray-800 text-white border-gray-800"
                  : "bg-white text-gray-600 border-gray-300 hover:border-gray-400"
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
              <div className="animate-spin h-8 w-8 border-2 border-primary-600 border-t-transparent rounded-full mx-auto" />
            </div>
          ) : (
            filteredTemplates.map((template) => (
              <button
                key={template.id}
                onClick={() => handleSelectTemplate(template)}
                className={`p-4 rounded-xl border text-left transition-all ${
                  selectedTemplate?.id === template.id
                    ? "border-primary-600 bg-primary-50 ring-2 ring-primary-600"
                    : "border-gray-200 hover:border-primary-300 hover:shadow-md"
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-lg">
                    {template.category === "comunicacion" && "📧"}
                    {template.category === "administrativo" && "📋"}
                    {template.category === "procesal" && "⚖️"}
                    {template.category === "poderes" && "📜"}
                    {template.category === "contratos" && "📄"}
                  </span>
                  <span className="font-medium text-gray-900">{template.name}</span>
                </div>
                <p className="text-sm text-gray-500 line-clamp-2">{template.description}</p>
                <p className="text-xs text-gray-400 mt-2">
                  {template.variables.filter((v) => v.required).length} campos requeridos
                </p>
              </button>
            ))
          )}
        </div>

        {/* Variable Form */}
        {selectedTemplate && (
          <div className="bg-gray-50 rounded-xl p-6 border">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900">
                Completar: {selectedTemplate.name}
              </h3>
              {matterId && (
                <button
                  onClick={handleSuggestVariables}
                  disabled={suggesting}
                  className="px-3 py-1.5 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center gap-2"
                >
                  {suggesting ? (
                    <>
                      <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                      Analizando caso...
                    </>
                  ) : (
                    <>
                      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                      </svg>
                      Sugerir desde caso
                    </>
                  )}
                </button>
              )}
            </div>

            {suggestedResult && suggestedResult.success && (
              <div className="mb-4 p-3 bg-purple-50 border border-purple-200 rounded-lg">
                <p className="text-sm text-purple-700 font-medium mb-1">Variables sugeridas</p>
                <p className="text-xs text-purple-600">{suggestedResult.reasoning}</p>
                {suggestedResult.missing_fields.length > 0 && (
                  <p className="text-xs text-orange-600 mt-1">
                    Campos sin inferir: {suggestedResult.missing_fields.join(", ")}
                  </p>
                )}
              </div>
            )}

            <div className="space-y-4">
              {selectedTemplate.variables.map((variable) => (
                <div key={variable.key}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {variable.label}
                    {variable.required && <span className="text-red-500 ml-1">*</span>}
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
                      rows={4}
                      className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
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
                      className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
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
                className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 flex items-center gap-2"
              >
                {generating ? (
                  <>
                    <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                    Generando...
                  </>
                ) : (
                  <>Generar Documento</>
                )}
              </button>
              <button
                onClick={() => setSelectedTemplate(null)}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
              >
                Cancelar
              </button>
            </div>

            {generatedDoc && !generatedDoc.success && (
              <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
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
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between p-6 border-b">
              <h2 className="text-xl font-semibold">
                {generatedDoc.document_name}
              </h2>
              <button
                onClick={() => setShowModal(false)}
                className="p-2 hover:bg-gray-100 rounded-lg"
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-6">
              <pre className="whitespace-pre-wrap font-mono text-sm text-gray-700 bg-gray-50 p-4 rounded-lg">
                {generatedDoc.content}
              </pre>
            </div>
            <div className="p-6 border-t flex gap-3">
              <button
                onClick={handleDownload}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-2"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h14a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4v12m-4-4l4-4m0 0l4 4" />
                </svg>
                Descargar
              </button>
              <button
                onClick={() => setShowModal(false)}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

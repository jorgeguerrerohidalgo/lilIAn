"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Matter {
  id: number;
  title: string;
  matter_type: string;
  description: string;
  status: string;
  urgency: string;
  counterparty_name: string;
  created_at: string;
  updated_at: string;
}

interface Document {
  id: number;
  original_filename: string;
  mime_type: string;
  file_size: number;
  status: string;
  created_at: string;
}

interface AnalysisReport {
  id: number;
  report_type: string;
  summary: string;
  facts: string;
  missing_information: string;
  next_steps: string;
  confidence: string;
  status: string;
  created_at: string;
  risks: RiskItem[];
}

interface RiskItem {
  id: number;
  level: string;
  title: string;
  description: string;
  impact: string;
  recommendation: string;
  confidence: string;
  review_status: string;
}

interface ChatSession {
  id: number;
  matter_id: number;
  title: string;
  created_at: string;
  updated_at: string;
}

interface ChatMessage {
  id: number;
  role: string;
  content: string;
  created_at: string;
}

type TabType = "details" | "documents" | "analysis" | "chat";

const matterTypeLabels: Record<string, string> = {
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

const statusLabels: Record<string, string> = {
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

const urgencyColors: Record<string, string> = {
  low: "bg-green-100 text-green-800",
  medium: "bg-yellow-100 text-yellow-800",
  high: "bg-orange-100 text-orange-800",
  urgent: "bg-red-100 text-red-800",
};

const statusColors: Record<string, string> = {
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

const riskLevelColors: Record<string, string> = {
  low: "bg-green-100 text-green-800",
  medium: "bg-yellow-100 text-yellow-800",
  high: "bg-orange-100 text-orange-800",
  critical: "bg-red-100 text-red-800",
};

const matterTypeToLegalArea: Record<string, string> = {
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

const legalAreaLabels: Record<string, string> = {
  labor: "Laboral",
  civil: "Civil",
  consumer: "Consumidor",
  family: "Familia",
  commerce: "Comercial",
  penal: "Penal",
  other: "General",
};

const legalAreaColors: Record<string, string> = {
  labor: "bg-blue-100 text-blue-800 border-blue-200",
  civil: "bg-green-100 text-green-800 border-green-200",
  consumer: "bg-yellow-100 text-yellow-800 border-yellow-200",
  family: "bg-purple-100 text-purple-800 border-purple-200",
  commerce: "bg-orange-100 text-orange-800 border-orange-200",
  penal: "bg-red-100 text-red-800 border-red-200",
  other: "bg-gray-100 text-gray-800 border-gray-200",
};

export default function MatterDetailPage() {
  const params = useParams();
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [matter, setMatter] = useState<Matter | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<TabType>("details");

  // Documents state
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [uploadSuccess, setUploadSuccess] = useState("");
  const [deletingDocId, setDeletingDocId] = useState<number | null>(null);
  const [deleteError, setDeleteError] = useState("");

  // Analysis state
  const [analysis, setAnalysis] = useState<AnalysisReport | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState("");
  const [analysisSuccess, setAnalysisSuccess] = useState("");
  const analysisRef = useRef<AnalysisReport | null>(null);

  // Chat state
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSession, setActiveSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [sendingMessage, setSendingMessage] = useState(false);
  const [chatError, setChatError] = useState("");
  const [creatingSession, setCreatingSession] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Legal area state for chat
  const defaultLegalArea = matter ? (matterTypeToLegalArea[matter.matter_type] || "other") : "other";
  const [selectedLegalArea, setSelectedLegalArea] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/auth/login");
      return;
    }

    fetch(`${API_URL}/api/v1/matters/${params.id}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Caso no encontrado");
        return res.json();
      })
      .then((data) => {
        setMatter(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Error al cargar el caso");
        setLoading(false);
      });
  }, [params.id, router]);

  useEffect(() => {
    if (matter) {
      fetchDocuments();
      fetchAnalysis();
      fetchSessions();
    }
  }, [matter]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const getToken = () => localStorage.getItem("token") || "";

  const fetchDocuments = async () => {
    const token = getToken();
    const res = await fetch(`${API_URL}/api/v1/documents/matters/${params.id}/documents`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      const data = await res.json();
      setDocuments(data);
    }
  };

  const fetchAnalysis = async () => {
    const token = getToken();
    const res = await fetch(`${API_URL}/api/v1/analysis/matters/${params.id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      const data = await res.json();
      if (data.length > 0) {
        fetchAnalysisDetail(data[0].id);
      }
    }
  };

  const fetchAnalysisDetail = async (reportId: number) => {
    const token = getToken();
    const res = await fetch(`${API_URL}/api/v1/analysis/reports/${reportId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      const data = await res.json();
      setAnalysis(data);
      analysisRef.current = data;
    }
  };

  const fetchSessions = async () => {
    const token = getToken();
    const res = await fetch(`${API_URL}/api/v1/chat/sessions?matter_id=${params.id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      const data = await res.json();
      setSessions(data);
    }
  };

  const fetchMessages = async (sessionId: number) => {
    const token = getToken();
    const res = await fetch(`${API_URL}/api/v1/chat/sessions/${sessionId}/messages`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      const data = await res.json();
      setMessages(data);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadError("");
    setUploadSuccess("");

    const formData = new FormData();
    formData.append("file", file);

    const token = getToken();
    const res = await fetch(`${API_URL}/api/v1/documents/matters/${params.id}/documents`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    });

    if (res.ok) {
      setUploadSuccess("Documento subido exitosamente");
      fetchDocuments();
      if (fileInputRef.current) fileInputRef.current.value = "";
    } else {
      const data = await res.json();
      setUploadError(data.detail || "Error al subir documento");
    }
    setUploading(false);
  };

  const handleDeleteDocument = async (docId: number) => {
    if (!confirm("¿Estás seguro de que deseas eliminar este documento?")) return;

    setDeletingDocId(docId);
    setDeleteError("");

    const token = getToken();
    const res = await fetch(`${API_URL}/api/v1/documents/${docId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });

    if (res.ok) {
      setDocuments(documents.filter((d) => d.id !== docId));
    } else {
      const data = await res.json();
      setDeleteError(data.detail || "Error al eliminar documento");
    }
    setDeletingDocId(null);
  };

  const handleRequestAnalysis = async () => {
    setAnalyzing(true);
    setAnalysisError("");
    setAnalysisSuccess("");

    const token = getToken();
    const res = await fetch(`${API_URL}/api/v1/analysis`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ matter_id: Number(params.id) }),
    });

    if (res.ok) {
      setAnalysisSuccess("El análisis puede tardar entre 30 segundos y 2 minutos...");
      setAnalyzing(true);
      // Poll for analysis result
      let attempts = 0;
      const maxAttempts = 24; // 2 minutes max (24 * 5s = 120s)
      const pollInterval = setInterval(async () => {
        attempts++;
        await fetchAnalysis();
        if (analysisRef.current || attempts >= maxAttempts) {
          clearInterval(pollInterval);
          setAnalyzing(false);
          if (!analysisRef.current) {
            setAnalysisError("El análisis está tardando más de lo esperado. Intenta de nuevo más tarde.");
          }
          setAnalysisSuccess("");
        }
      }, 5000);
    } else {
      const data = await res.json();
      setAnalysisError(data.detail || "Error al solicitar análisis");
    }
    setAnalyzing(false);
  };

  const handleCreateSession = async () => {
    setCreatingSession(true);
    setChatError("");

    const token = getToken();
    const res = await fetch(`${API_URL}/api/v1/chat/sessions`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ matter_id: Number(params.id), title: `Chat - ${matter?.title}` }),
    });

    if (res.ok) {
      const session = await res.json();
      setSessions([session, ...sessions]);
      setActiveSession(session);
      setMessages([]);
    } else {
      const data = await res.json();
      setChatError(data.detail || "Error al crear sesión");
    }
    setCreatingSession(false);
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || !activeSession || sendingMessage) return;

    setSendingMessage(true);
    setChatError("");

    const userMessage: ChatMessage = {
      id: Date.now(),
      role: "user",
      content: chatInput,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    const inputToSend = chatInput;
    setChatInput("");

    const token = getToken();
    const payload: { session_id: number; message: string; legal_area_override?: string } = {
      session_id: activeSession.id,
      message: inputToSend,
    };

    // Only include legal_area_override if user selected something different from default
    if (selectedLegalArea && selectedLegalArea !== defaultLegalArea) {
      payload.legal_area_override = selectedLegalArea;
    }

    const res = await fetch(`${API_URL}/api/v1/chat/message`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      const data = await res.json();
      const assistantMessage: ChatMessage = {
        id: data.message_id,
        role: "assistant",
        content: data.content,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } else {
      const data = await res.json();
      setChatError(data.detail || "Error al enviar mensaje");
      setMessages((prev) => prev.filter((m) => m.id !== userMessage.id));
    }
    setSendingMessage(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-gray-600">Cargando caso...</p>
      </div>
    );
  }

  if (error || !matter) {
    return (
      <div className="text-center py-20">
        <h2 className="text-xl font-semibold text-red-600 mb-4">
          {error || "Caso no encontrado"}
        </h2>
        <Link href="/dashboard" className="text-primary-600 hover:text-primary-700">
          Volver a casos
        </Link>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <Link href="/dashboard" className="text-sm text-gray-600 hover:text-primary-600 mb-2 inline-block">
          ← Volver al dashboard
        </Link>
        <h1 className="text-3xl font-bold text-gray-900">{matter.title}</h1>
        <div className="flex gap-3 mt-3">
          <span className={`px-3 py-1 text-sm font-medium rounded-full ${statusColors[matter.status] || "bg-gray-100 text-gray-800"}`}>
            {statusLabels[matter.status] || matter.status}
          </span>
          <span className={`px-3 py-1 text-sm font-medium rounded-full ${urgencyColors[matter.urgency] || "bg-gray-100 text-gray-800"}`}>
            Urgencia: {matter.urgency}
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-6">
          {(["details", "documents", "analysis", "chat"] as TabType[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab
                  ? "border-primary-600 text-primary-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              }`}
            >
              {tab === "details" && "Detalles"}
              {tab === "documents" && "Documentos"}
              {tab === "analysis" && "Análisis IA"}
              {tab === "chat" && "Chat"}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === "details" && (
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h2 className="text-lg font-semibold mb-4">Detalles del caso</h2>
          <dl className="space-y-3">
            <div className="flex">
              <dt className="w-40 text-gray-500">Tipo:</dt>
              <dd className="text-gray-900">
                {matterTypeLabels[matter.matter_type] || matter.matter_type}
              </dd>
            </div>
            {matter.counterparty_name && (
              <div className="flex">
                <dt className="w-40 text-gray-500">Contraparte:</dt>
                <dd className="text-gray-900">{matter.counterparty_name}</dd>
              </div>
            )}
            <div className="flex">
              <dt className="w-40 text-gray-500">Creado:</dt>
              <dd className="text-gray-900">
                {new Date(matter.created_at).toLocaleDateString("es-CL")}
              </dd>
            </div>
          </dl>
          {matter.description && (
            <div className="mt-6 pt-6 border-t">
              <h3 className="font-medium text-gray-900 mb-2">Descripción</h3>
              <p className="text-gray-700 whitespace-pre-wrap">{matter.description}</p>
            </div>
          )}
        </div>
      )}

      {activeTab === "documents" && (
        <div className="space-y-6">
          {/* Upload Section */}
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold mb-4">Subir documento</h2>
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
              <input
                ref={fileInputRef}
                type="file"
                id="file-upload"
                className="hidden"
                accept=".pdf,.docx,.doc,.txt"
                onChange={handleFileUpload}
                disabled={uploading}
              />
              <label
                htmlFor="file-upload"
                className="cursor-pointer flex flex-col items-center"
              >
                <svg className="w-12 h-12 text-gray-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                <span className="text-gray-600">
                  {uploading ? "Subiendo..." : "Arrastra un archivo o haz clic para seleccionar"}
                </span>
                <span className="text-sm text-gray-400 mt-1">PDF, DOCX, DOC, TXT (máx. 50MB)</span>
              </label>
            </div>
            {uploadError && (
              <div className="mt-3 p-3 bg-red-50 text-red-600 rounded-lg text-sm">{uploadError}</div>
            )}
            {uploadSuccess && (
              <div className="mt-3 p-3 bg-green-50 text-green-600 rounded-lg text-sm">{uploadSuccess}</div>
            )}
          </div>

          {/* Documents List */}
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold mb-4">Documentos ({documents.length})</h2>
            {documents.length === 0 ? (
              <p className="text-gray-500 text-center py-8">No hay documentos subiendo.</p>
            ) : (
              <div className="space-y-3">
                {documents.map((doc) => (
                  <div key={doc.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center gap-3">
                      <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      <div>
                        <p className="font-medium text-gray-900">{doc.original_filename}</p>
                        <p className="text-sm text-gray-500">
                          {(doc.file_size / 1024).toFixed(1)} KB • {doc.status}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => handleDeleteDocument(doc.id)}
                      disabled={deletingDocId === doc.id}
                      className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
                      title="Eliminar documento"
                    >
                      {deletingDocId === doc.id ? (
                        <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                      ) : (
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      )}
                    </button>
                  </div>
                ))}
                {deleteError && (
                  <div className="mt-3 p-3 bg-red-50 text-red-600 rounded-lg text-sm">{deleteError}</div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === "analysis" && (
        <div className="space-y-6">
          {/* Request Analysis */}
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h2 className="text-lg font-semibold mb-4">Análisis de Inteligencia Artificial</h2>
            <p className="text-gray-600 mb-4">
              Solicita un análisis automático de tu caso legal basado en los documentos subidos y la información del caso.
            </p>
            <button
              onClick={handleRequestAnalysis}
              disabled={analyzing}
              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              {analyzing ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Procesando...
              </span>
            ) : "Solicitar nuevo análisis"}
            </button>
            {analysisError && (
              <div className="mt-3 p-3 bg-red-50 text-red-600 rounded-lg text-sm">{analysisError}</div>
            )}
            {analysisSuccess && (
              <div className="mt-3 p-4 bg-blue-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <svg className="animate-spin h-5 w-5 text-blue-600" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  <div>
                    <p className="text-blue-800 font-medium">Análisis en progreso</p>
                    <p className="text-blue-600 text-sm">{analysisSuccess}</p>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Analysis Results */}
          {analysis ? (
            <div className="bg-white rounded-xl shadow-sm border p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-semibold">Informe de Análisis</h2>
                <span className="text-sm text-gray-500">
                  {new Date(analysis.created_at).toLocaleDateString("es-CL")}
                </span>
              </div>

              {/* Resumen Ejecutivo */}
              {analysis.summary && (
                <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-100">
                  <h3 className="font-semibold text-blue-900 mb-2 flex items-center gap-2">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Resumen Ejecutivo
                  </h3>
                  <p className="text-gray-700 whitespace-pre-wrap">{analysis.summary}</p>
                </div>
              )}

              {/* Puntos Críticos - parseados del JSON */}
              {analysis.facts && (
                <div className="mb-6">
                  <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <svg className="w-5 h-5 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    Puntos Críticos a Revisar
                  </h3>
                  {(() => {
                    let puntos = [];
                    try {
                      puntos = typeof analysis.facts === 'string' ? JSON.parse(analysis.facts) : analysis.facts;
                    } catch { puntos = []; }
                    if (!Array.isArray(puntos)) puntos = [];
                    return puntos.length > 0 ? (
                      <div className="space-y-3">
                        {puntos.map((punto: any, idx: number) => (
                          <div key={idx} className={`p-4 rounded-lg border-l-4 ${
                            punto.prioridad === 'alta' ? 'bg-red-50 border-red-500' :
                            punto.prioridad === 'media' ? 'bg-yellow-50 border-yellow-500' :
                            'bg-green-50 border-green-500'
                          }`}>
                            <div className="flex items-start justify-between gap-3">
                              <div className="flex-1">
                                <p className="font-medium text-gray-900">{punto.asunto}</p>
                                <p className="text-gray-600 text-sm mt-1">{punto.descripcion}</p>
                                {punto.fundamento_legal && (
                                  <p className="text-gray-500 text-xs mt-2 italic">
                                    Fundamento: {punto.fundamento_legal}
                                  </p>
                                )}
                              </div>
                              <span className={`px-2 py-1 text-xs font-medium rounded ${
                                punto.prioridad === 'alta' ? 'bg-red-100 text-red-700' :
                                punto.prioridad === 'media' ? 'bg-yellow-100 text-yellow-700' :
                                'bg-green-100 text-green-700'
                              }`}>
                                {punto.prioridad?.toUpperCase()}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-gray-500 italic">No hay puntos críticos identificados.</p>
                    );
                  })()}
                </div>
              )}

              {/* Riesgos Identificados */}
              {analysis.risks && analysis.risks.length > 0 && (
                <div className="mb-6">
                  <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Riesgos Identificados
                  </h3>
                  <div className="space-y-3">
                    {analysis.risks.map((risk) => (
                      <div key={risk.id} className={`border rounded-lg p-4 ${
                        risk.level === 'red' ? 'bg-red-50 border-red-200' :
                        risk.level === 'yellow' ? 'bg-yellow-50 border-yellow-200' :
                        risk.level === 'green' ? 'bg-green-50 border-green-200' :
                        'bg-gray-50 border-gray-200'
                      }`}>
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`px-2 py-1 text-xs font-medium rounded ${riskLevelColors[risk.level] || "bg-gray-100 text-gray-800"}`}>
                            {risk.level?.toUpperCase()}
                          </span>
                          <span className="font-semibold text-gray-900">{risk.title}</span>
                        </div>
                        <p className="text-gray-700 text-sm mb-3">{risk.description}</p>
                        {risk.impact && (
                          <p className="text-sm"><span className="font-medium text-gray-800">Impacto:</span> <span className="text-gray-600">{risk.impact}</span></p>
                        )}
                        {risk.recommendation && (
                          <p className="text-sm mt-2"><span className="font-medium text-gray-800">Recomendación:</span> <span className="text-gray-600">{risk.recommendation}</span></p>
                        )}
                        {risk.confidence && (
                          <p className="text-xs text-gray-400 mt-2">Confianza: {risk.confidence}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Información Faltante */}
              {analysis.missing_information && (
                <div className="mb-6 p-4 bg-amber-50 rounded-lg border border-amber-200">
                  <h3 className="font-semibold text-amber-900 mb-2 flex items-center gap-2">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Información Faltante
                  </h3>
                  {(() => {
                    let info = [];
                    try {
                      info = typeof analysis.missing_information === 'string' ? JSON.parse(analysis.missing_information) : analysis.missing_information;
                    } catch { info = []; }
                    return Array.isArray(info) && info.length > 0 ? (
                      <ul className="list-disc list-inside text-amber-800 space-y-1">
                        {info.map((item: string, idx: number) => (
                          <li key={idx}>{item}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-amber-700">{String(analysis.missing_information)}</p>
                    );
                  })()}
                </div>
              )}

              {/* Próximos Pasos */}
              {analysis.next_steps && (
                <div className="mb-6 p-4 bg-purple-50 rounded-lg border border-purple-100">
                  <h3 className="font-semibold text-purple-900 mb-2 flex items-center gap-2">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                    </svg>
                    Próximos Pasos
                  </h3>
                  {(() => {
                    let pasos = [];
                    try {
                      pasos = typeof analysis.next_steps === 'string' ? JSON.parse(analysis.next_steps) : analysis.next_steps;
                    } catch { pasos = []; }
                    return Array.isArray(pasos) && pasos.length > 0 ? (
                      <ol className="list-decimal list-inside text-purple-800 space-y-1">
                        {pasos.map((paso: string, idx: number) => (
                          <li key={idx}>{paso}</li>
                        ))}
                      </ol>
                    ) : (
                      <p className="text-purple-700">{String(analysis.next_steps)}</p>
                    );
                  })()}
                </div>
              )}

              <div className="mt-6 p-4 bg-gray-100 rounded-lg border border-gray-200">
                <div className="flex items-start gap-3">
                  <svg className="w-5 h-5 text-gray-500 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <p className="text-xs text-gray-600">
                    <strong>Nota legal:</strong> Este análisis es preliminar y no reemplaza la revisión profesional de un abogado habilitado en Chile. Los resultados se basan en la información disponible en los documentos.
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-xl shadow-sm border p-6 text-center">
              <p className="text-gray-500">No hay análisis disponible. Solicita uno usando el botón de arriba.</p>
            </div>
          )}
        </div>
      )}

      {activeTab === "chat" && (
        <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
          <div className="flex h-[500px]">
            {/* Sessions Sidebar */}
            <div className="w-64 border-r flex flex-col">
              <div className="p-4 border-b">
                <button
                  onClick={handleCreateSession}
                  disabled={creatingSession}
                  className="w-full px-3 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50"
                >
                  {creatingSession ? "Creando..." : "+ Nueva sesión"}
                </button>
              </div>
              <div className="flex-1 overflow-y-auto">
                {sessions.length === 0 ? (
                  <p className="p-4 text-sm text-gray-500 text-center">No hay sesiones de chat.</p>
                ) : (
                  <div className="p-2">
                    {sessions.map((session) => (
                      <button
                        key={session.id}
                        onClick={() => {
                          setActiveSession(session);
                          fetchMessages(session.id);
                        }}
                        className={`w-full text-left p-3 rounded-lg mb-1 ${
                          activeSession?.id === session.id
                            ? "bg-primary-50 text-primary-700"
                            : "hover:bg-gray-50"
                        }`}
                      >
                        <p className="text-sm font-medium truncate">{session.title || `Chat ${session.id}`}</p>
                        <p className="text-xs text-gray-500">
                          {new Date(session.updated_at).toLocaleDateString("es-CL")}
                        </p>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Chat Area */}
            <div className="flex-1 flex flex-col">
              {activeSession ? (
                <>
                  {/* Legal Area Selector */}
                  <div className="px-4 py-3 border-b bg-gray-50">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm text-gray-600">Área legal:</span>
                      <div className="flex gap-2 flex-wrap">
                        <button
                          type="button"
                          onClick={() => setSelectedLegalArea(null)}
                          className={`px-3 py-1 text-xs font-medium rounded-full border transition-colors ${
                            selectedLegalArea === null
                              ? "bg-primary-600 text-white border-primary-600"
                              : "bg-white text-gray-600 border-gray-300 hover:border-primary-400"
                          }`}
                        >
                          {legalAreaLabels[defaultLegalArea]} (auto)
                        </button>
                        {Object.entries(legalAreaLabels).map(([area, label]) => (
                          area !== defaultLegalArea && (
                            <button
                              key={area}
                              type="button"
                              onClick={() => setSelectedLegalArea(area)}
                              className={`px-3 py-1 text-xs font-medium rounded-full border transition-colors ${
                                selectedLegalArea === area
                                  ? `${legalAreaColors[area]} border-current`
                                  : "bg-white text-gray-600 border-gray-300 hover:border-gray-400"
                              }`}
                            >
                              {label}
                            </button>
                          )
                        ))}
                      </div>
                    </div>
                    {selectedLegalArea && selectedLegalArea !== defaultLegalArea && (
                      <p className="text-xs text-primary-600 mt-1">
                        Buscando en área: {legalAreaLabels[selectedLegalArea]}
                      </p>
                    )}
                  </div>

                  <div className="flex-1 overflow-y-auto p-4 space-y-4">
                    {messages.length === 0 ? (
                      <div className="text-center text-gray-500 py-8">
                        <p>Envía un mensaje para comenzar la conversación.</p>
                      </div>
                    ) : (
                      messages.map((msg) => (
                        <div
                          key={msg.id}
                          className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                        >
                          <div
                            className={`max-w-[70%] rounded-lg px-4 py-2 ${
                              msg.role === "user"
                                ? "bg-primary-600 text-white"
                                : "bg-gray-100 text-gray-900"
                            }`}
                          >
                            <p className="whitespace-pre-wrap">{msg.content}</p>
                            <p className={`text-xs mt-1 ${
                              msg.role === "user" ? "text-primary-200" : "text-gray-400"
                            }`}>
                              {new Date(msg.created_at).toLocaleTimeString("es-CL", {
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
                            </p>
                          </div>
                        </div>
                      ))
                    )}
                    <div ref={chatEndRef} />
                  </div>
                  <form onSubmit={handleSendMessage} className="p-4 border-t">
                    <div className="flex gap-3">
                      <input
                        type="text"
                        value={chatInput}
                        onChange={(e) => setChatInput(e.target.value)}
                        placeholder="Escribe tu mensaje..."
                        className="flex-1 px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                        disabled={sendingMessage}
                      />
                      <button
                        type="submit"
                        disabled={sendingMessage || !chatInput.trim()}
                        className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
                      >
                        {sendingMessage ? "..." : "Enviar"}
                      </button>
                    </div>
                    {chatError && (
                      <p className="mt-2 text-sm text-red-600">{chatError}</p>
                    )}
                  </form>
                </>
              ) : (
                <div className="flex-1 flex items-center justify-center text-gray-500">
                  <div className="text-center">
                    <svg className="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                    <p>Selecciona una sesión o crea una nueva para chatear.</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="mt-6 p-4 bg-primary-50 rounded-xl">
        <p className="text-sm text-primary-800">
          <strong>Nota legal:</strong> Este análisis es preliminar y no reemplaza
          la revisión profesional de un abogado habilitado en Chile.
        </p>
      </div>
    </div>
  );
}

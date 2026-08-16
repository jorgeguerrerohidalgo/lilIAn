"use client";

import { useState, useRef, useEffect } from "react";
import { clsx } from 'clsx';

type AgentMode = 'qa' | 'case_researcher' | 'drafting_assistant' | 'compliance_checker';

interface AgentOption {
  kind: AgentMode;
  label: string;
  description: string;
}

const AGENT_OPTIONS: AgentOption[] = [
  { kind: 'qa', label: 'Pregunta libre', description: 'Q&A conversacional sobre el caso.' },
  { kind: 'case_researcher', label: 'Investigar caso', description: 'Brief estructurado: leyes, precedentes, riesgos, próximos pasos.' },
  { kind: 'drafting_assistant', label: 'Redactar documento', description: 'Completa una plantilla legal con variables del caso.' },
  { kind: 'compliance_checker', label: 'Revisar cumplimiento', description: 'Detecta cláusulas que violan legislación chilena.' },
];

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  agentKind?: AgentMode;
  structured?: unknown;
  feedbackRating?: -1 | 1;
}

interface ChatContextInfo {
  matterId?: number;
  matterTitle?: string;
  documentName?: string;
}

interface ChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
  contextInfo?: ChatContextInfo;
}

const SESSION_STORAGE_KEY = 'lilian.chat.sessionId';
const CHAT_MESSAGE_MAX_LEN = 4_000;
const SESSION_BOOTSTRAP_TIMEOUT_MS = 15_000;
const MESSAGE_REQUEST_TIMEOUT_MS = 60_000;
const AGENT_RUN_TIMEOUT_MS = 90_000;
const FEEDBACK_TIMEOUT_MS = 10_000;

interface FeedbackButtonsProps {
  messageId: string;
  onRated: (rating: -1 | 1, correction: string | null) => void;
}

function FeedbackButtons({ messageId, onRated }: FeedbackButtonsProps) {
  const [showCorrection, setShowCorrection] = useState(false);
  const [correction, setCorrection] = useState('');
  const [pending, setPending] = useState(false);

  const submit = async (rating: -1 | 1, withCorrection: boolean) => {
    if (pending) return;
    setPending(true);
    try {
      const serverId = parseServerMessageId(messageId);
      if (serverId === null) return;
      const body: Record<string, unknown> = {
        chat_message_id: serverId,
        rating,
      };
      if (withCorrection && correction.trim()) {
        body.correction = correction.trim();
        body.extracted_fact = correction.trim();
        body.extracted_kind = 'preference';
      }
      const res = await fetchJsonWithTimeout(
        '/api/v1/feedback',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        },
        FEEDBACK_TIMEOUT_MS,
      );
      if (res.ok) {
        onRated(rating, withCorrection ? correction.trim() : null);
      }
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="inline-flex items-center gap-1">
      <button
        onClick={() => submit(1, false)}
        disabled={pending}
        aria-label="Marcar respuesta como útil"
        className="text-ink/40 hover:text-emerald-600 transition-colors disabled:opacity-50"
      >
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6.633 10.5c.806 0 1.533-.446 2.031-1.08a9.041 9.041 0 0112.591 0c.498.634 1.225 1.08 2.031 1.08 1.512 0 2.714-1.21 2.714-2.715 0-.708-.259-1.358-.692-1.85l-1.422-1.422A9.04 9.04 0 0021 3c-1.273 0-2.54.232-3.726.692A9.933 9.933 0 0014.21 3c-.638 0-1.27.063-1.886.183M6.633 10.5C5.722 10.5 5 11.222 5 12.083v5.834c0 .861.722 1.583 1.633 1.583h12.734c.911 0 1.633-.722 1.633-1.583V12.083c0-.861-.722-1.583-1.633-1.583H6.633z" />
        </svg>
      </button>
      <button
        onClick={() => setShowCorrection((v) => !v)}
        disabled={pending}
        aria-label="Marcar respuesta como no útil"
        className="text-ink/40 hover:text-red-500 transition-colors disabled:opacity-50"
      >
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M7.498 15.25H4.372c-1.625 0-2.9-1.343-2.9-2.94V9.31c0-1.597 1.275-2.94 2.9-2.94h12.16c1.625 0 2.9 1.343 2.9 2.94v3c0 1.597-1.275 2.94-2.9 2.94h-1.876m-6-7.5L7.5 13.25m0 0L4.372 10.06M7.5 13.25l3.128-3.19" />
        </svg>
      </button>
      {showCorrection && (
        <div className="absolute mt-8 bg-white border border-border rounded-lg p-2 shadow-md z-10 w-72">
          <textarea
            value={correction}
            onChange={(e) => setCorrection(e.target.value)}
            placeholder="¿Qué estuvo mal? (opcional)"
            className="w-full text-xs p-2 border border-border rounded resize-none h-16"
            aria-label="Corrección"
          />
          <div className="flex gap-1 mt-1 justify-end">
            <button
              onClick={() => setShowCorrection(false)}
              className="text-[10px] px-2 py-1 text-ink/60 hover:text-ink"
            >
              Cancelar
            </button>
            <button
              onClick={() => submit(-1, true)}
              disabled={pending}
              className="text-[10px] px-2 py-1 bg-red-500 text-white rounded hover:bg-red-600 disabled:opacity-50"
            >
              Enviar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function parseServerMessageId(localId: string): number | null {
  // Local ids look like `srv-123`, `agent-456`, or pending ones like
  // `srv-pending-...`. We only post feedback for persisted messages.
  const parts = localId.split('-');
  if (parts.length < 2) return null;
  if (parts[0] !== 'srv' && parts[0] !== 'agent') return null;
  const idStr = parts[parts.length - 1];
  const id = Number.parseInt(idStr, 10);
  return Number.isFinite(id) ? id : null;
}

function formatAgentSummary(output: Record<string, unknown>, mode: AgentMode): string {
  if (!output || typeof output !== 'object') return '(sin respuesta)';
  if (mode === 'case_researcher') {
    const lines: string[] = [];
    const summary = typeof output.summary === 'string' ? output.summary : '';
    if (summary) lines.push(summary);
    const laws = Array.isArray(output.applicable_laws) ? output.applicable_laws : [];
    if (laws.length > 0) {
      lines.push('\nLeyes aplicables:');
      for (const law of laws.slice(0, 6)) {
        if (typeof law !== 'object' || law === null) continue;
        const l = law as Record<string, unknown>;
        lines.push(`• ${l.law_name ?? '?'} ${l.article ?? ''} — ${l.summary ?? ''}`.trim());
      }
    }
    const risks = Array.isArray(output.identified_risks) ? output.identified_risks : [];
    if (risks.length > 0) {
      lines.push('\nRiesgos:');
      for (const r of risks.slice(0, 5)) {
        if (typeof r !== 'object' || r === null) continue;
        const ri = r as Record<string, unknown>;
        lines.push(`• [${ri.severity ?? '?'}] ${ri.title ?? ''} — ${ri.description ?? ''}`.trim());
      }
    }
    const next = Array.isArray(output.next_steps) ? output.next_steps : [];
    if (next.length > 0) {
      lines.push('\nPróximos pasos:');
      for (const step of next.slice(0, 5)) lines.push(`• ${String(step)}`);
    }
    const disclaimer = typeof output._disclaimer === 'string' ? output._disclaimer : '';
    if (disclaimer) lines.push(`\n${disclaimer}`);
    return lines.join('\n');
  }
  if (mode === 'drafting_assistant') {
    const draft = typeof output.draft_content === 'string' ? output.draft_content : '';
    if (draft) return draft;
    return typeof output._raw === 'string' ? output._raw : '(sin borrador)';
  }
  if (mode === 'compliance_checker') {
    const lines: string[] = [];
    const compliant = output.compliant === true;
    lines.push(compliant ? '✓ Documento cumple con la normativa.' : '✗ Se detectaron posibles incumplimientos.');
    const violations = Array.isArray(output.violations) ? output.violations : [];
    if (violations.length > 0) {
      lines.push('\nViolaciones:');
      for (const v of violations.slice(0, 8)) {
        if (typeof v !== 'object' || v === null) continue;
        const vi = v as Record<string, unknown>;
        lines.push(`• [${vi.severity ?? '?'}] ${vi.law_name ?? '?'} ${vi.article ?? ''} — ${vi.description ?? ''}`.trim());
      }
    }
    const obs = Array.isArray(output.observations) ? output.observations : [];
    if (obs.length > 0) {
      lines.push('\nObservaciones:');
      for (const o of obs.slice(0, 5)) lines.push(`• ${String(o)}`);
    }
    const disclaimer = typeof output._disclaimer === 'string' ? output._disclaimer : '';
    if (disclaimer) lines.push(`\n${disclaimer}`);
    return lines.join('\n');
  }
  return JSON.stringify(output, null, 2);
}

const BotIcon = () => (
  <svg aria-hidden="true" className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.556 4.03-8 9-8s9 3.444 9 8z" />
  </svg>
);

const SendIcon = () => (
  <svg aria-hidden="true" className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.269 20.876L5.999 12zm0 0h7.5" />
  </svg>
);

const CloseIcon = () => (
  <svg aria-hidden="true" className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const AlertIcon = () => (
  <svg aria-hidden="true" className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
  </svg>
);

async function fetchJsonWithTimeout(
  input: RequestInfo,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    window.clearTimeout(timeoutId);
  }
}

/**
 * Panel lateral de chat con el asistente legal lilIAn.
 *
 * Conecta con el backend en /api/v1/chat:
 *   - Al abrir, si no hay sesión persistida, crea una para el `matterId`
 *     recibido por prop o el primer caso del usuario.
 *   - Cada mensaje del usuario hace POST /chat/message y muestra la
 *     respuesta del LLM en streaming-friendly (texto completo, dado
 *     que el endpoint actual no expone SSE todavía — fase 2 lo agrega).
 *   - El sessionId se guarda en sessionStorage para sobrevivir
 *     refresh pero NO cruzar pestañas/pestañas de usuario.
 *
 * Accesibilidad WCAG:
 *   - role="dialog" + aria-modal + aria-labelledby
 *   - Escape cierra el panel
 *   - Focus atrapado dentro del diálogo, restaurado al trigger al cerrar
 *
 * @param props - {@link ChatPanelProps}.
 */
export function ChatPanel({ isOpen, onClose, contextInfo }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: '¡Hola! Soy el asistente legal de LILIAN. ¿En qué caso o materia legal puedo ayudarte?',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [mode, setMode] = useState<AgentMode>('qa');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (isOpen) {
      previouslyFocusedRef.current = document.activeElement as HTMLElement | null;
      const id = window.setTimeout(() => {
        closeButtonRef.current?.focus();
      }, 0);
      return () => {
        window.clearTimeout(id);
        previouslyFocusedRef.current?.focus?.();
      };
    }
  }, [isOpen]);

  // Bootstrap: cuando se abre el panel por primera vez, restaurar o crear
  // una sesión de chat. Solo se ejecuta si no hay sessionId en estado.
  useEffect(() => {
    if (!isOpen || sessionId !== null) return;
    let cancelled = false;

    async function bootstrap() {
      setError(null);
      try {
        const stored = sessionStorage.getItem(SESSION_STORAGE_KEY);
        if (stored) {
          const parsed = Number.parseInt(stored, 10);
          if (Number.isFinite(parsed)) {
            if (!cancelled) setSessionId(parsed);
            await loadHistory(parsed);
            return;
          }
        }
        const matterId = await resolveMatterId(contextInfo?.matterId);
        if (cancelled) return;
        if (matterId === null) {
          setError('Necesitas crear un caso antes de usar el chat.');
          return;
        }
        const session = await createSession(matterId);
        if (cancelled) return;
        sessionStorage.setItem(SESSION_STORAGE_KEY, String(session.id));
        setSessionId(session.id);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'No se pudo iniciar el chat');
        }
      }
    }

    bootstrap();
    return () => { cancelled = true; };
    // contextInfo.matterId changes when the user navigates between matters;
    // re-bootstrap so the session always reflects the current matter.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, contextInfo?.matterId]);

  const resolveMatterId = async (preferred: number | undefined): Promise<number | null> => {
    if (preferred !== undefined) return preferred;
    const res = await fetchJsonWithTimeout('/api/v1/matters', {}, SESSION_BOOTSTRAP_TIMEOUT_MS);
    if (!res.ok) {
      throw new Error(`No se pudieron cargar los casos (HTTP ${res.status})`);
    }
    const matters = await res.json();
    if (!Array.isArray(matters) || matters.length === 0) return null;
    const first = matters[0];
    return typeof first?.id === 'number' ? first.id : null;
  };

  const createSession = async (matterId: number) => {
    const res = await fetchJsonWithTimeout(
      '/api/v1/chat/sessions',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ matter_id: matterId, title: 'Chat desde dashboard' }),
      },
      SESSION_BOOTSTRAP_TIMEOUT_MS,
    );
    if (!res.ok) {
      throw new Error(`No se pudo crear la sesión de chat (HTTP ${res.status})`);
    }
    return res.json() as Promise<{ id: number; matter_id: number; title: string | null }>;
  };

  const loadHistory = async (sid: number) => {
    const res = await fetchJsonWithTimeout(
      `/api/v1/chat/sessions/${sid}/messages`,
      {},
      SESSION_BOOTSTRAP_TIMEOUT_MS,
    );
    if (!res.ok) {
      // Si la sesión guardada ya no existe (borrada en backend), limpiamos
      // y dejamos que el siguiente intento cree una nueva.
      sessionStorage.removeItem(SESSION_STORAGE_KEY);
      setSessionId(null);
      return;
    }
    const history = await res.json();
    if (Array.isArray(history) && history.length > 0) {
      const restored: ChatMessage[] = history.map((m: { id: number; role: string; content: string; created_at: string }) => ({
        id: String(m.id),
        role: m.role === 'assistant' ? 'assistant' : 'user',
        content: m.content,
        timestamp: new Date(m.created_at),
      }));
      setMessages(restored);
    }
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isLoading) return;
    if (text.length > CHAT_MESSAGE_MAX_LEN) {
      setError(`El mensaje supera el límite de ${CHAT_MESSAGE_MAX_LEN} caracteres.`);
      return;
    }

    if (mode !== 'qa') {
      await sendAgent(text);
      return;
    }

    if (sessionId === null) return;

    const userMessage: ChatMessage = {
      id: `local-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date(),
    };
    // Placeholder del assistant que iremos rellenando con cada delta.
    // Lo creamos ya para que el scroll-to-bottom y el streaming se vean fluidos.
    const assistantMessageId = `srv-pending-${Date.now()}`;
    const assistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setInput('');
    setIsLoading(true);
    setError(null);

    try {
      const streamed = await tryStream(
        sessionId,
        text,
        assistantMessageId,
        setMessages,
      );
      if (!streamed) {
        // Fallback al endpoint bloqueante si el navegador no soporta SSE
        // o el backend devolvió 404 sobre el endpoint stream.
        const ok = await sendBlockingAndReplace(
          sessionId,
          text,
          assistantMessageId,
          setMessages,
        );
        if (!ok) return; // error ya mostrado en setError
      }
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Ejecuta un agente (case_researcher, drafting_assistant, compliance_checker)
   * contra el backend. La respuesta reemplaza el placeholder del assistant y se
   * renderiza como bloques estructurados (summary, applicable_laws, etc.).
   */
  const sendAgent = async (text: string) => {
    const userMessage: ChatMessage = {
      id: `local-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date(),
    };
    const placeholderId = `agent-pending-${Date.now()}`;
    const placeholder: ChatMessage = {
      id: placeholderId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      agentKind: mode,
    };
    setMessages((prev) => [...prev, userMessage, placeholder]);
    setInput('');
    setIsLoading(true);
    setError(null);

    try {
      const res = await fetchJsonWithTimeout(
        '/api/v1/agents/run',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            agent_kind: mode,
            matter_id: contextInfo?.matterId,
            input: { query: text },
          }),
        },
        90_000,
      );
      if (res.status === 401) {
        setError('Tu sesión expiró. Vuelve a iniciar sesión.');
        setMessages((prev) => prev.slice(0, -2));
        return;
      }
      if (!res.ok) {
        throw new Error(`El agente no pudo ejecutarse (HTTP ${res.status})`);
      }
      const data = await res.json() as {
        id: number;
        status: string;
        output: Record<string, unknown>;
        error_message?: string;
      };
      if (data.status === 'failed') {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === placeholderId
              ? { ...m, content: data.error_message ?? 'El agente falló.', structured: data.output }
              : m,
          ),
        );
        return;
      }
      setMessages((prev) =>
        prev.map((m) =>
          m.id === placeholderId
            ? { ...m, content: formatAgentSummary(data.output, mode), structured: data.output, id: `agent-${data.id}` }
            : m,
        ),
      );
    } catch (err) {
      setMessages((prev) => prev.slice(0, -2));
      setError(err instanceof Error ? err.message : 'Error desconocido');
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Intenta consumir el endpoint SSE /chat/message/stream. Devuelve true
   * si el stream se conectó (aunque termine en error del LLM). Devuelve
   * false si el endpoint no existe o el navegador no soporta fetch streaming.
   */
  async function tryStream(
    sid: number,
    text: string,
    assistantId: string,
    setMsgs: React.Dispatch<React.SetStateAction<ChatMessage[]>>,
  ): Promise<boolean> {
    let res: Response;
    try {
      res = await fetchJsonWithTimeout(
        '/api/v1/chat/message/stream',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
          body: JSON.stringify({ session_id: sid, message: text }),
        },
        MESSAGE_REQUEST_TIMEOUT_MS,
      );
    } catch {
      return false;
    }
    if (res.status === 404 || res.status === 405) return false;
    if (res.status === 401) {
      setError('Tu sesión expiró. Vuelve a iniciar sesión.');
      rollback(setMsgs);
      return true;
    }
    if (!res.ok || !res.body) {
      return false;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let gotAnyDelta = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // Procesamos todos los eventos SSE completos en el buffer.
      let boundary: number;
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const rawEvent = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const lines = rawEvent.split('\n').filter((l) => l.startsWith('data: '));
        if (lines.length === 0) continue;
        const payload = lines.map((l) => l.slice(6)).join('\n');
        let parsed: { type: string; content?: string; message_id?: number; message?: string };
        try {
          parsed = JSON.parse(payload);
        } catch {
          continue;
        }
        if (parsed.type === 'delta' && typeof parsed.content === 'string') {
          gotAnyDelta = true;
          appendDelta(setMsgs, assistantId, parsed.content);
        } else if (parsed.type === 'done' && typeof parsed.message_id === 'number') {
          finalizeAssistant(setMsgs, assistantId, parsed.message_id);
        } else if (parsed.type === 'error') {
          setError(parsed.message ?? 'Error desconocido');
          return true;
        }
      }
    }
    return true;

    function rollback(set: typeof setMsgs) {
      set((prev) => prev.slice(0, -2));
    }
    function appendDelta(set: typeof setMsgs, id: string, chunk: string) {
      set((prev) =>
        prev.map((m) => (m.id === id ? { ...m, content: m.content + chunk } : m)),
      );
    }
    function finalizeAssistant(set: typeof setMsgs, id: string, serverId: number) {
      set((prev) =>
        prev.map((m) => (m.id === id ? { ...m, id: `srv-${serverId}` } : m)),
      );
    }
  }

  /**
   * Fallback al endpoint /chat/message que devuelve la respuesta completa.
   * Usado cuando SSE no está disponible.
   */
  async function sendBlockingAndReplace(
    sid: number,
    text: string,
    assistantId: string,
    setMsgs: React.Dispatch<React.SetStateAction<ChatMessage[]>>,
  ): Promise<boolean> {
    try {
      const res = await fetchJsonWithTimeout(
        '/api/v1/chat/message',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sid, message: text }),
        },
        MESSAGE_REQUEST_TIMEOUT_MS,
      );
      if (res.status === 401) {
        setError('Tu sesión expiró. Vuelve a iniciar sesión.');
        setMsgs((prev) => prev.slice(0, -2));
        return false;
      }
      if (!res.ok) {
        throw new Error(`El asistente no pudo responder (HTTP ${res.status})`);
      }
      const data = await res.json() as { content: string; message_id: number };
      setMsgs((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: data.content || '(Sin respuesta)', id: `srv-${data.message_id}` }
            : m,
        ),
      );
      return true;
    } catch (err) {
      setMsgs((prev) => prev.slice(0, -2));
      setError(err instanceof Error ? err.message : 'Error desconocido');
      return false;
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const markFeedback = (messageId: string, rating: -1 | 1, _correction: string | null) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === messageId ? { ...m, feedbackRating: rating } : m)),
    );
  };

  return (
    <>
      <div
        className={clsx(
          'fixed inset-0 bg-ink/20 backdrop-blur-sm z-40 transition-opacity duration-300',
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        )}
        onClick={onClose}
        aria-hidden={!isOpen}
      />

      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="chat-panel-title"
        aria-hidden={!isOpen}
        tabIndex={-1}
        className={clsx(
          'fixed top-0 right-0 h-full w-[380px] max-w-full flex flex-col',
          'bg-cream border-l border-border z-50 shadow-xl',
          'transition-transform duration-300 ease-out',
          isOpen ? 'translate-x-0' : 'translate-x-full'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border bg-soft2">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center">
              <BotIcon />
            </div>
            <div>
              <h3 id="chat-panel-title" className="font-heading font-bold text-ink">
                Asistente LILIAN
              </h3>
              <p className="text-xs text-ink/50">siempre disponible</p>
            </div>
          </div>
          <button
            ref={closeButtonRef}
            onClick={onClose}
            aria-label="Cerrar chat"
            className="w-8 h-8 rounded-lg flex items-center justify-center text-ink/50 hover:bg-soft hover:text-ink focus-visible:ring-2 focus-visible:ring-coral transition-colors"
          >
            <CloseIcon />
          </button>
        </div>

        {/* Context Banner */}
        {contextInfo?.matterTitle && (
          <div className="px-5 py-3 bg-blue-pale border-b border-border">
            <p className="text-xs text-blue font-semibold">Contexto actual</p>
            <p className="text-sm text-ink truncate">{contextInfo.matterTitle}</p>
          </div>
        )}

        {/* Error banner */}
        {error && (
          <div
            role="alert"
            className="px-5 py-3 bg-red-50 border-b border-red-200 flex items-start gap-2"
          >
            <span className="text-red-700 mt-0.5"><AlertIcon /></span>
            <p className="text-sm text-red-800 flex-1">{error}</p>
            <button
              onClick={() => setError(null)}
              aria-label="Cerrar mensaje de error"
              className="text-red-500 hover:text-red-700 text-xs"
            >
              ✕
            </button>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={clsx('flex gap-3', message.role === 'user' && 'flex-row-reverse')}
            >
              {message.role === 'assistant' && (
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center flex-shrink-0">
                  <BotIcon />
                </div>
              )}
              <div
                className={clsx(
                  'max-w-[80%] rounded-2xl px-4 py-3',
                  message.role === 'assistant'
                    ? 'bg-soft text-ink rounded-tl-sm'
                    : 'bg-coral text-white rounded-tr-sm'
                )}
              >
                <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
                <div className="flex items-center gap-3 mt-1">
                  <p className={clsx(
                    'text-[10px]',
                    message.role === 'assistant' ? 'text-ink/40' : 'text-white/60'
                  )}>
                    {message.timestamp.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}
                  </p>
                  {message.role === 'assistant' && message.feedbackRating === undefined && (
                    <FeedbackButtons messageId={message.id} onRated={(r, c) => markFeedback(message.id, r, c)} />
                  )}
                  {message.role === 'assistant' && message.feedbackRating !== undefined && (
                    <p className="text-[10px] text-ink/40 italic">
                      {message.feedbackRating === 1 ? 'Marcado como útil' : 'Gracias por tu feedback'}
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex gap-3" role="status" aria-live="polite">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center flex-shrink-0">
                <BotIcon />
              </div>
              <div className="bg-soft rounded-2xl rounded-tl-sm px-4 py-3">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-ink/30 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-2 h-2 bg-ink/30 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-2 h-2 bg-ink/30 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <span className="sr-only">El asistente está escribiendo...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t border-border bg-soft2">
          {/* Mode selector */}
          <div className="mb-2 flex items-center gap-2">
            <label htmlFor="lilian-mode" className="text-[11px] uppercase tracking-wider text-ink/50 font-semibold">
              Modo
            </label>
            <select
              id="lilian-mode"
              value={mode}
              onChange={(e) => setMode(e.target.value as AgentMode)}
              disabled={isLoading}
              className="flex-1 px-3 py-1.5 rounded-lg bg-cream border border-border text-xs text-ink focus:outline-none focus:ring-2 focus:ring-coral/30 focus:border-coral disabled:opacity-50"
              aria-label="Modo del asistente"
            >
              {AGENT_OPTIONS.map((opt) => (
                <option key={opt.kind} value={opt.kind}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <p className="text-[11px] text-ink/40 mb-2">
            {AGENT_OPTIONS.find((o) => o.kind === mode)?.description}
          </p>
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={mode === 'qa' && sessionId === null && error === null ? "Conectando..." : "Escribe tu consulta..."}
              aria-label="Escribe tu pregunta al asistente"
              disabled={mode === 'qa' && sessionId === null}
              className="flex-1 px-4 py-3 rounded-xl bg-cream border border-border text-sm text-ink placeholder-ink/40 focus:outline-none focus:ring-2 focus:ring-coral/30 focus:border-coral transition-all disabled:opacity-50"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading || (mode === 'qa' && sessionId === null)}
              aria-label="Enviar mensaje"
              aria-busy={isLoading}
              className="w-11 h-11 rounded-xl bg-coral text-white flex items-center justify-center hover:bg-coral-dark focus-visible:ring-2 focus-visible:ring-coral transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <SendIcon />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
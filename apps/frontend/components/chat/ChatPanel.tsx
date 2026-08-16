"use client";

import { useState, useRef, useEffect } from "react";
import { clsx } from 'clsx';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
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
    if (!text || isLoading || sessionId === null) return;
    if (text.length > CHAT_MESSAGE_MAX_LEN) {
      setError(`El mensaje supera el límite de ${CHAT_MESSAGE_MAX_LEN} caracteres.`);
      return;
    }

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
                <p className={clsx(
                  'text-[10px] mt-1',
                  message.role === 'assistant' ? 'text-ink/40' : 'text-white/60'
                )}>
                  {message.timestamp.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}
                </p>
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
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={sessionId === null && error === null ? "Conectando..." : "Escribe tu pregunta..."}
              aria-label="Escribe tu pregunta al asistente"
              disabled={sessionId === null}
              className="flex-1 px-4 py-3 rounded-xl bg-cream border border-border text-sm text-ink placeholder-ink/40 focus:outline-none focus:ring-2 focus:ring-coral/30 focus:border-coral transition-all disabled:opacity-50"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading || sessionId === null}
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
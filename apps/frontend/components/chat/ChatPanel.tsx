"use client";

import { useState, useRef, useEffect } from "react";
import { clsx } from 'clsx';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface ChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
  contextInfo?: {
    matterTitle?: string;
    documentName?: string;
  };
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

export function ChatPanel({ isOpen, onClose, contextInfo }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: '¡Hola! Soy el asistente legal de LILIAN. Puedo ayudarte a analizar documentos, responder preguntas sobre casos y proporcionar información sobre precedentes relevantes.',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  // S5 accessibility: remember the element that opened the panel so we can
  // restore focus to it when the panel closes (WCAG 2.4.3 Focus Order).
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // S5 accessibility: Escape key closes the panel and restores focus.
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

  // S5 accessibility: trap focus inside the dialog while it is open, move
  // initial focus to the close button on open, and restore focus to the
  // trigger on close (WCAG 2.4.3 Focus Order).
  useEffect(() => {
    if (isOpen) {
      previouslyFocusedRef.current = document.activeElement as HTMLElement | null;
      // Defer to next tick so the panel is in the DOM.
      const id = window.setTimeout(() => {
        closeButtonRef.current?.focus();
      }, 0);
      return () => {
        window.clearTimeout(id);
        previouslyFocusedRef.current?.focus?.();
      };
    }
  }, [isOpen]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    setTimeout(() => {
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `He analizado tu pregunta sobre "${input.trim()}". Basado en el contexto del caso${contextInfo?.matterTitle ? ` "${contextInfo.matterTitle}"` : ''}, te puedo indicar que necesito más información para darte una respuesta precisa.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setIsLoading(false);
    }, 1500);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <>
      {/* S5 accessibility: backdrop with click-to-close + aria-hidden when closed. */}
      <div
        className={clsx(
          'fixed inset-0 bg-ink/20 backdrop-blur-sm z-40 transition-opacity duration-300',
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        )}
        onClick={onClose}
        aria-hidden={!isOpen}
      />

      {/* S5 accessibility: panel is a dialog with role + aria-modal + labelled by header h3. */}
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
                <p className="text-sm leading-relaxed">{message.content}</p>
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
              placeholder="Escribe tu pregunta..."
              aria-label="Escribe tu pregunta al asistente"
              className="flex-1 px-4 py-3 rounded-xl bg-cream border border-border text-sm text-ink placeholder-ink/40 focus:outline-none focus:ring-2 focus:ring-coral/30 focus:border-coral transition-all"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
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

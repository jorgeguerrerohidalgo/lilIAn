"use client";

import { clsx } from 'clsx';

interface FloatingChatButtonProps {
  onClick: () => void;
  isOpen: boolean;
}

export function FloatingChatButton({ onClick, isOpen }: FloatingChatButtonProps) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        'fab fixed rounded-full flex items-center justify-center cursor-pointer',
        'transition-all duration-200 z-50',
        'bottom-6 right-6',
        'w-14 h-14',
        'bg-coral text-white',
        'hover:scale-105 active:scale-95',
        'shadow-lg hover:shadow-xl',
        isOpen && 'scale-0 opacity-0 pointer-events-none'
      )}
      style={{
        boxShadow: '0 8px 24px rgba(244, 74, 90, 0.35)',
      }}
      aria-label="Abrir chat con asistente"
      tabIndex={isOpen ? -1 : 0}
      aria-hidden={isOpen ? "true" : undefined}
    >
      {/* Bot Icon */}
      <svg aria-hidden="true" className="w-7 h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.556 4.03-8 9-8s9 3.444 9 8z" />
      </svg>
    </button>
  );
}

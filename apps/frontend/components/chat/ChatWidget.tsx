"use client";

import { useState } from "react";
import { FloatingChatButton } from "./FloatingChatButton";
import { ChatPanel } from "./ChatPanel";

interface ChatWidgetProps {
  contextInfo?: {
    matterId?: number;
    matterTitle?: string;
    documentName?: string;
  };
}

export function ChatWidget({ contextInfo }: ChatWidgetProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <FloatingChatButton onClick={() => setIsOpen(true)} isOpen={isOpen} />
      <ChatPanel isOpen={isOpen} onClose={() => setIsOpen(false)} contextInfo={contextInfo} />
    </>
  );
}

"use client";

import { useState } from "react";
import ChatInput from "./ChatInput";
import ChatWindow from "./ChatWindow";
import Navbar from "./Navbar";
import Sidebar from "./Sidebar";
import type { Attachment, Chat, Message, SourceCitation } from "./types";

function createId() {
  return Math.random().toString(36).slice(2, 10);
}

type ChatApiResponse = {
  question?: string;
  answer?: string;
  sources?: SourceCitation[];
  mode?: "rag" | "no_context" | "error" | "greeting";
  model?: string;
  error?: string;
  detail?: string;
};

export default function ChatShell() {
  const [chats, setChats] = useState<Chat[]>([]);
  const [messagesByChat, setMessagesByChat] = useState<Record<string, Message[]>>({});
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const messages = activeChatId ? messagesByChat[activeChatId] ?? [] : [];

  function handleNewChat() {
    const chat: Chat = { id: createId(), title: "New chat" };
    setChats((current) => [chat, ...current]);
    setMessagesByChat((current) => ({ ...current, [chat.id]: [] }));
    setActiveChatId(chat.id);
    setSidebarOpen(false);
  }

  function handleSelectChat(id: string) {
    setActiveChatId(id);
    setSidebarOpen(false);
  }

  function updateMessage(chatId: string, messageId: string, patch: Partial<Message>) {
    setMessagesByChat((current) => ({
      ...current,
      [chatId]: (current[chatId] ?? []).map((message) =>
        message.id === messageId ? { ...message, ...patch } : message,
      ),
    }));
  }

  async function handleSend(text: string, attachments: Attachment[]) {
    if (isSubmitting) return;

    const chatId = activeChatId ?? createId();

    if (!activeChatId) {
      const title = text.slice(0, 40) || attachments[0]?.name || "New chat";
      setChats((current) => [{ id: chatId, title }, ...current]);
      setActiveChatId(chatId);
    } else {
      setChats((current) =>
        current.map((chat) =>
          chat.id === chatId && chat.title === "New chat"
            ? { ...chat, title: text.slice(0, 40) || chat.title }
            : chat,
        ),
      );
    }

    const userMessage: Message = {
      id: createId(),
      role: "user",
      text,
      attachments: attachments.length > 0 ? attachments : undefined,
    };
    const assistantId = createId();
    const pendingMessage: Message = {
      id: assistantId,
      role: "assistant",
      text: "",
      status: "pending",
      loadingText: "Searching legal documents and generating explanation…",
    };

    setMessagesByChat((current) => ({
      ...current,
      [chatId]: [...(current[chatId] ?? []), userMessage, pendingMessage],
    }));

    setIsSubmitting(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: text }),
      });
      const data: ChatApiResponse = await response.json().catch(() => ({}));

      if (!response.ok) {
        updateMessage(chatId, assistantId, {
          text: data.detail ?? "Failed to generate answer.",
          status: "error",
        });
        return;
      }

      updateMessage(chatId, assistantId, {
        text: data.answer ?? "No explanation returned.",
        sources: data.sources ?? [],
        status: "complete",
        mode: data.mode,
        model: data.model,
      });
    } catch {
      updateMessage(chatId, assistantId, {
        text: "Could not reach the assistant service. Check that the backend is running.",
        status: "error",
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-white">
      <Navbar onToggleSidebar={() => setSidebarOpen((open) => !open)} />
      <div className="flex min-h-0 flex-1">
        <Sidebar
          chats={chats}
          activeChatId={activeChatId}
          onSelectChat={handleSelectChat}
          onNewChat={handleNewChat}
          isOpen={sidebarOpen}
        />
        <main className="flex min-w-0 flex-1 flex-col">
          <ChatWindow messages={messages} />
          <ChatInput onSend={handleSend} disabled={isSubmitting} />
        </main>
      </div>
    </div>
  );
}

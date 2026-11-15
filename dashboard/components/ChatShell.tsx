"use client";

import { useState } from "react";
import ChatInput from "./ChatInput";
import ChatWindow from "./ChatWindow";
import Navbar from "./Navbar";
import Sidebar from "./Sidebar";
import type { Attachment, Chat, Message } from "./types";

function createId() {
  return Math.random().toString(36).slice(2, 10);
}

export default function ChatShell() {
  const [chats, setChats] = useState<Chat[]>([]);
  const [messagesByChat, setMessagesByChat] = useState<Record<string, Message[]>>({});
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

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

  function handleSend(text: string, attachments: Attachment[]) {
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

    const message: Message = {
      id: createId(),
      role: "user",
      text,
      attachments: attachments.length > 0 ? attachments : undefined,
    };

    setMessagesByChat((current) => ({
      ...current,
      [chatId]: [...(current[chatId] ?? []), message],
    }));
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
          <ChatInput onSend={handleSend} />
        </main>
      </div>
    </div>
  );
}

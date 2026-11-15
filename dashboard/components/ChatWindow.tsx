"use client";

import type { Message } from "./types";

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

type ChatWindowProps = {
  messages: Message[];
};

export default function ChatWindow({ messages }: ChatWindowProps) {
  return (
    <div className="flex-1 overflow-y-auto bg-white px-4 py-6 sm:px-8">
      {messages.length === 0 ? (
        <div className="flex h-full flex-col items-center justify-center text-center">
          <span className="grid h-16 w-16 place-items-center rounded-full bg-red-50 text-red-600">
            <svg viewBox="0 0 24 24" className="h-8 w-8" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.9 8.9 0 0 1-3.9-.9L3 21l1.9-4.7A8.4 8.4 0 0 1 12 3.1a8.4 8.4 0 0 1 9 8.4Z" />
            </svg>
          </span>
          <h1 className="mt-4 text-xl font-semibold text-black">How can I help you today?</h1>
          <p className="mt-1 max-w-sm text-sm text-neutral-500">
            Ask a question, or attach a file with the + button to get started.
          </p>
        </div>
      ) : (
        <ul className="mx-auto flex max-w-3xl flex-col gap-4">
          {messages.map((message) => {
            const isUser = message.role === "user";
            return (
              <li
                key={message.id}
                className={`flex ${isUser ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed sm:max-w-[75%] ${
                    isUser
                      ? "rounded-br-sm bg-red-600 text-white"
                      : "rounded-bl-sm border border-neutral-200 bg-white text-black"
                  }`}
                >
                  {message.text && <p className="whitespace-pre-wrap">{message.text}</p>}

                  {message.attachments && message.attachments.length > 0 && (
                    <ul className="mt-2 flex flex-col gap-1">
                      {message.attachments.map((file) => (
                        <li
                          key={file.id}
                          className={`flex items-center gap-2 rounded-md px-2 py-1 text-xs ${
                            isUser ? "bg-black/20 text-white" : "bg-neutral-100 text-neutral-700"
                          }`}
                        >
                          <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                            <path d="M21.4 11.05 12.25 20.2a6 6 0 0 1-8.49-8.49l8.49-8.48a4 4 0 0 1 5.66 5.65l-8.49 8.49a2 2 0 0 1-2.83-2.83l7.78-7.78" />
                          </svg>
                          <span className="truncate">{file.name}</span>
                          <span className={isUser ? "text-white/70" : "text-neutral-400"}>
                            {formatSize(file.size)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

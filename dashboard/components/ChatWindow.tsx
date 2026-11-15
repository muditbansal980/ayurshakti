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
            Ask any question about Indian intellectual property laws, biodiversity regulations, or Ayurveda innovation.
          </p>
        </div>
      ) : (
        <ul className="mx-auto flex max-w-3xl flex-col gap-4">
          {messages.map((message) => {
            const isUser = message.role === "user";
            const isLoading = message.status === "pending" || message.status === "generating";

            return (
              <li
                key={message.id}
                className={`flex ${isUser ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed sm:max-w-[75%] ${
                    isUser
                      ? "rounded-br-sm bg-red-600 text-white"
                      : "rounded-bl-sm border border-neutral-200 bg-white text-black shadow-xs"
                  }`}
                >
                  {isLoading ? (
                    <div className="flex items-center gap-2 text-neutral-500">
                      <svg
                        className="h-4 w-4 animate-spin text-red-600"
                        viewBox="0 0 24 24"
                        fill="none"
                      >
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="3"
                        />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                        />
                      </svg>
                      <span className="text-xs">
                        {message.loadingText ?? "Searching legal documents and generating explanation…"}
                      </span>
                    </div>
                  ) : (
                    message.status !== "error" &&
                    message.text && (
                      <div className="whitespace-pre-wrap">{message.text}</div>
                    )
                  )}

                  {message.status === "error" && (
                    <p className="mt-1 text-xs text-red-600">{message.text}</p>
                  )}

                  {/* Render structured sources from RAG generation */}
                  {!isLoading && message.sources && message.sources.length > 0 && (
                    <div className="mt-3 border-t border-neutral-200 pt-2">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                        Sources Cited
                      </p>
                      <ul className="mt-1 flex flex-col gap-1.5">
                        {message.sources.map((src) => (
                          <li key={src.id} className="text-xs text-neutral-600">
                            <span className="mr-1.5 inline-flex items-center rounded-sm bg-red-50 px-1 py-0.5 text-[10px] font-semibold text-red-700">
                              [{src.id}]
                            </span>
                            <span className="font-medium text-neutral-800">
                              {src.title}
                            </span>
                            {src.provision ? `, ${src.provision}` : ""}
                            {src.review_status === "needs_review" && (
                              <span className="ml-1 rounded bg-amber-50 px-1 text-[10px] text-amber-700">
                                unreviewed
                              </span>
                            )}
                          </li>
                        ))}
                      </ul>
                      <p className="mt-2 text-[10px] italic text-neutral-400">
                        Sources referenced from indexed legal corpus. Not personalized legal advice.
                      </p>
                    </div>
                  )}

                  {/* Fallback support for legacy search citations */}
                  {!isLoading && !message.sources && message.citations && message.citations.length > 0 && (
                    <div className="mt-3 border-t border-neutral-200 pt-2">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                        Sources
                      </p>
                      <ul className="mt-1 flex flex-col gap-1">
                        {message.citations.map((citation, index) => (
                          <li key={index} className="text-xs text-neutral-600">
                            <span className="font-medium text-neutral-800">
                              {citation.title ?? "Untitled source"}
                            </span>
                            {citation.provision ? `, ${citation.provision}` : ""}
                            {citation.review_status === "needs_review" && (
                              <span className="ml-1 rounded bg-amber-50 px-1 text-[10px] text-amber-700">
                                unreviewed
                              </span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

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

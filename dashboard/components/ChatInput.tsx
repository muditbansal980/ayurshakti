"use client";

import { useRef, useState } from "react";
import type { Attachment } from "./types";

type ChatInputProps = {
  onSend: (text: string, attachments: Attachment[]) => void;
  disabled?: boolean;
};

export default function ChatInput({ onSend, disabled = false }: ChatInputProps) {
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const canSend = !disabled && (text.trim().length > 0 || attachments.length > 0);

  function handleFiles(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    setAttachments((current) => [
      ...current,
      ...files.map((file) => ({
        id: `${file.name}-${file.lastModified}-${Math.random().toString(36).slice(2, 8)}`,
        name: file.name,
        size: file.size,
      })),
    ]);
    event.target.value = "";
  }

  function removeAttachment(id: string) {
    setAttachments((current) => current.filter((file) => file.id !== id));
  }

  function submit() {
    if (!canSend) return;
    onSend(text.trim(), attachments);
    setText("");
    setAttachments([]);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <div className="border-t border-neutral-200 bg-white px-4 py-4 sm:px-8">
      <div className="mx-auto max-w-3xl">
        {attachments.length > 0 && (
          <ul className="mb-2 flex flex-wrap gap-2">
            {attachments.map((file) => (
              <li
                key={file.id}
                className="flex items-center gap-2 rounded-md border border-neutral-200 bg-neutral-50 py-1 pl-2 pr-1 text-xs text-neutral-700"
              >
                <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 shrink-0 text-red-600" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21.4 11.05 12.25 20.2a6 6 0 0 1-8.49-8.49l8.49-8.48a4 4 0 0 1 5.66 5.65l-8.49 8.49a2 2 0 0 1-2.83-2.83l7.78-7.78" />
                </svg>
                <span className="max-w-40 truncate">{file.name}</span>
                <button
                  type="button"
                  onClick={() => removeAttachment(file.id)}
                  aria-label={`Remove ${file.name}`}
                  className="grid h-5 w-5 place-items-center rounded text-neutral-400 hover:bg-neutral-200 hover:text-black"
                >
                  <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round">
                    <path d="M18 6 6 18M6 6l12 12" />
                  </svg>
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className={`flex items-end gap-2 rounded-xl border border-neutral-300 bg-white p-2 focus-within:border-red-600 ${disabled ? "opacity-70" : ""}`}>
          <button
            type="button"
            disabled={true}
            title="File uploads are currently unavailable"
            aria-label="File upload disabled"
            className="grid h-9 w-9 shrink-0 cursor-not-allowed place-items-center rounded-lg border border-neutral-200 text-neutral-400 opacity-60"
          >
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round">
              <path d="M12 5v14M5 12h14" />
            </svg>
          </button>

          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFiles}
            className="hidden"
            disabled={true}
          />

          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={disabled}
            placeholder={disabled ? "Generating answer…" : "Message AyurSakti…"}
            className="max-h-40 min-h-9 flex-1 resize-none bg-transparent px-1 py-2 text-sm text-black placeholder:text-neutral-400 focus:outline-none disabled:cursor-not-allowed"
          />

          <button
            type="button"
            onClick={submit}
            disabled={!canSend}
            aria-label="Send message"
            className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-red-600 text-white transition-colors hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-neutral-200 disabled:text-neutral-400"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7Z" />
            </svg>
          </button>
        </div>

        <p className="mt-2 text-center text-[11px] text-neutral-400">
          Enter to send · Shift + Enter for a new line
        </p>
      </div>
    </div>
  );
}

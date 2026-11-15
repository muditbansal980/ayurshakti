"use client";

import type { Chat } from "./types";

type SidebarProps = {
  chats: Chat[];
  activeChatId: string | null;
  onSelectChat: (id: string) => void;
  onNewChat: () => void;
  isOpen: boolean;
};

export default function Sidebar({
  chats,
  activeChatId,
  onSelectChat,
  onNewChat,
  isOpen,
}: SidebarProps) {
  return (
    <aside
      className={`${
        isOpen ? "flex" : "hidden"
      } w-full shrink-0 flex-col border-r border-neutral-200 bg-white md:flex md:w-64`}
    >
      <div className="flex items-center justify-between border-b border-neutral-200 px-4 py-3">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-neutral-500">
          Chats
        </h2>
        <button
          type="button"
          onClick={onNewChat}
          aria-label="New chat"
          className="grid h-8 w-8 place-items-center rounded-md bg-red-600 text-white transition-colors hover:bg-red-700"
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round">
            <path d="M12 5v14M5 12h14" />
          </svg>
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto p-2">
        {chats.length === 0 ? (
          <p className="px-3 py-6 text-center text-sm text-neutral-400">
            No chats yet. Start a new one.
          </p>
        ) : (
          <ul className="flex flex-col gap-1">
            {chats.map((chat) => {
              const isActive = chat.id === activeChatId;
              return (
                <li key={chat.id}>
                  <button
                    type="button"
                    onClick={() => onSelectChat(chat.id)}
                    className={`w-full truncate rounded-md px-3 py-2 text-left text-sm transition-colors ${
                      isActive
                        ? "bg-red-50 font-medium text-red-700"
                        : "text-neutral-700 hover:bg-neutral-100"
                    }`}
                  >
                    {chat.title}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </nav>

      <div className="border-t border-neutral-200 px-4 py-3">
        <p className="text-xs text-neutral-400">AyurSakti dashboard</p>
      </div>
    </aside>
  );
}

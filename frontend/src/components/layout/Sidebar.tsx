import { useMemo, useState } from "react";
import { useJarvis } from "../../context/JarvisContext";
import { formatDate } from "../../lib/format";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { UserPanel } from "./UserPanel";

export function Sidebar() {
  const {
    chats,
    chatSearch,
    setChatSearch,
    pinnedIds,
    archivedIds,
    togglePin,
    toggleArchive,
    activeChatId,
    loadConversation,
    createNewChat,
    deleteConversation,
    renameConversation,
    setTab,
    sidebarCollapsed,
    setSidebarCollapsed,
    sidebarMobileOpen,
    setSidebarMobileOpen,
    isMobile,
    tab,
  } = useJarvis();

  const [showArchived, setShowArchived] = useState(false);

  const filtered = useMemo(() => {
    const q = chatSearch.trim().toLowerCase();
    let list = chats.filter((c) =>
      showArchived ? archivedIds.has(c.id) : !archivedIds.has(c.id)
    );
    if (q) list = list.filter((c) => (c.title || "").toLowerCase().includes(q));
    const pin = list.filter((c) => pinnedIds.has(c.id)).sort((a, b) => b.id - a.id);
    const rest = list.filter((c) => !pinnedIds.has(c.id)).sort((a, b) => b.id - a.id);
    return [...pin, ...rest].slice(0, 50);
  }, [chats, chatSearch, pinnedIds, archivedIds, showArchived]);

  const narrow = !isMobile && sidebarCollapsed;

  return (
    <>
      <aside
        className={`relative z-30 flex h-full min-h-0 flex-col border-r border-white/[0.06] bg-slate-950/50 shadow-[inset_-1px_0_0_rgba(255,255,255,0.04)] backdrop-blur-2xl transition-[width] duration-300 ease-out ${
          narrow ? "w-[76px]" : "w-[280px]"
        } ${isMobile ? "fixed inset-y-3 left-3 z-40 max-w-[min(280px,calc(100vw-24px))] rounded-2xl border border-white/10" : ""} ${
          isMobile && !sidebarMobileOpen ? "-translate-x-[calc(100%+24px)]" : "translate-x-0"
        }`}
      >
        <div className={`flex items-center gap-2 p-3 ${narrow ? "flex-col" : ""}`}>
          <div
            className={`flex min-w-0 flex-1 items-center gap-3 ${narrow ? "justify-center" : ""}`}
          >
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-sky-400/25 bg-gradient-to-br from-sky-500/20 to-violet-600/20 text-lg">
              ⚡
            </div>
            {!narrow && (
              <div className="min-w-0">
                <div className="truncate font-display text-base font-semibold text-white">Jarvis</div>
                <div className="truncate text-[11px] font-medium uppercase tracking-wider text-slate-500">
                  AI Workspace
                </div>
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={() => (isMobile ? setSidebarMobileOpen(false) : setSidebarCollapsed((c) => !c))}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] text-slate-300 transition hover:bg-white/[0.08] hover:text-white"
            aria-label={isMobile ? "Close sidebar" : "Collapse sidebar"}
          >
            {isMobile ? "×" : narrow ? "»" : "«"}
          </button>
        </div>

        <div className={`px-3 pb-2 ${narrow ? "px-2" : ""}`}>
          <Button
            onClick={() => void createNewChat({ clearFile: true })}
            className={`w-full py-3 ${narrow ? "!px-0" : ""}`}
            title="New chat"
          >
            <span className="text-lg leading-none">+</span>
            {!narrow && <span>New chat</span>}
          </Button>
        </div>

        <nav className={`flex flex-col gap-1 px-3 pb-3 ${narrow ? "px-2" : ""}`}>
          {(
            [
              { id: "chat" as const, label: "Chat", icon: "💬" },
              { id: "notes" as const, label: "Notes", icon: "📝" },
              { id: "history" as const, label: "History", icon: "🕐" },
            ] as const
          ).map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setTab(item.id)}
              className={`flex items-center gap-3 rounded-xl border px-3 py-2.5 text-left text-sm font-medium transition ${
                narrow ? "justify-center px-2" : ""
              } ${
                tab === item.id
                  ? "border-sky-500/30 bg-sky-500/10 text-white"
                  : "border-transparent text-slate-400 hover:border-white/10 hover:bg-white/[0.04] hover:text-slate-100"
              }`}
              title={item.label}
            >
              <span className="text-base">{item.icon}</span>
              {!narrow && item.label}
            </button>
          ))}
        </nav>

        {!narrow && (
          <div className="px-3 pb-2">
            <Input
              placeholder="Search chats…"
              value={chatSearch}
              onChange={(e) => setChatSearch(e.target.value)}
              className="py-2 text-xs"
              aria-label="Search chats"
            />
          </div>
        )}

        <div className={`flex min-h-0 flex-1 flex-col px-3 pb-2 ${narrow ? "px-2" : ""}`}>
          {!narrow && (
            <div className="mb-2 flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              <span>{showArchived ? "Archived" : "Recent"}</span>
              <div className="flex gap-1">
                <button
                  type="button"
                  onClick={() => setShowArchived((s) => !s)}
                  className="rounded-md px-2 py-0.5 text-sky-400/90 hover:bg-white/5"
                >
                  {showArchived ? "Back" : "Archive"}
                </button>
                <button
                  type="button"
                  onClick={() => setTab("history")}
                  className="rounded-md px-2 py-0.5 text-sky-400/90 hover:bg-white/5"
                >
                  All
                </button>
              </div>
            </div>
          )}
          <div className="scrollbar-thin flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto pr-0.5">
            {filtered.length === 0 && (
              <div className="rounded-xl border border-dashed border-white/10 px-3 py-6 text-center text-xs text-slate-500">
                {!narrow && "No chats match. Start a new one."}
              </div>
            )}
            {filtered.map((c) => (
              <div
                key={c.id}
                className={`group relative rounded-xl border transition ${
                  activeChatId === c.id
                    ? "border-sky-500/35 bg-sky-500/10 shadow-[0_0_0_1px_rgba(56,189,248,0.12)]"
                    : "border-transparent bg-white/[0.02] hover:border-white/10 hover:bg-white/[0.05]"
                }`}
              >
                <button
                  type="button"
                  onClick={() => void loadConversation(c.id)}
                  className={`flex w-full min-w-0 flex-col gap-0.5 px-3 py-2.5 text-left ${narrow ? "items-center px-2" : ""}`}
                >
                  {pinnedIds.has(c.id) && !narrow && (
                    <span className="text-[10px] font-semibold uppercase tracking-wide text-amber-400/90">
                      Pinned
                    </span>
                  )}
                  <span
                    className={`truncate text-sm font-medium text-slate-100 ${narrow ? "max-w-[2.5rem] text-center text-xs" : ""}`}
                  >
                    {narrow ? c.title?.charAt(0) || "·" : c.title || "Untitled"}
                  </span>
                  {!narrow && (
                    <span className="text-[11px] text-slate-500">{formatDate(c.created_at)}</span>
                  )}
                </button>
                {!narrow && (
                  <div className="absolute right-1 top-1 flex gap-0.5 opacity-0 transition group-hover:opacity-100">
                    <button
                      type="button"
                      title="Pin"
                      className="rounded-lg p-1 text-xs text-slate-400 hover:bg-white/10 hover:text-amber-300"
                      onClick={(e) => {
                        e.stopPropagation();
                        togglePin(c.id);
                      }}
                    >
                      📌
                    </button>
                    <button
                      type="button"
                      title="Rename"
                      className="rounded-lg p-1 text-xs text-slate-400 hover:bg-white/10 hover:text-sky-300"
                      onClick={(e) => {
                        e.stopPropagation();
                        const t = prompt("Chat title", c.title || "");
                        if (t?.trim()) void renameConversation(c.id, t.trim());
                      }}
                    >
                      ✎
                    </button>
                    <button
                      type="button"
                      title="Archive"
                      className="rounded-lg p-1 text-xs text-slate-400 hover:bg-white/10"
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleArchive(c.id);
                      }}
                    >
                      📥
                    </button>
                    <button
                      type="button"
                      title="Delete"
                      className="rounded-lg p-1 text-xs text-slate-400 hover:bg-white/10 hover:text-rose-400"
                      onClick={(e) => {
                        e.stopPropagation();
                        void deleteConversation(c.id);
                      }}
                    >
                      🗑
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        <UserPanel narrow={narrow} />
      </aside>
    </>
  );
}

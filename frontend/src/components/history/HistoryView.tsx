import { useJarvis } from "../../context/JarvisContext";
import { formatDate } from "../../lib/format";
import { AppHeader } from "../layout/AppHeader";
import { Card } from "../ui/Card";
import { Skeleton } from "../ui/Skeleton";

export function HistoryView() {
  const {
    chats,
    historyLoading,
    loadConversation,
    deleteConversation,
    setSidebarMobileOpen,
  } = useJarvis();

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-white/[0.06] bg-slate-950/30 lg:rounded-3xl">
      <AppHeader onOpenSidebar={() => setSidebarMobileOpen(true)} />
      <div className="flex min-h-0 flex-1 flex-col p-4 sm:p-6">
        <div className="mb-6">
          <h2 className="font-display text-2xl font-semibold text-white">Chat history</h2>
          <p className="text-sm text-slate-500">Open, rename from sidebar, or remove old threads</p>
        </div>

        <div className="scrollbar-thin flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto rounded-2xl border border-white/[0.06] bg-black/20 p-2">
          {historyLoading &&
            Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="rounded-xl p-4">
                <Skeleton className="mb-2 h-4 w-2/3" />
                <Skeleton className="h-3 w-1/3" />
              </div>
            ))}

          {!historyLoading && chats.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <span className="mb-3 text-4xl opacity-40">🕐</span>
              <p className="text-slate-400">No conversations yet. Start chatting!</p>
            </div>
          )}

          {!historyLoading &&
            chats.map((c) => (
              <Card
                key={c.id}
                className="group flex cursor-pointer items-center justify-between gap-4 p-4 transition hover:border-sky-500/25"
                onClick={() => void loadConversation(c.id)}
              >
                <div className="min-w-0">
                  <h4 className="truncate font-display font-semibold text-white">{c.title}</h4>
                  <span className="text-xs text-slate-500">{formatDate(c.created_at)}</span>
                </div>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    void deleteConversation(c.id);
                  }}
                  className="shrink-0 rounded-lg border border-white/10 px-3 py-1.5 text-xs font-medium text-slate-400 opacity-0 transition hover:border-rose-500/30 hover:text-rose-300 group-hover:opacity-100"
                >
                  Delete
                </button>
              </Card>
            ))}
        </div>
      </div>
    </div>
  );
}

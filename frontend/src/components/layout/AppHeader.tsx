import { useJarvis } from "../../context/JarvisContext";

export function AppHeader({ onOpenSidebar }: { onOpenSidebar: () => void }) {
  const { chatTitle, activeFile, healthOnline, healthLabel, activeChatId } = useJarvis();

  return (
    <header className="flex shrink-0 items-center justify-between gap-3 border-b border-white/[0.06] bg-slate-950/40 px-3 py-3 backdrop-blur-xl sm:px-5">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <button
          type="button"
          onClick={onOpenSidebar}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-slate-200 lg:hidden"
          aria-label="Open sidebar"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500">
            Jarvis AI Assistant
          </p>
          <h1 className="truncate font-display text-lg font-semibold text-white sm:text-xl">{chatTitle}</h1>
        </div>
        {activeFile && activeChatId && (
          <span className="hidden max-w-[140px] items-center gap-1 truncate rounded-full border border-sky-500/25 bg-sky-500/10 px-2.5 py-1 text-[11px] font-medium text-sky-200 sm:inline-flex">
            📄 {activeFile.name}
          </span>
        )}
      </div>
      <div
        className={`flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium ${
          healthOnline
            ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-200"
            : "border-amber-500/25 bg-amber-500/10 text-amber-200"
        }`}
      >
        <span
          className={`h-2 w-2 rounded-full ${healthOnline ? "animate-pulse bg-emerald-400" : "bg-amber-400"}`}
        />
        {healthLabel}
      </div>
    </header>
  );
}

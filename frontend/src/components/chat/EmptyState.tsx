import { SuggestionChips } from "./SuggestionChips";

export function EmptyState({ onSuggestion }: { onSuggestion: (msg: string) => void }) {
  return (
    <div className="flex min-h-[min(60vh,520px)] flex-col items-center justify-center gap-6 px-4 py-12 text-center">
      <div className="rounded-full border border-sky-400/20 bg-gradient-to-br from-sky-500/15 to-violet-600/15 px-4 py-1.5 text-[11px] font-bold uppercase tracking-[0.2em] text-sky-300/90">
        Premium assistant
      </div>
      <div className="flex h-20 w-20 items-center justify-center rounded-3xl border border-white/10 bg-white/[0.04] text-4xl shadow-glow">
        ⚡
      </div>
      <div className="max-w-lg space-y-2">
        <h2 className="font-display text-3xl font-semibold tracking-tight text-white sm:text-4xl">
          What should we tackle first?
        </h2>
        <p className="text-sm leading-relaxed text-slate-400">
          Ask naturally, attach files, or switch modes for images. Your workspace stays fast, private, and
          demo-ready.
        </p>
      </div>
      <SuggestionChips onPick={onSuggestion} />
    </div>
  );
}

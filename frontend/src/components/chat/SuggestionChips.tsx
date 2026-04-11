const SUGGESTIONS = [
  { label: "Introduce yourself", msg: "Hello Jarvis! Who are you?" },
  { label: "Today’s date", msg: "What's today's date?" },
  { label: "Current time", msg: "What time is it?" },
  { label: "Capabilities", msg: "How can you help me?" },
];

export function SuggestionChips({ onPick }: { onPick: (msg: string) => void }) {
  return (
    <div className="flex flex-wrap justify-center gap-2">
      {SUGGESTIONS.map((s) => (
        <button
          key={s.label}
          type="button"
          onClick={() => onPick(s.msg)}
          className="rounded-full border border-white/[0.08] bg-white/[0.04] px-4 py-2.5 text-left text-sm font-medium text-slate-300 transition hover:border-sky-500/30 hover:bg-sky-500/10 hover:text-white"
        >
          {s.label}
        </button>
      ))}
    </div>
  );
}

import type { AgentMode } from "../../types";

const OPTIONS: { value: AgentMode; label: string; hint: string }[] = [
  { value: "auto", label: "Auto", hint: "Route intelligently" },
  { value: "chat", label: "Chat", hint: "Text with Groq" },
  { value: "generate_image", label: "Create", hint: "Image generation" },
  { value: "analyze_image", label: "Vision", hint: "Image analysis" },
];

export function ModeSelector({
  value,
  onChange,
}: {
  value: AgentMode;
  onChange: (v: AgentMode) => void;
}) {
  const meta = OPTIONS.find((o) => o.value === value) || OPTIONS[0];

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/[0.08] bg-black/25 px-3 py-2.5 backdrop-blur-sm">
      <label className="flex min-w-0 flex-1 items-center gap-2 sm:max-w-[55%]">
        <span className="whitespace-nowrap text-[10px] font-bold uppercase tracking-wider text-slate-500">
          Mode
        </span>
        <select
          value={value}
          onChange={(e) => onChange(e.target.value as AgentMode)}
          className="min-w-0 flex-1 cursor-pointer rounded-xl border border-white/10 bg-slate-900/90 py-2 pl-3 pr-8 text-sm font-medium text-slate-100 outline-none focus:border-sky-500/40 focus:ring-2 focus:ring-sky-500/15"
          aria-label="Select mode"
        >
          {OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
      <div className="flex items-center gap-2 text-right">
        <span className="hidden text-[10px] font-bold uppercase tracking-wider text-slate-500 sm:inline">
          Active
        </span>
        <span className="rounded-full border border-sky-500/25 bg-sky-500/10 px-3 py-1 text-xs font-semibold text-sky-200">
          {meta.label}
        </span>
      </div>
      <p className="w-full text-[11px] text-slate-500">{meta.hint}</p>
    </div>
  );
}

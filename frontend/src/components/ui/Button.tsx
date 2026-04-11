import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "ghost" | "danger" | "subtle";

const variants: Record<Variant, string> = {
  primary:
    "bg-gradient-to-br from-sky-400 via-sky-500 to-violet-500 text-slate-950 font-semibold shadow-glow-sm hover:brightness-110 active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none",
  ghost:
    "border border-white/10 bg-white/[0.04] text-slate-100 hover:bg-white/[0.08] hover:border-white/15 active:scale-[0.99]",
  danger: "border border-rose-500/30 bg-rose-500/10 text-rose-200 hover:bg-rose-500/15",
  subtle: "text-slate-400 hover:text-slate-100 hover:bg-white/[0.05]",
};

export function Button({
  variant = "primary",
  className = "",
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; children: ReactNode }) {
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm transition-all duration-200 ${variants[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

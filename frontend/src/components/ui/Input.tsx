import type { InputHTMLAttributes } from "react";

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`w-full rounded-xl border border-white/10 bg-black/30 px-3.5 py-3 text-sm text-slate-100 outline-none transition-all placeholder:text-slate-500 focus:border-sky-500/40 focus:ring-2 focus:ring-sky-500/20 ${className}`}
      {...props}
    />
  );
}

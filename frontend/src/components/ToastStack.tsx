import { useJarvis } from "../context/JarvisContext";

export function ToastStack() {
  const { toasts, dismissToast } = useJarvis();

  return (
    <div
      className="pointer-events-none fixed bottom-5 right-5 z-[100] flex max-w-sm flex-col gap-2 sm:left-5 sm:right-5"
      aria-live="polite"
    >
      {toasts.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => dismissToast(t.id)}
          className={`pointer-events-auto w-full rounded-xl border px-4 py-3 text-left text-sm shadow-glow backdrop-blur-xl transition hover:brightness-110 ${
            t.type === "error"
              ? "border-amber-500/25 bg-amber-500/10 text-amber-50"
              : t.type === "success"
                ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-50"
                : "border-white/10 bg-slate-900/90 text-slate-100"
          }`}
        >
          {t.message}
        </button>
      ))}
    </div>
  );
}

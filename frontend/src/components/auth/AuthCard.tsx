import { useState } from "react";
import { useJarvis } from "../../context/JarvisContext";
import { ApiError } from "../../lib/api";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Input } from "../ui/Input";

export function AuthCard() {
  const {
    authMode,
    setAuthMode,
    login,
    signup,
    authBanner,
    setAuthBanner,
    showToast,
  } = useJarvis();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [busy, setBusy] = useState(false);

  const isLogin = authMode === "login";

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const em = email.trim();
    if (!em || !password) {
      setAuthBanner({ text: "Please enter your email and password.", variant: "error" });
      return;
    }
    setBusy(true);
    setAuthBanner({ text: isLogin ? "Signing you in…" : "Creating your account…", variant: "neutral" });
    try {
      if (isLogin) {
        await login(em, password);
        setPassword("");
      } else {
        await signup(em, password);
        setPassword("");
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Something went wrong.";
      setAuthBanner({ text: msg, variant: "error" });
      showToast(msg, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-full flex-col items-center justify-center p-4 sm:p-8">
      <div
        className="pointer-events-none absolute inset-0 overflow-hidden"
        aria-hidden
      >
        <div className="absolute -left-32 top-20 h-72 w-72 rounded-full bg-sky-500/15 blur-[100px]" />
        <div className="absolute -right-20 bottom-32 h-96 w-96 rounded-full bg-violet-500/12 blur-[110px]" />
      </div>

      <Card className="relative z-10 w-full max-w-[440px] p-8 sm:p-10">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-sky-400/30 bg-gradient-to-br from-sky-400/20 to-violet-500/20 text-2xl shadow-glow-sm">
            ⚡
          </div>
          <h1 className="font-display text-3xl font-semibold tracking-tight text-white sm:text-[2rem]">
            Jarvis
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            Premium AI workspace — sign in to continue
          </p>
        </div>

        <div className="mb-6 flex rounded-xl border border-white/[0.06] bg-black/25 p-1">
          <button
            type="button"
            onClick={() => {
              setAuthMode("login");
              setAuthBanner(null);
            }}
            className={`flex-1 rounded-lg py-2.5 text-sm font-medium transition ${
              isLogin
                ? "bg-white/[0.1] text-white shadow-inner"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            Login
          </button>
          <button
            type="button"
            onClick={() => {
              setAuthMode("signup");
              setAuthBanner(null);
            }}
            className={`flex-1 rounded-lg py-2.5 text-sm font-medium transition ${
              !isLogin
                ? "bg-white/[0.1] text-white shadow-inner"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            Sign up
          </button>
        </div>

        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <div>
            <label htmlFor="auth-email" className="mb-1.5 block text-xs font-medium text-slate-400">
              Email
            </label>
            <Input
              id="auth-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div>
            <label htmlFor="auth-password" className="mb-1.5 block text-xs font-medium text-slate-400">
              Password
            </label>
            <div className="relative">
              <Input
                id="auth-password"
                type={showPw ? "text" : "password"}
                autoComplete={isLogin ? "current-password" : "new-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                className="pr-24"
              />
              <button
                type="button"
                onClick={() => setShowPw((s) => !s)}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg px-2 py-1 text-xs font-medium text-sky-400/90 hover:bg-white/5"
              >
                {showPw ? "Hide" : "Show"}
              </button>
            </div>
          </div>

          {authBanner && (
            <div
              role="status"
              className={`rounded-xl border px-3 py-2.5 text-center text-sm ${
                authBanner.variant === "error"
                  ? "border-amber-500/30 bg-amber-500/10 text-amber-100"
                  : authBanner.variant === "success"
                    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-100"
                    : "border-white/10 bg-white/[0.04] text-slate-300"
              }`}
            >
              {authBanner.text}
            </div>
          )}

          <Button type="submit" disabled={busy} className="mt-1 w-full py-3">
            {busy ? "Please wait…" : isLogin ? "Continue" : "Create account"}
          </Button>
        </form>

        <p className="mt-6 text-center text-xs text-slate-500">
          Encrypted session · Same-origin API · No third-party analytics
        </p>
      </Card>
    </div>
  );
}

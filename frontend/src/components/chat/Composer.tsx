import { useCallback, useEffect, useRef } from "react";
import { useJarvis } from "../../context/JarvisContext";
import { formatBytes } from "../../lib/format";
import { ModeSelector } from "./ModeSelector";

export function Composer() {
  const {
    composerText,
    setComposerText,
    sendMessage,
    isSending,
    selectedAgent,
    setSelectedAgent,
    activeFile,
    clearActiveFile,
    pendingImage,
    clearPendingImage,
    triggerFilePicker,
    fileInputRef,
    onFileSelected,
    showToast,
  } = useJarvis();

  const taRef = useRef<HTMLTextAreaElement>(null);

  const resize = useCallback(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
  }, []);

  useEffect(() => {
    resize();
  }, [composerText, resize]);

  const placeholder = (() => {
    if (activeFile) return `Ask about "${activeFile.name}"…`;
    if (pendingImage) return "Ask a question about this image…";
    if (selectedAgent === "generate_image") return "Describe the image to create…";
    return "Message Jarvis…";
  })();

  const hint = (() => {
    if (activeFile) return "Document mode — answers use your uploaded file.";
    if (pendingImage) return "Image attached — optional question, then send.";
    if (selectedAgent === "generate_image") return "Describe the scene; Jarvis routes to the image generator.";
    if (selectedAgent === "analyze_image") return "Attach an image or drop one in the chat area.";
    if (selectedAgent === "chat") return "Chat mode — prompts go straight to the text model.";
    return "Enter to send · Shift+Enter newline · drop files to attach";
  })();

  function startListening() {
    const w = window as unknown as {
      SpeechRecognition?: new () => {
        lang: string;
        interimResults: boolean;
        maxAlternatives: number;
        onresult: ((ev: { results: ArrayLike<{ 0: { transcript: string } }> }) => void) | null;
        onerror: (() => void) | null;
        start: () => void;
      };
      webkitSpeechRecognition?: new () => {
        lang: string;
        interimResults: boolean;
        maxAlternatives: number;
        onresult: ((ev: { results: ArrayLike<{ 0: { transcript: string } }> }) => void) | null;
        onerror: (() => void) | null;
        start: () => void;
      };
    };
    const SR = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!SR) {
      showToast("Speech recognition not supported in this browser.", "error");
      return;
    }
    const rec = new SR();
    rec.lang = "en-US";
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    rec.onresult = (ev) => {
      const t = ev.results[0][0].transcript.trim();
      if (t) {
        setComposerText(t);
        void sendMessage(t);
      }
    };
    rec.onerror = () => showToast("Voice input error.", "error");
    try {
      rec.start();
    } catch {
      showToast("Could not start microphone.", "error");
    }
  }

  return (
    <div className="pointer-events-auto border-t border-white/[0.06] bg-gradient-to-t from-[#070a12] via-[#070a12]/95 to-transparent px-3 pb-4 pt-3 sm:px-4">
      <div className="mx-auto w-full max-w-3xl space-y-3">
        <ModeSelector value={selectedAgent} onChange={setSelectedAgent} />

        {activeFile && (
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-sky-500/20 bg-sky-500/5 px-3 py-2 text-sm">
            <div className="flex min-w-0 items-center gap-2">
              <span className="text-lg">📄</span>
              <div className="min-w-0">
                <div className="truncate font-medium text-slate-100">{activeFile.name}</div>
                <div className="text-xs text-slate-500">{activeFile.meta}</div>
              </div>
            </div>
            <button
              type="button"
              onClick={() => {
                clearActiveFile();
                showToast("Document detached.");
              }}
              className="shrink-0 rounded-lg border border-white/10 px-2 py-1 text-xs text-slate-400 hover:bg-white/5"
            >
              Remove
            </button>
          </div>
        )}

        {pendingImage && (
          <div className="flex flex-wrap items-start gap-3 rounded-2xl border border-violet-500/20 bg-violet-500/5 p-3">
            <img
              src={pendingImage.previewUrl}
              alt=""
              className="h-14 w-14 rounded-xl border border-white/10 object-cover"
            />
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium text-slate-100">{pendingImage.name}</div>
              <div className="text-xs text-slate-500">{formatBytes(pendingImage.size)} · Ready</div>
            </div>
            <button
              type="button"
              onClick={() => clearPendingImage()}
              className="rounded-lg border border-white/10 px-2 py-1 text-xs text-slate-400 hover:bg-white/5"
            >
              Remove
            </button>
          </div>
        )}

        <div className="flex items-end gap-2 rounded-[1.35rem] border border-white/[0.1] bg-slate-900/90 p-2 shadow-glow backdrop-blur-xl focus-within:border-sky-500/35 focus-within:ring-2 focus-within:ring-sky-500/15">
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept=".pdf,.txt,.png,.jpg,.jpeg,image/png,image/jpeg"
            onChange={(e) => void onFileSelected(e.target.files)}
          />
          <button
            type="button"
            onClick={triggerFilePicker}
            disabled={isSending}
            title="Attach"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-slate-300 transition hover:bg-white/[0.08] hover:text-white disabled:opacity-40"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
            </svg>
          </button>
          <button
            type="button"
            onClick={startListening}
            disabled={isSending}
            title="Voice"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-lg text-slate-300 transition hover:bg-white/[0.08] disabled:opacity-40"
          >
            🎤
          </button>
          <textarea
            ref={taRef}
            rows={1}
            value={composerText}
            onChange={(e) => setComposerText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void sendMessage(composerText);
              }
            }}
            placeholder={placeholder}
            disabled={isSending}
            className="max-h-40 min-h-[44px] flex-1 resize-none bg-transparent py-2.5 text-sm text-slate-100 outline-none placeholder:text-slate-500 disabled:opacity-50"
            aria-label="Message input"
          />
          <button
            type="button"
            disabled={isSending || (!composerText.trim() && !pendingImage)}
            onClick={() => void sendMessage(composerText)}
            title="Send"
            className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-sky-400 to-violet-600 text-slate-950 shadow-glow-sm transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {isSending ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-900/40 border-t-slate-900" />
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            )}
          </button>
        </div>
        <p className="px-1 text-center text-[11px] text-slate-500">{hint}</p>
      </div>
    </div>
  );
}

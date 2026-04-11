import { useCallback, useEffect, useRef, useState } from "react";
import { useJarvis } from "../../context/JarvisContext";
import { AppHeader } from "../layout/AppHeader";
import { Composer } from "./Composer";
import { EmptyState } from "./EmptyState";
import { MessageBubble } from "./MessageBubble";

function TypingDots() {
  return (
    <div className="flex max-w-3xl gap-3">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/[0.06] text-xs font-bold text-slate-400">
        J
      </div>
      <div className="rounded-2xl border border-white/[0.08] bg-slate-900/80 px-4 py-3">
        <div className="flex gap-1">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="h-2 w-2 animate-bounce rounded-full bg-sky-400/80"
              style={{ animationDelay: `${i * 0.15}s` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export function ChatWorkspace() {
  const {
    messages,
    isSending,
    sendMessage,
    setSidebarMobileOpen,
    onFileSelected,
    createNewChat,
  } = useJarvis();

  const scrollRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const dragDepth = useRef(0);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    endRef.current?.scrollIntoView({ behavior, block: "end" });
  }, []);

  useEffect(() => {
    scrollToBottom(messages.length < 3 ? "auto" : "smooth");
  }, [messages, isSending, scrollToBottom]);

  const onDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragDepth.current += 1;
    setDragActive(true);
  };
  const onDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragDepth.current = Math.max(0, dragDepth.current - 1);
    if (dragDepth.current === 0) setDragActive(false);
  };
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragDepth.current = 0;
    setDragActive(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      const dt = new DataTransfer();
      dt.items.add(file);
      void onFileSelected(dt.files);
    }
  };

  const showEmpty = messages.length === 0;
  const last = messages[messages.length - 1];
  const showTyping = isSending && last?.role === "user";

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-white/[0.06] bg-slate-950/30 shadow-inner backdrop-blur-sm lg:rounded-3xl">
      <AppHeader onOpenSidebar={() => setSidebarMobileOpen(true)} />

      <div
        className={`relative flex min-h-0 flex-1 flex-col ${
          dragActive ? "ring-2 ring-inset ring-sky-500/40" : ""
        }`}
        onDragEnter={onDragEnter}
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        {dragActive && (
          <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-sky-500/10 backdrop-blur-[2px]">
            <p className="rounded-xl border border-sky-400/30 bg-slate-950/80 px-6 py-3 text-sm font-medium text-sky-200">
              Drop file to attach
            </p>
          </div>
        )}

        <div
          ref={scrollRef}
          className="scrollbar-thin flex min-h-0 flex-1 flex-col overflow-y-auto px-3 py-4 sm:px-6"
        >
          {showEmpty ? (
            <EmptyState
              onSuggestion={(msg) => {
                void (async () => {
                  const chat = await createNewChat({ clearFile: true });
                  if (chat) await sendMessage(msg, chat.id);
                })();
              }}
            />
          ) : (
            <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 pb-8">
              {messages.map((m, i) => (
                <MessageBubble key={String(m.id)} message={m} stagger={i} />
              ))}
              {showTyping && <TypingDots />}
              <div ref={endRef} className="h-px w-full shrink-0" />
            </div>
          )}
        </div>

        <Composer />
      </div>
    </div>
  );
}

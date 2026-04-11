import hljs from "highlight.js";
import { useEffect, useRef } from "react";
import { useJarvis } from "../../context/JarvisContext";
import type { UiMessage } from "../../context/JarvisContext";
import { formatMessageTime } from "../../lib/format";
import { renderMarkdown } from "../../lib/markdown";

const agentMeta: Record<string, { icon: string; label: string }> = {
  auto: { icon: "✨", label: "Auto" },
  chat: { icon: "💬", label: "Chat" },
  generate_image: { icon: "🖼", label: "Image" },
  analyze_image: { icon: "🔍", label: "Vision" },
};

function enhanceCodeBlocks(root: HTMLElement) {
  root.querySelectorAll("pre > code").forEach((codeEl) => {
    const el = codeEl as HTMLElement;
    if (el.dataset.enhanced === "1") return;
    el.dataset.enhanced = "1";
    const pre = el.parentElement as HTMLElement;
    const wrap = document.createElement("div");
    wrap.className =
      "my-3 overflow-hidden rounded-xl border border-white/10 bg-[#0d1117] shadow-inner";
    const toolbar = document.createElement("div");
    toolbar.className =
      "flex items-center justify-between gap-2 border-b border-white/[0.06] bg-white/[0.03] px-3 py-2";
    const label = document.createElement("span");
    label.className = "text-[10px] font-bold uppercase tracking-wider text-slate-500";
    const langMatch = (el.className || "").match(/language-([\w-]+)/);
    label.textContent = (langMatch?.[1] || "code").replace(/^\w/, (s) => s.toUpperCase());
    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className =
      "rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-[11px] font-medium text-slate-300 hover:bg-white/10";
    copyBtn.textContent = "Copy";
    copyBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(el.textContent || "");
        copyBtn.textContent = "Copied";
        setTimeout(() => {
          copyBtn.textContent = "Copy";
        }, 1400);
      } catch {
        /* noop */
      }
    });
    toolbar.append(label, copyBtn);
    pre.parentNode?.insertBefore(wrap, pre);
    wrap.append(toolbar, pre);
    try {
      hljs.highlightElement(el);
    } catch {
      /* noop */
    }
  });
}

export function MessageBubble({
  message,
  stagger = 0,
}: {
  message: UiMessage;
  stagger?: number;
}) {
  const { showToast, saveNote, lastUserContent, setComposerText } = useJarvis();
  const contentRef = useRef<HTMLDivElement>(null);
  const isUser = message.role === "user";
  const displayContent = message.isStreaming ? message.streamPlain ?? "" : message.content;
  const html = !isUser && !message.isStreaming ? renderMarkdown(message.content) : null;

  useEffect(() => {
    const root = contentRef.current;
    if (!root || isUser || message.isStreaming) return;
    root.innerHTML = html || "";
    enhanceCodeBlocks(root);
  }, [html, isUser, message.isStreaming]);

  function speak() {
    if (!("speechSynthesis" in window)) {
      showToast("Text-to-speech is not supported.", "error");
      return;
    }
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(message.content);
    window.speechSynthesis.speak(u);
  }

  async function copyAll() {
    try {
      await navigator.clipboard.writeText(message.content);
      showToast("Copied to clipboard.", "success");
    } catch {
      showToast("Could not copy.", "error");
    }
  }

  function regenerate() {
    const last = lastUserContent();
    if (last) {
      setComposerText(last);
      showToast("Last prompt loaded into composer.", "success");
    } else {
      showToast("No user message to retry.", "error");
    }
  }

  async function saveAsNote() {
    const title = message.content.slice(0, 48).trim() || "From chat";
    await saveNote(title, message.content, undefined);
  }

  const agent =
    !isUser && message.agent_type
      ? agentMeta[message.agent_type] ?? {
          icon: "✨",
          label: message.agent_type,
        }
      : null;

  return (
    <div
      className={`group flex w-full max-w-3xl animate-fade-in gap-3 ${isUser ? "ml-auto flex-row-reverse" : ""}`}
      style={{ animationDelay: `${stagger * 40}ms` }}
    >
      <div
        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border text-sm ${
          isUser
            ? "border-sky-400/30 bg-gradient-to-br from-sky-400 to-violet-600 text-slate-950"
            : "border-white/10 bg-white/[0.06] text-slate-200"
        }`}
      >
        {isUser ? "You" : "J"}
      </div>
      <div className={`flex min-w-0 max-w-[min(100%,720px)] flex-col gap-1.5 ${isUser ? "items-end" : ""}`}>
        <div
          className={`flex flex-wrap items-center gap-2 text-[11px] text-slate-500 ${isUser ? "justify-end" : ""}`}
        >
          <span className="font-medium text-slate-400">{isUser ? "You" : "Jarvis"}</span>
          {agent && (
            <span className="rounded-full border border-white/10 bg-white/[0.05] px-2 py-0.5 text-[10px] font-semibold text-slate-300">
              {agent.icon} {agent.label}
            </span>
          )}
          <span>{formatMessageTime(message.created_at)}</span>
        </div>

        <div
          className={`relative rounded-2xl border px-4 py-3 text-[15px] leading-relaxed shadow-lg ${
            isUser
              ? "border-sky-500/25 bg-gradient-to-br from-sky-500/25 to-violet-600/20 text-slate-50"
              : "border-white/[0.08] bg-slate-900/80 text-slate-200"
          }`}
        >
          {message.attachment_url && message.message_type === "image_analysis" && (
            <a
              href={message.attachment_url}
              target="_blank"
              rel="noreferrer"
              className="mb-3 block overflow-hidden rounded-xl border border-white/10"
            >
              <img
                src={message.attachment_url}
                alt="Attachment"
                className="max-h-60 w-full object-cover"
              />
            </a>
          )}

          {message.image_url && message.message_type === "image_generation" && (
            <div className="mb-3 overflow-hidden rounded-xl border border-white/10">
              <a href={message.image_url} target="_blank" rel="noreferrer" className="block">
                <img
                  src={message.image_url}
                  alt="Generated"
                  className="max-h-80 w-full object-cover"
                />
              </a>
              <div className="flex gap-2 border-t border-white/10 bg-black/30 px-3 py-2 text-xs">
                <a
                  href={message.image_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sky-400 hover:underline"
                >
                  Open
                </a>
                <a
                  href={message.image_url}
                  download
                  className="text-sky-400 hover:underline"
                >
                  Download
                </a>
              </div>
            </div>
          )}

          {isUser ? (
            <div className="whitespace-pre-wrap break-words">{displayContent}</div>
          ) : message.isStreaming ? (
            <div className="whitespace-pre-wrap break-words">
              {displayContent}
              <span className="ml-0.5 inline-block h-4 w-1 animate-pulse rounded-sm bg-sky-400 align-middle" />
            </div>
          ) : (
            <div
              ref={contentRef}
              className="markdown-body prose-invert max-w-none [&_a]:text-sky-400 [&_code]:text-amber-200/90"
            />
          )}
        </div>

        {!isUser && !message.isStreaming && (
          <div className="flex flex-wrap gap-1 opacity-0 transition group-hover:opacity-100 sm:opacity-100">
            <button
              type="button"
              onClick={speak}
              className="rounded-lg px-2 py-1 text-[11px] font-medium text-slate-500 hover:bg-white/5 hover:text-slate-300"
            >
              Speak
            </button>
            <button
              type="button"
              onClick={() => void copyAll()}
              className="rounded-lg px-2 py-1 text-[11px] font-medium text-slate-500 hover:bg-white/5 hover:text-slate-300"
            >
              Copy
            </button>
            <button
              type="button"
              onClick={regenerate}
              className="rounded-lg px-2 py-1 text-[11px] font-medium text-slate-500 hover:bg-white/5 hover:text-slate-300"
            >
              Retry
            </button>
            <button
              type="button"
              onClick={() => void saveAsNote()}
              className="rounded-lg px-2 py-1 text-[11px] font-medium text-slate-500 hover:bg-white/5 hover:text-slate-300"
            >
              Save note
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

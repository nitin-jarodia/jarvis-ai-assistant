import DOMPurify from "dompurify";
import { marked } from "marked";
import { escapeHtml } from "./format";

marked.setOptions({ gfm: true, breaks: true });

export function renderMarkdown(content: string): string {
  try {
    const raw = marked.parse(content, { async: false }) as string;
    return DOMPurify.sanitize(raw, { USE_PROFILES: { html: true } });
  } catch {
    return escapeHtml(content).replace(/\n/g, "<br>");
  }
}

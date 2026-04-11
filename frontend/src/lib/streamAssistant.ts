/** Client-side “typing” reveal for assistant text (matches legacy UX). */
export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
}

export async function streamAssistantText(
  fullText: string,
  onUpdate: (partial: string) => void,
  shouldAbort: () => boolean
): Promise<void> {
  if (prefersReducedMotion() || fullText.split(/\s+/).filter(Boolean).length <= 3) {
    onUpdate(fullText);
    return;
  }

  const parts = fullText.split(/(\s+)/).filter(Boolean);
  let index = 0;
  let rendered = "";

  await new Promise<void>((resolve) => {
    const tick = () => {
      if (shouldAbort()) {
        resolve();
        return;
      }

      const nextChunk: string[] = [];
      let chunkCount = 0;
      while (index < parts.length && chunkCount < 3) {
        nextChunk.push(parts[index]);
        if (!/^\s+$/.test(parts[index])) chunkCount += 1;
        index += 1;
      }

      rendered += nextChunk.join("");
      onUpdate(rendered);

      if (index >= parts.length) {
        resolve();
        return;
      }

      setTimeout(tick, 18 + Math.min(44, nextChunk.join("").length * 2));
    };

    tick();
  });

  if (!shouldAbort()) onUpdate(fullText);
}

const PINNED_KEY = "jarvis_pinned_chat_ids";
const ARCHIVED_KEY = "jarvis_archived_chat_ids";

function readIds(key: string): Set<number> {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return new Set();
    const arr = JSON.parse(raw) as number[];
    return new Set(Array.isArray(arr) ? arr : []);
  } catch {
    return new Set();
  }
}

function writeIds(key: string, set: Set<number>) {
  localStorage.setItem(key, JSON.stringify([...set]));
}

export function getPinnedChatIds(): Set<number> {
  return readIds(PINNED_KEY);
}

export function togglePinnedChatId(id: number): Set<number> {
  const s = getPinnedChatIds();
  if (s.has(id)) s.delete(id);
  else s.add(id);
  writeIds(PINNED_KEY, s);
  return s;
}

export function getArchivedChatIds(): Set<number> {
  return readIds(ARCHIVED_KEY);
}

export function toggleArchivedChatId(id: number): Set<number> {
  const s = getArchivedChatIds();
  if (s.has(id)) s.delete(id);
  else s.add(id);
  writeIds(ARCHIVED_KEY, s);
  return s;
}

import { useState } from "react";
import { useJarvis } from "../../context/JarvisContext";
import { formatDate } from "../../lib/format";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Input } from "../ui/Input";
import { Skeleton } from "../ui/Skeleton";
import { AppHeader } from "../layout/AppHeader";

export function NotesView() {
  const {
    notes,
    notesLoading,
    saveNote,
    deleteNote,
    showToast,
    setSidebarMobileOpen,
  } = useJarvis();

  const [editingId, setEditingId] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [editorOpen, setEditorOpen] = useState(false);

  function openNew() {
    setEditingId(null);
    setTitle("");
    setBody("");
    setEditorOpen(true);
  }

  function openEdit(id: number) {
    const n = notes.find((x) => x.id === id);
    if (!n) return;
    setEditingId(id);
    setTitle(n.title);
    setBody(n.content);
    setEditorOpen(true);
  }

  async function onSave() {
    const t = title.trim();
    const c = body.trim();
    if (!t) {
      showToast("Please enter a title.", "error");
      return;
    }
    if (!c) {
      showToast("Please enter content.", "error");
      return;
    }
    await saveNote(t, c, editingId ?? undefined);
    setEditorOpen(false);
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-white/[0.06] bg-slate-950/30 lg:rounded-3xl">
      <AppHeader onOpenSidebar={() => setSidebarMobileOpen(true)} />
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden p-4 sm:p-6">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-display text-2xl font-semibold text-white">Notes</h2>
            <p className="text-sm text-slate-500">Capture ideas alongside your chats</p>
          </div>
          <Button onClick={openNew} className="shrink-0">
            + New note
          </Button>
        </div>

        {editorOpen && (
          <Card className="mb-6 space-y-3 p-5">
            <Input
              placeholder="Title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="font-display font-semibold"
            />
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Write something…"
              rows={6}
              className="w-full resize-y rounded-xl border border-white/10 bg-black/30 p-3 text-sm text-slate-100 outline-none focus:border-sky-500/40 focus:ring-2 focus:ring-sky-500/15"
            />
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void onSave()}>Save</Button>
              <Button variant="ghost" onClick={() => setEditorOpen(false)}>
                Cancel
              </Button>
            </div>
          </Card>
        )}

        <div className="scrollbar-thin grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-y-auto sm:grid-cols-2 xl:grid-cols-3">
          {notesLoading &&
            Array.from({ length: 6 }).map((_, i) => (
              <Card key={i} className="h-36 p-4">
                <Skeleton className="mb-2 h-4 w-3/4" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="mt-2 h-3 w-1/2" />
              </Card>
            ))}

          {!notesLoading && notes.length === 0 && !editorOpen && (
            <div className="col-span-full flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 py-20 text-center">
              <span className="mb-3 text-4xl opacity-40">📝</span>
              <p className="text-slate-400">No notes yet. Create your first one.</p>
              <Button onClick={openNew} className="mt-4">
                Create note
              </Button>
            </div>
          )}

          {!notesLoading &&
            notes.map((n) => (
              <Card key={n.id} className="group flex flex-col p-4 transition hover:border-sky-500/20">
                <h3 className="font-display text-lg font-semibold text-white">{n.title}</h3>
                <p className="mt-2 line-clamp-4 text-sm text-slate-400">{n.content}</p>
                <div className="mt-auto flex items-center justify-between gap-2 pt-4 text-xs text-slate-500">
                  <span>{formatDate(n.created_at)}</span>
                  <div className="flex gap-1 opacity-0 transition group-hover:opacity-100">
                    <button
                      type="button"
                      onClick={() => openEdit(n.id)}
                      className="rounded-lg px-2 py-1 text-sky-400 hover:bg-white/5"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => void deleteNote(n.id)}
                      className="rounded-lg px-2 py-1 text-rose-400 hover:bg-white/5"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </Card>
            ))}
        </div>
      </div>
    </div>
  );
}

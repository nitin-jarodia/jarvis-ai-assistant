import { AuthCard } from "./auth/AuthCard";
import { ChatWorkspace } from "./chat/ChatWorkspace";
import { ToastStack } from "./ToastStack";
import { HistoryView } from "./history/HistoryView";
import { Sidebar } from "./layout/Sidebar";
import { NotesView } from "./notes/NotesView";
import { useJarvis } from "../context/JarvisContext";

export function AppShell() {
  const { isAuthenticated, tab, isMobile, sidebarMobileOpen, setSidebarMobileOpen } = useJarvis();

  if (!isAuthenticated) {
    return (
      <>
        <div
          className="pointer-events-none fixed inset-0 opacity-[0.35]"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.05'/%3E%3C/svg%3E")`,
          }}
        />
        <AuthCard />
        <ToastStack />
      </>
    );
  }

  return (
    <div className="flex h-full min-h-0 gap-0 p-2 sm:p-3 lg:gap-3 lg:p-4">
      {isMobile && sidebarMobileOpen && (
        <button
          type="button"
          className="fixed inset-0 z-20 bg-slate-950/70 backdrop-blur-sm transition-opacity"
          aria-label="Close sidebar"
          onClick={() => setSidebarMobileOpen(false)}
        />
      )}

      {(!isMobile || sidebarMobileOpen) && <Sidebar />}

      <main className="relative z-10 flex min-h-0 min-w-0 flex-1 flex-col">
        {tab === "chat" && <ChatWorkspace />}
        {tab === "notes" && <NotesView />}
        {tab === "history" && <HistoryView />}
      </main>

      <ToastStack />
    </div>
  );
}

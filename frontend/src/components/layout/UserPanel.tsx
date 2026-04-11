import { useJarvis } from "../../context/JarvisContext";
import { Button } from "../ui/Button";

export function UserPanel({ narrow }: { narrow: boolean }) {
  const { userId, logout } = useJarvis();

  return (
    <div className={`mt-auto border-t border-white/[0.06] p-3 ${narrow ? "px-2" : ""}`}>
      <div
        className={`rounded-xl border border-white/[0.06] bg-black/20 p-3 ${narrow ? "flex flex-col items-center gap-2" : ""}`}
      >
        {!narrow && (
          <>
            <div className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
              Signed in
            </div>
            <div className="truncate text-sm font-semibold text-slate-100">User #{userId}</div>
          </>
        )}
        <Button
          variant="ghost"
          onClick={logout}
          className={`w-full py-2 text-xs ${narrow ? "!px-2" : ""}`}
          title="Log out"
        >
          {narrow ? "⎋" : "Log out"}
        </Button>
      </div>
    </div>
  );
}

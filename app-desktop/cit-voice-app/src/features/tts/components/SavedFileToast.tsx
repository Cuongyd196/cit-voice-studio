import { CheckCircle2, FileAudio, FolderOpen, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { desktopApi, onSaved, type SavedFile } from "../desktop-files";

const VISIBLE_MS = 8000;

/** Thông báo "Đã lưu" sau mỗi lần lưu trong app desktop, có nút mở file và mở
 *  thư mục. Gắn một lần ở TtsStudio; mọi nút lưu đi qua downloadBlobAsFile /
 *  downloadHistoryAudio nên không phải sửa từng nơi. */
export function SavedFileToast() {
  const [file, setFile] = useState<SavedFile | null>(null);
  const [error, setError] = useState("");
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(
    () =>
      onSaved((saved) => {
        setFile(saved);
        setError("");
        clearTimeout(timer.current);
        timer.current = setTimeout(() => setFile(null), VISIBLE_MS);
      }),
    []
  );
  useEffect(() => () => clearTimeout(timer.current), []);

  if (!file) {
    return null;
  }

  const open = async (reveal: boolean) => {
    const api = await desktopApi();
    const res = await api?.open_saved(file.path, reveal);
    if (res?.success) {
      setFile(null);
    } else {
      setError(res?.error || "Không mở được.");
    }
  };

  return (
    <div
      aria-live="polite"
      className="fade-in-50 slide-in-from-bottom-2 fixed right-4 bottom-28 z-50 w-[360px] max-w-[calc(100vw-2rem)] animate-in rounded-xl border border-brand-500/40 bg-card p-3 text-sm shadow-lg"
      role="status"
    >
      <div className="flex items-start gap-2">
        <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-brand-500" />
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-foreground">
            {file.opened ? "Đã lưu và mở file" : "Đã lưu file"}
          </p>
          <p
            className="truncate text-muted-foreground text-xs"
            title={file.path}
          >
            {file.path}
          </p>
        </div>
        <button
          aria-label="Đóng"
          className="rounded p-0.5 text-muted-foreground hover:text-foreground"
          onClick={() => setFile(null)}
          type="button"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="mt-2 flex gap-2">
        {!file.opened && (
          <button
            className="studio-primary flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 font-medium text-xs"
            onClick={() => open(false)}
            type="button"
          >
            <FileAudio className="h-3.5 w-3.5" />
            Mở file
          </button>
        )}
        <button
          className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-border px-3 py-1.5 font-medium text-foreground text-xs hover:bg-secondary"
          onClick={() => open(true)}
          type="button"
        >
          <FolderOpen className="h-3.5 w-3.5" />
          Mở thư mục
        </button>
      </div>
      {error && (
        <p
          className="mt-2 text-rose-600 text-xs dark:text-rose-400"
          role="alert"
        >
          {error}
        </p>
      )}
    </div>
  );
}

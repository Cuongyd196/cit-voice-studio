// Lưu file trong app desktop (PyWebView, apps/desktop_app.py DesktopApi): thư mục
// lưu, hỏi Save As hay lưu thẳng, tự mở file, và thông báo "Đã lưu" có nút mở.
// Trình duyệt thường không có các API này - giao diện ẩn phần cài đặt tương ứng.

export interface SaveSettings {
  ask: boolean;
  default_folder: string;
  effective_folder: string;
  folder: string | null;
  open_after: boolean;
}

export interface SavedFile {
  name: string;
  opened: boolean;
  path: string;
}

interface DesktopApi {
  choose_save_folder: () => Promise<{
    cancelled?: boolean;
    error?: string;
    folder?: string;
    success: boolean;
  }>;
  get_save_settings: () => Promise<SaveSettings>;
  open_saved: (
    path: string,
    reveal: boolean
  ) => Promise<{ error?: string; success: boolean }>;
  set_save_settings: (
    settings: Partial<Pick<SaveSettings, "ask" | "folder" | "open_after">>
  ) => Promise<SaveSettings & { error?: string; success: boolean }>;
}

const SAVED_EVENT = "cit:file-saved";

function currentApi(): DesktopApi | null {
  // biome-ignore lint/suspicious/noExplicitAny: cầu nối PyWebView không có kiểu
  const api = (window as any).pywebview?.api;
  return typeof api?.get_save_settings === "function" ? api : null;
}

/** API desktop, chờ PyWebView gắn xong (sự kiện pywebviewready) tối đa ~3 giây;
 *  null khi chạy trong trình duyệt thường. */
export function desktopApi(): Promise<DesktopApi | null> {
  const ready = currentApi();
  if (ready || typeof window === "undefined") {
    return Promise.resolve(ready);
  }
  return new Promise((resolve) => {
    const done = () => {
      window.removeEventListener("pywebviewready", done);
      clearTimeout(timer);
      resolve(currentApi());
    };
    const timer = setTimeout(done, 3000);
    window.addEventListener("pywebviewready", done);
  });
}

/** Gọi sau khi DesktopApi lưu xong: hiện thông báo "Đã lưu" (SavedFileToast). */
export function notifySaved(result: unknown): void {
  const r = result as Partial<SavedFile> | null;
  if (!r?.path) {
    return;
  }
  window.dispatchEvent(
    new CustomEvent<SavedFile>(SAVED_EVENT, {
      detail: {
        name: r.name || r.path,
        opened: Boolean(r.opened),
        path: r.path,
      },
    })
  );
}

export function onSaved(listener: (file: SavedFile) => void): () => void {
  const handler = (event: Event) =>
    listener((event as CustomEvent<SavedFile>).detail);
  window.addEventListener(SAVED_EVENT, handler);
  return () => window.removeEventListener(SAVED_EVENT, handler);
}

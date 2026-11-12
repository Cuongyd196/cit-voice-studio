import { FileText } from "lucide-react";
import type React from "react";
import { useEffect, useState } from "react";
import { acceptTerms, fetchTerms, type TermsInfo } from "../api";
import { TermsMarkdown } from "./TermsMarkdown";

// Màn hình chặn toàn app cho tới khi người dùng đồng ý điều khoản (lần đầu mở app,
// hoặc khi điều khoản đổi phiên bản). Máy chủ chưa trả lời thì không chặn - màn hình
// chờ kết nối của app đã lo phần đó.
export const TermsGate: React.FC<{ apiUrl: string }> = ({ apiUrl }) => {
  const [info, setInfo] = useState<TermsInfo | null>(null);
  const [checked, setChecked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [quitHint, setQuitHint] = useState(false);

  useEffect(() => {
    fetchTerms(apiUrl)
      .then(setInfo)
      .catch(() => setInfo(null));
  }, [apiUrl]);

  if (!info || info.accepted) {
    return null;
  }

  const handleAccept = async () => {
    try {
      await acceptTerms(apiUrl);
      setInfo({ ...info, accepted: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleQuit = () => {
    // biome-ignore lint/suspicious/noExplicitAny: API do pywebview gắn vào window
    const api = (window as any).pywebview?.api;
    if (api && typeof api.quit_app === "function") {
      api.quit_app();
    } else {
      setQuitHint(true);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-background/95 p-4">
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-2xl border border-border bg-card shadow-md">
        <div className="flex items-center gap-2 border-border/60 border-b px-5 py-4">
          <FileText className="h-5 w-5 text-brand-500" />
          <h2 className="font-bold text-base text-foreground">
            Điều khoản sử dụng
          </h2>
        </div>
        <div className="flex-1 select-text overflow-y-auto px-5 py-4">
          <TermsMarkdown text={info.text} />
        </div>
        <div className="space-y-3 border-border/60 border-t px-5 py-4">
          <label className="flex cursor-pointer items-start gap-2 text-sm">
            <input
              checked={checked}
              className="mt-0.5 rounded border-border text-brand-500"
              onChange={(e) => setChecked(e.target.checked)}
              type="checkbox"
            />
            <span>
              Tôi đã đọc, hiểu và đồng ý với toàn bộ điều khoản sử dụng.
            </span>
          </label>
          {error && (
            <p className="text-rose-600 text-xs" role="alert">
              {error}
            </p>
          )}
          {quitHint && (
            <p className="text-muted-foreground text-xs">
              Bạn có thể đóng cửa sổ/tab này để thoát.
            </p>
          )}
          <div className="flex justify-end gap-2">
            <button
              className="rounded-lg border border-border px-4 py-2 font-medium text-foreground text-sm hover:bg-secondary"
              onClick={handleQuit}
              type="button"
            >
              Thoát
            </button>
            <button
              className="studio-primary rounded-lg bg-brand-600 px-4 py-2 font-semibold text-sm text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!checked}
              onClick={handleAccept}
              type="button"
            >
              Tôi đồng ý
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

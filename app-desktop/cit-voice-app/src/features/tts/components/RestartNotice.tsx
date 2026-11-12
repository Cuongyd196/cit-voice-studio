import { AlertTriangle, CheckCircle2, RotateCw } from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useState } from "react";
import { fetchRestartSupport, restartApp } from "../api";

/** App co tu khoi dong lai duoc khong (chi ban desktop; chay run_stream thi khong). */
export function useAppRestart(apiUrl: string) {
  const [supported, setSupported] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    fetchRestartSupport(apiUrl)
      .then((ok) => {
        if (alive) {
          setSupported(ok);
        }
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [apiUrl]);

  const restart = useCallback(async () => {
    setError("");
    setRestarting(true);
    try {
      await restartApp(apiUrl);
      // Thanh cong: tien trinh nay tu thoat, cua so dong va ban moi mo len.
    } catch (e) {
      setRestarting(false);
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [apiUrl]);

  return { error, restart, restarting, supported };
}

interface RestartNoticeProps {
  apiUrl: string;
  /** Vi du "Đã lưu cổng 8002." - phan "can khoi dong lai" do component tu them. */
  message: string;
}

/** Thong bao "da luu, can khoi dong lai" kem nut khoi dong lai ngay. */
export const RestartNotice: React.FC<RestartNoticeProps> = ({
  apiUrl,
  message,
}) => {
  const { error, restart, restarting, supported } = useAppRestart(apiUrl);

  return (
    <div
      aria-live="polite"
      className="space-y-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-2.5 py-2 text-[12px] text-amber-800 dark:text-amber-200"
      role="status"
    >
      <div className="flex items-start gap-2">
        {restarting ? (
          <RotateCw className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin" />
        ) : (
          <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-600 dark:text-brand-400" />
        )}
        <span>
          {restarting ? (
            "Đang khởi động lại… cửa sổ sẽ đóng rồi tự mở lại sau vài giây."
          ) : (
            <>
              <strong>{message}</strong> Cần khởi động lại ứng dụng để áp dụng
              {supported ? "." : " - hãy tắt rồi mở lại ứng dụng."}
            </>
          )}
        </span>
      </div>
      {supported && !restarting && (
        <button
          className="flex items-center gap-1.5 rounded-lg bg-amber-600 px-3 py-1.5 font-semibold text-white shadow-sm hover:bg-amber-700"
          onClick={restart}
          type="button"
        >
          <RotateCw className="h-3.5 w-3.5" /> Khởi động lại ngay
        </button>
      )}
      {error && (
        <p className="flex items-start gap-1.5 text-rose-600 dark:text-rose-400">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          {error}
        </p>
      )}
    </div>
  );
};

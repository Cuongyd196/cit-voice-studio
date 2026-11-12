import { AudioLines, CheckCircle2, Download, RefreshCw, X } from "lucide-react";
import type React from "react";
import { useEffect, useId, useRef, useState } from "react";
import {
  type AppUpdateInfo,
  checkAppUpdate,
  saveUpdateCheck,
  skipAppUpdate,
} from "../api";

// Kiem tra ban moi: chi BAO va dan toi trang tai, khong tu tai/tu cai (bo cai ~365 MB,
// chua ky so nen SmartScreen van hoi; cai hong giua chung thi nguoi dung mat app).

const errorText = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** Thanh bao "Da co ban moi" duoi thanh tab. Chi hien khi co ban moi hon. */
export const UpdateBanner: React.FC<{
  info: AppUpdateInfo | null;
  onDismiss: () => void;
}> = ({ info, onDismiss }) => {
  if (!info?.newer) {
    return null;
  }
  return (
    <div className="slide-in-from-top-2 mx-6 mt-3 flex animate-in items-center justify-between gap-3 rounded-xl border border-brand-500/30 bg-brand-500/10 p-3 text-brand-700 text-xs shadow-sm dark:text-brand-300">
      <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
        <Download className="h-4 w-4 shrink-0" />
        <span>
          Đã có <strong>bản {info.latest}</strong> (bạn đang dùng bản{" "}
          {info.current}).
        </span>
        <a
          className="font-bold underline underline-offset-2 hover:text-brand-500"
          href={info.url}
          rel="noreferrer"
          target="_blank"
        >
          Xem thay đổi &amp; tải về
        </a>
      </div>
      <button
        className="shrink-0 rounded-lg p-1 transition-colors hover:bg-brand-500/20"
        onClick={onDismiss}
        title="Để sau"
        type="button"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
};

/** Hộp thoại "Có bản mới" giữa màn hình, hiện một lần cho mỗi bản. "Để sau" ghi
 *  nhớ bản đó ở máy chủ nên lần mở sau không bật lại (thanh báo nhỏ vẫn còn);
 *  nút X chỉ đóng trong phiên này. Chỉ mở trang tải, không tự tải/tự cài. */
export const UpdateDialog: React.FC<{
  apiUrl: string;
  info: AppUpdateInfo;
  onClose: () => void;
}> = ({ apiUrl, info, onClose }) => {
  const titleId = useId();
  const primaryRef = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    primaryRef.current?.focus();
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const handleLater = () => {
    if (info.latest) {
      skipAppUpdate(apiUrl, info.latest).catch(() => undefined);
    }
    onClose();
  };

  return (
    <div
      aria-labelledby={titleId}
      aria-modal="true"
      className="update-dialog-overlay fixed inset-0 z-[70]"
      role="dialog"
    >
      <div className="update-dialog fade-in-50 zoom-in-95 animate-in">
        <div className="flex items-start gap-3">
          <span className="update-dialog-logo">
            <AudioLines size={26} />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-bold text-base text-foreground" id={titleId}>
                CIT Voice Studio
              </h2>
              <span className="update-dialog-badge">Cập nhật</span>
            </div>
            <p className="mt-0.5 font-mono text-muted-foreground text-xs">
              {info.current} → {info.latest}
            </p>
          </div>
          <button
            aria-label="Đóng"
            className="rounded-lg p-1 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
            onClick={onClose}
            type="button"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <p className="mt-4 text-foreground/80 text-sm">
          Đã có bản <strong>{info.latest}</strong> với tính năng mới và sửa lỗi.
          Cài đè lên bản cũ, giọng đã nhân bản, các bản đã tạo và cài đặt được
          giữ nguyên.
        </p>
        {info.highlights && info.highlights.length > 0 && (
          <ul className="update-dialog-list">
            {info.highlights.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        )}

        <div className="update-dialog-footer">
          <a
            className="font-medium text-foreground text-sm underline underline-offset-4 hover:text-brand-600"
            href={info.url}
            rel="noreferrer"
            target="_blank"
          >
            Có gì mới
          </a>
          <div className="flex gap-2">
            <button
              className="rounded-lg border border-border px-4 py-2 font-semibold text-foreground text-xs transition-colors hover:bg-secondary"
              onClick={handleLater}
              type="button"
            >
              Để sau
            </button>
            <a
              className="studio-primary inline-flex items-center gap-1.5 rounded-lg px-4 py-2 font-semibold text-xs"
              href={info.url}
              onClick={onClose}
              ref={primaryRef}
              rel="noreferrer"
              target="_blank"
            >
              <Download className="h-3.5 w-3.5" />
              Tải bản mới
            </a>
          </div>
        </div>
      </div>
    </div>
  );
};

/** Nut "Kiem tra cap nhat" trong tab Thong tin (hoi GitHub ngay, ke ca khi da tat tu kiem tra). */
export const UpdateCheckButton: React.FC<{
  apiUrl: string;
  info: AppUpdateInfo | null;
  onChecked: (info: AppUpdateInfo) => void;
  variant?: "default" | "sidebar";
}> = ({ apiUrl, info, onChecked, variant = "default" }) => {
  const [busy, setBusy] = useState(false);
  const [checked, setChecked] = useState(false);
  const [error, setError] = useState("");

  const handleCheck = async () => {
    setBusy(true);
    setError("");
    try {
      const result = await checkAppUpdate(apiUrl, true);
      onChecked(result);
      setChecked(true);
      if (result.error) {
        setError(result.error);
      }
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className={
        variant === "sidebar"
          ? "studio-update-check"
          : "flex flex-wrap items-center gap-2 text-xs"
      }
    >
      <button
        className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-secondary/60 px-2.5 py-1 font-semibold text-foreground transition-colors hover:bg-secondary disabled:opacity-50"
        disabled={busy}
        onClick={handleCheck}
        type="button"
      >
        <RefreshCw className={`h-3.5 w-3.5 ${busy ? "animate-spin" : ""}`} />
        {busy ? "Đang kiểm tra..." : "Kiểm tra cập nhật"}
      </button>
      {error && (
        <span className="text-rose-600 dark:text-rose-400" role="alert">
          {error}
        </span>
      )}
      {info?.newer && (
        <a
          className="font-bold text-brand-600 underline underline-offset-2 dark:text-brand-400"
          href={info.url}
          rel="noreferrer"
          target="_blank"
        >
          Tải bản {info.latest}
        </a>
      )}
      {!(error || info?.error) &&
        (checked || info?.checked_at) &&
        !info?.newer && (
          <span className="inline-flex items-center gap-1 text-brand-600 dark:text-brand-400">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Bạn đang dùng bản mới nhất.
          </span>
        )}
    </div>
  );
};

/** Phiên bản từ backend, dùng chung trạng thái cập nhật với Thông tin và Cài đặt. */
export const SidebarFooter: React.FC<{
  apiUrl: string;
  info: AppUpdateInfo | null;
  onChecked: (info: AppUpdateInfo) => void;
}> = ({ apiUrl, info, onChecked }) => (
  <footer className="studio-sidebar-footer">
    <div className="studio-sidebar-credit">
      <span>
        by{" "}
        <a
          className="rounded-sm font-bold underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-current focus-visible:outline-offset-2"
          href="https://me.cuongit.net"
          rel="noopener noreferrer"
          target="_blank"
          title="Trang cá nhân Cường IT (mở tab mới)"
        >
          Cường IT
        </a>
      </span>
      <span className="studio-sidebar-version" title="Phiên bản hiện tại">
        {info ? `v${info.current}` : "Đang kết nối…"}
      </span>
    </div>
    <UpdateCheckButton
      apiUrl={apiUrl}
      info={info}
      onChecked={onChecked}
      variant="sidebar"
    />
  </footer>
);

/** Cong tac trong Cai dat: tu kiem tra ban moi khi mo app (lan duy nhat app tu ket noi Internet). */
export const UpdateCheckToggle: React.FC<{
  apiUrl: string;
  isOpen: boolean;
  /** Vua bat: kiem tra ngay de thanh bao ban moi hien luon, khong doi lan mo app sau. */
  onChecked?: (info: AppUpdateInfo) => void;
}> = ({ apiUrl, isOpen, onChecked }) => {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const controller = new AbortController();
    // Khong force: dung ket qua da luu, khong hoi GitHub them lan nao.
    checkAppUpdate(apiUrl, false, controller.signal)
      .then((info) => setEnabled(info.enabled))
      .catch(() => {
        if (!controller.signal.aborted) {
          setEnabled(null);
        }
      });
    return () => controller.abort();
  }, [apiUrl, isOpen]);

  const handleChange = async (value: boolean) => {
    setError("");
    try {
      const saved = await saveUpdateCheck(apiUrl, value);
      setEnabled(saved);
      if (saved) {
        checkAppUpdate(apiUrl)
          .then((info) => onChecked?.(info))
          .catch(() => undefined);
      }
    } catch (e) {
      setError(errorText(e));
    }
  };

  return (
    <div className="settings-card space-y-2">
      <label className="settings-toggle">
        <span aria-hidden="true" className="settings-toggle-icon">
          <RefreshCw size={18} />
        </span>
        <span className="settings-toggle-text">
          <strong>Tự kiểm tra bản mới khi mở app</strong>
          <span>
            Mỗi ngày hỏi GitHub một lần, không gửi văn bản, audio hay thông tin
            máy. Tắt thì app hoàn toàn offline; vẫn kiểm tra tay được ở tab
            Thông tin.
          </span>
        </span>
        <input
          checked={enabled === true}
          className="studio-switch"
          disabled={enabled === null}
          onChange={(e) => handleChange(e.target.checked)}
          type="checkbox"
        />
      </label>
      {error && (
        <p className="text-rose-600 dark:text-rose-400" role="alert">
          {error}
        </p>
      )}
    </div>
  );
};

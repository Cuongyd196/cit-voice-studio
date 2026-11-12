import { AlertTriangle, FolderOpen, HardDrive } from "lucide-react";
import type React from "react";
import { useEffect, useState } from "react";
import { fetchHistoryInfo, type HistoryInfo, openHistoryFolder } from "../api";

// Lich su KHONG tu xoa (truoc day vuot 300 bai / 1 GB thi lang le xoa bai cu nhat).
// Dong nay cho nguoi dung biet lich su chiem bao nhieu, nam o dau, va nhac don khi
// qua lon hoac o dia sap day.

const formatBytes = (bytes: number) => {
  if (bytes >= 1024 ** 3) {
    return `${(bytes / 1024 ** 3).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} GB`;
  }
  return `${Math.max(0, Math.round(bytes / 1024 ** 2)).toLocaleString("vi-VN")} MB`;
};

export const HistoryStorageNote: React.FC<{
  apiUrl: string;
  /** Doi gia tri (vd so muc lich su) thi doc lai dung luong. */
  refreshKey: number;
}> = ({ apiUrl, refreshKey }) => {
  const [info, setInfo] = useState<HistoryInfo | null>(null);
  const [error, setError] = useState("");

  // biome-ignore lint/correctness/useExhaustiveDependencies: refreshKey chi de doc lai khi lich su doi
  useEffect(() => {
    const controller = new AbortController();
    fetchHistoryInfo(apiUrl, controller.signal)
      .then(setInfo)
      .catch(() => undefined); // backend cu / mat ket noi: an dong ghi chu
    return () => controller.abort();
  }, [apiUrl, refreshKey]);

  if (!info) {
    return null;
  }

  const handleOpen = () => {
    setError("");
    openHistoryFolder(apiUrl).catch((e) =>
      setError(e instanceof Error ? e.message : String(e))
    );
  };

  let reason = "";
  if (info.disk_free !== null && info.disk_free < 2 * 1024 ** 3) {
    reason = "Ổ đĩa sắp đầy. ";
  } else if (info.warn) {
    reason = "Các bản đã tạo đang chiếm nhiều dung lượng. ";
  }

  return (
    <div
      className={`space-y-1 rounded-xl border px-3 py-2 text-xs ${
        info.warn
          ? "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300"
          : "border-border/70 bg-card/60 text-muted-foreground"
      }`}
    >
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {info.warn ? (
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
        ) : (
          <HardDrive className="h-3.5 w-3.5 shrink-0" />
        )}
        <span>
          <strong className="text-foreground">{info.count} bài</strong> ·{" "}
          {formatBytes(info.bytes)}
          {info.disk_free !== null &&
            ` · ổ đĩa còn trống ${formatBytes(info.disk_free)}`}
        </span>
        <button
          className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-semibold text-sky-600 transition-colors hover:bg-sky-500/10 dark:text-sky-400"
          onClick={handleOpen}
          title={info.folder}
          type="button"
        >
          <FolderOpen className="h-3.5 w-3.5" />
          Mở thư mục
        </button>
      </div>
      <p className="leading-relaxed">
        {reason}
        Bản đã tạo không tự xoá - hãy tải về bài cần giữ và xoá bớt để giải
        phóng ổ đĩa.
      </p>
      {error && (
        <p className="text-rose-600 dark:text-rose-400" role="alert">
          {error}
        </p>
      )}
    </div>
  );
};

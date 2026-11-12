import { useEffect, useId, useState } from "react";
import { fetchGpuMemory, type GpuMemoryInfo, saveGpuMemory } from "../api";

/** Đọc lại sau khi đổi mô hình: nơi dùng đổi `key` để component mount lại. */
interface GpuMemoryPanelProps {
  apiUrl: string;
  enabled: boolean;
}

const LEVELS_GB = [2, 3, 4, 6, 8, 12, 16, 24];

const gb = (value: number | null | undefined) =>
  value === null || value === undefined
    ? "?"
    : value.toLocaleString("vi-VN", { maximumFractionDigits: 1 });

/** Giới hạn VRAM cho mô hình GPU. Card 4 GB từng treo máy khi đọc bài dài vì app
 *  giữ mãi các CUDA graph; mức "Tự động" đã đủ cho đa số máy, ô chọn để người
 *  dùng hạ thấp hơn khi máy còn chạy app nặng khác (game, trình duyệt...). */
export function GpuMemoryPanel({ apiUrl, enabled }: GpuMemoryPanelProps) {
  const selectId = useId();
  const [info, setInfo] = useState<GpuMemoryInfo | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!enabled) {
      return;
    }
    const controller = new AbortController();
    setMessage("");
    fetchGpuMemory(apiUrl, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setInfo(result);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setInfo(null);
        }
      });
    return () => controller.abort();
  }, [apiUrl, enabled]);

  if (!info?.available) {
    return null;
  }

  const total = info.total_gb ?? 0;
  const levels = LEVELS_GB.filter((level) => level < total);
  if (info.limit_gb !== null && !levels.includes(info.limit_gb)) {
    levels.push(info.limit_gb);
    levels.sort((a, b) => a - b);
  }

  const handleChange = async (value: string) => {
    const limit = value === "auto" ? null : Number(value);
    setSaving(true);
    setMessage("Đang áp dụng...");
    try {
      setInfo(await saveGpuMemory(apiUrl, limit));
      setMessage("✓ Đã áp dụng ngay, không cần khởi động lại.");
    } catch (error) {
      setMessage(
        error instanceof Error && error.message
          ? error.message
          : "Không lưu được giới hạn VRAM. Thử lại sau."
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="settings-card mt-3 space-y-3">
      <label className="settings-card-title" htmlFor={selectId}>
        Giới hạn VRAM (GPU)
      </label>
      <p className="settings-help">
        {info.gpu_name} · {gb(total)} GB. Đang dùng {gb(info.used_gb)} GB, trần{" "}
        {gb(info.effective_limit_gb)} GB. Nếu máy chậm hẳn hoặc đứng khi đọc bài
        dài, hãy chọn mức thấp hơn - app vẫn đọc được, chỉ chậm hơn một chút.
      </p>
      <select
        className="w-full rounded-xl border border-border bg-secondary/50 px-3 py-2"
        disabled={saving}
        id={selectId}
        onChange={(event) => handleChange(event.target.value)}
        value={info.limit_gb === null ? "auto" : String(info.limit_gb)}
      >
        <option value="auto">Tự động (khuyên dùng)</option>
        {levels.map((level) => (
          <option key={level} value={String(level)}>
            Tối đa {level} GB
          </option>
        ))}
      </select>
      {message && (
        <p aria-live="polite" className="settings-help" role="status">
          {message}
        </p>
      )}
    </div>
  );
}

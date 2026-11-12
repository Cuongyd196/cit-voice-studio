import { AudioLines, Moon, RefreshCw, Sun } from "lucide-react";
import type React from "react";
import type { ConnectionStatus } from "../types";

const GPU_ENGINE = /GPU|CUDA|pytorch/i;
const CONNECTION_LABELS = {
  connected: "Sẵn sàng · Đổi mô hình",
  connecting: "Đang kết nối · Đổi mô hình",
  disconnected: "Mất kết nối · Đổi mô hình",
  error: "Mất kết nối · Đổi mô hình",
};
const CONNECTION_COLORS = {
  connected: "bg-green-600",
  connecting: "bg-amber-500",
  disconnected: "bg-rose-500",
  error: "bg-rose-500",
};
interface HeaderProps {
  engineName: string;
  isDark: boolean;
  onOpenSettings: () => void;
  onRefresh: () => void;
  onToggleDark: () => void;
  sampleRate: number;
  status: ConnectionStatus;
}

export const Header: React.FC<HeaderProps> = ({
  engineName,
  isDark,
  onOpenSettings,
  onRefresh,
  onToggleDark,
  sampleRate,
  status,
}) => (
  <header className="studio-header">
    <div className="flex items-center gap-2.5">
      <span className="studio-logo">
        <AudioLines size={18} />
      </span>
      <h1 className="font-bold text-sm tracking-tight">CIT Voice Studio</h1>
    </div>
    <div className="flex min-w-0 items-center gap-2">
      <button
        className="studio-model"
        onClick={onOpenSettings}
        title={CONNECTION_LABELS[status]}
        type="button"
      >
        <span
          className={`h-2 w-2 shrink-0 rounded-full ${CONNECTION_COLORS[status]}`}
        />
        <span className="truncate font-semibold">{engineName}</span>
        <span className="hidden whitespace-nowrap tabular-nums sm:inline">
          · {GPU_ENGINE.test(engineName) ? "GPU" : "CPU"} · {sampleRate / 1000}{" "}
          kHz
        </span>
        <span className="studio-model-action">⇄ Đổi mô hình</span>
      </button>
      {status !== "connected" && (
        <button
          aria-label="Thử kết nối lại"
          className="studio-icon-button"
          onClick={onRefresh}
          type="button"
        >
          <RefreshCw size={16} />
        </button>
      )}
      <button
        aria-label={
          isDark ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối"
        }
        className="studio-icon-button"
        onClick={onToggleDark}
        type="button"
      >
        {isDark ? <Sun size={17} /> : <Moon size={17} />}
      </button>
    </div>
  </header>
);

import {
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Settings,
  Sparkles,
  Volume2,
} from "lucide-react";
import type React from "react";

interface LoadingScreenProps {
  isDark: boolean;
  message: string;
  onOpenSettings: () => void;
  onRetry: () => void;
  status: "starting" | "downloading" | "ready" | "failed";
}

export const LoadingScreen: React.FC<LoadingScreenProps> = ({
  status,
  message,
  onRetry,
  onOpenSettings,
}) => {
  return (
    <div className="fixed inset-0 z-50 flex select-none flex-col items-center justify-center bg-background/95 px-4 backdrop-blur-xl">
      <div className="relative flex w-full max-w-md flex-col items-center overflow-hidden rounded-3xl border border-border/80 bg-card p-8 text-center shadow-2xl">
        {/* Background glow effects */}
        <div className="pointer-events-none absolute -top-20 -left-20 h-48 w-48 rounded-full bg-brand-500/20 blur-3xl" />
        <div className="pointer-events-none absolute -right-20 -bottom-20 h-48 w-48 rounded-full bg-cyan-500/20 blur-3xl" />

        {/* Animated Brand Logo */}
        <div className="relative mb-6">
          <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-to-tr from-brand-500 to-cyan-500 text-white shadow-brand-500/25 shadow-md">
            <Volume2 className="h-10 w-10 animate-pulse" />
          </div>
          {status === "failed" ? (
            <span className="absolute -right-1 -bottom-1 flex h-5 w-5">
              <span className="relative inline-flex h-5 w-5 items-center justify-center rounded-full border-2 border-card bg-rose-500 font-bold text-[12px] text-white">
                !
              </span>
            </span>
          ) : (
            <span className="absolute -right-1 -bottom-1 flex h-5 w-5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand-400 opacity-75" />
              <span className="relative inline-flex h-5 w-5 rounded-full border-2 border-card bg-brand-500" />
            </span>
          )}
        </div>

        {/* Title & Description */}
        <h2 className="mb-1.5 flex items-center gap-2 font-bold text-foreground text-xl tracking-tight">
          <span>CIT Voice Studio</span>
          <span className="rounded-full border border-brand-500/20 bg-brand-500/10 px-2 py-0.5 font-bold text-[12px] text-brand-600 uppercase dark:text-brand-400">
            v3 Turbo
          </span>
        </h2>
        <p className="mb-6 text-muted-foreground text-xs">
          Hệ thống tổng hợp giọng nói tiếng Việt trên máy tính
        </p>

        {/* Step Checklist */}
        <div className="mb-6 w-full space-y-3 rounded-2xl border border-border/60 bg-secondary/40 p-4 text-left">
          <div className="flex items-center gap-3 text-xs">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-brand-500" />
            <span className="font-medium text-foreground/90">
              1. Khởi động dịch vụ giọng nói
            </span>
          </div>

          <div className="flex items-center gap-3 text-xs">
            {status === "failed" ? (
              <AlertTriangle className="h-4 w-4 shrink-0 text-rose-500" />
            ) : status === "ready" ? (
              <CheckCircle2 className="h-4 w-4 shrink-0 text-brand-500" />
            ) : (
              <RefreshCw className="h-4 w-4 shrink-0 animate-spin text-amber-500" />
            )}
            <div className="min-w-0 flex-1">
              <span className="block font-medium text-foreground/90">
                2. Nạp mô hình giọng nói vào bộ nhớ
              </span>
              <span className="block break-words text-[12px] text-muted-foreground">
                {message || "Đang chuẩn bị mô hình giọng nói..."}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3 text-xs">
            <div
              className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full border text-[12px] ${
                status === "ready"
                  ? "border-brand-500 bg-brand-600 text-white"
                  : "border-border text-muted-foreground"
              }`}
            >
              3
            </div>
            <span className="font-medium text-muted-foreground">
              3. Sẵn sàng tạo giọng nói
            </span>
          </div>
        </div>

        {/* Action button if failed or taking too long */}
        {status === "failed" ? (
          <div className="w-full space-y-2">
            <button
              className="studio-primary flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-brand-500 to-teal-600 px-4 py-3 font-bold text-white text-xs shadow-brand-500/20 shadow-md transition-all hover:from-brand-600 hover:to-teal-700 active:scale-95"
              onClick={onRetry}
              type="button"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              <span>Thử kết nối lại ngay</span>
            </button>
            <button
              className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-border bg-secondary/80 px-4 py-2.5 font-medium text-foreground text-xs transition-all hover:bg-secondary"
              onClick={onOpenSettings}
              type="button"
            >
              <Settings className="h-3.5 w-3.5" />
              <span>Mở cài đặt kết nối</span>
            </button>
          </div>
        ) : (
          <div className="flex items-start gap-2 text-left text-muted-foreground text-xs leading-relaxed">
            <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" />
            <span>
              Mỗi lần mở ứng dụng cần nạp mô hình vào bộ nhớ. File mô hình đã
              tải được giữ trên máy để dùng lại; chỉ tải từ Internet khi còn
              thiếu.
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

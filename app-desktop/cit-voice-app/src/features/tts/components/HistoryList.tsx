import {
  Captions,
  Clock,
  Download,
  FolderOpen,
  History,
  Pause,
  Play,
  RotateCcw,
  Trash2,
  Volume2,
} from "lucide-react";
import type React from "react";
import { downloadBlobAsFile } from "../audio-engine";
import {
  entryBlob,
  entryFileBase,
  entrySubtitles,
  hasSubtitles,
  srtBlob,
} from "../history";
import type { HistoryEntry } from "../types";

interface HistoryListProps {
  items: HistoryEntry[];
  onClearAll: () => void;
  onDeleteItem: (id: string) => void;
  /** Tai audio; khong co thi tai blob (muc chi co trong phien hien tai). */
  onDownloadItem?: (item: HistoryEntry) => void;
  onPlayItem: (item: HistoryEntry) => void;
  /** Muc hoi thoai duoc dua ve tab Hoi thoai, con lai ve khung TTS. */
  onRestoreText: (item: HistoryEntry) => void;
  /** Mo thu muc chua file; chi co voi muc da luu xuong o dia (co serverId). */
  onRevealItem?: (item: HistoryEntry) => void;
  playingId: string | null;
}

export const HistoryList: React.FC<HistoryListProps> = ({
  items,
  playingId,
  onPlayItem,
  onRevealItem,
  onDownloadItem,
  onRestoreText,
  onDeleteItem,
  onClearAll,
}) => {
  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center space-y-2 rounded-2xl border border-border/80 border-dashed bg-card/50 p-8 text-muted-foreground text-xs">
        <History className="h-6 w-6 stroke-1 text-muted-foreground/60" />
        <span>Chưa có bản nào được tạo</span>
        <span className="text-[12px] text-muted-foreground/60">
          Các bản audio bạn tạo được lưu trên máy, vẫn còn khi mở lại ứng dụng
        </span>
      </div>
    );
  }

  return (
    <div className="studio-history space-y-3 rounded-[14px] border border-border bg-card p-4 shadow-md">
      {/* Header */}
      <div className="flex items-center justify-between border-border/60 border-b pb-2.5">
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-brand-500" />
          <h3 className="font-bold text-muted-foreground text-xs uppercase tracking-wider">
            Bản đã tạo ({items.length})
          </h3>
        </div>
        <button
          className="flex cursor-pointer items-center gap-1 text-rose-500 text-xs transition-all hover:text-rose-600 hover:underline"
          onClick={onClearAll}
          type="button"
        >
          <Trash2 className="h-3 w-3" />
          <span>Xóa hết</span>
        </button>
      </div>

      {/* History Items */}
      <div className="studio-history-list space-y-2">
        {items.map((item) => {
          const isItemPlaying = playingId === item.id;
          return (
            <div
              className={`studio-history-row group flex items-center justify-between rounded-xl border p-3 transition-all ${
                isItemPlaying
                  ? "border-brand-500/40 bg-brand-500/10 shadow-xs"
                  : "border-border/60 bg-secondary/40 hover:bg-secondary/70"
              }`}
              key={item.id}
            >
              {/* Left info */}
              <div className="min-w-0 flex-1 pr-3">
                <div className="mb-1 flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="rounded border border-brand-500/25 bg-brand-500/15 px-1.5 py-0.5 font-bold text-[12px] text-brand-600 dark:text-brand-400">
                    {item.voiceName}
                  </span>
                  <span className="flex items-center gap-0.5 text-[12px] text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    {item.durationSeconds
                      ? item.durationSeconds.toFixed(1)
                      : "0.0"}
                    s
                  </span>
                  <span className="text-[12px] text-muted-foreground/60">
                    {new Date(item.timestamp).toLocaleString("vi-VN")}
                  </span>
                  {isItemPlaying && (
                    <span className="flex animate-pulse items-center gap-1 font-bold text-[12px] text-brand-600 dark:text-brand-400">
                      <Volume2 className="h-3 w-3" />
                      <span>Đang phát...</span>
                    </span>
                  )}
                </div>
                <p className="line-clamp-2 break-words font-sans text-foreground/90 text-xs leading-relaxed">
                  {item.text}
                </p>
              </div>

              {/* Right actions */}
              <div className="flex shrink-0 items-center gap-1">
                {/* Play / Pause Toggle Button */}
                <button
                  className={`cursor-pointer rounded-lg p-2 shadow-xs transition-all ${
                    isItemPlaying
                      ? "scale-105 bg-brand-600 text-white shadow-brand-500/30"
                      : "bg-brand-500/10 text-brand-600 hover:bg-brand-500 hover:text-white"
                  }`}
                  onClick={() => onPlayItem(item)}
                  title={isItemPlaying ? "Tạm dừng" : "Nghe lại trực tiếp"}
                  type="button"
                >
                  {isItemPlaying ? (
                    <Pause className="h-4 w-4 fill-current" />
                  ) : (
                    <Play className="h-4 w-4 fill-current" />
                  )}
                </button>

                {/* Restore Text */}
                <button
                  className="cursor-pointer rounded-lg p-2 text-muted-foreground transition-all hover:bg-secondary hover:text-foreground"
                  onClick={() => onRestoreText(item)}
                  title="Đưa lại vào khung soạn thảo"
                  type="button"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                </button>

                {/* Download WAV */}
                <button
                  className="cursor-pointer rounded-lg p-2 text-muted-foreground transition-all hover:bg-secondary hover:text-foreground"
                  onClick={() =>
                    onDownloadItem
                      ? onDownloadItem(item)
                      : entryBlob(item)
                          .then((blob) =>
                            downloadBlobAsFile(
                              blob,
                              `${entryFileBase(item)}.${item.format ?? "wav"}`
                            )
                          )
                          .catch((e) => console.warn("[History]", e))
                  }
                  title={`Tải file ${(item.format ?? "wav").toUpperCase()}`}
                  type="button"
                >
                  <Download className="h-3.5 w-3.5" />
                </button>

                {onRevealItem && item.serverId && (
                  <button
                    className="cursor-pointer rounded-lg p-2 text-muted-foreground transition-all hover:bg-amber-500/10 hover:text-amber-600"
                    onClick={() => onRevealItem(item)}
                    title="Mở thư mục chứa file"
                    type="button"
                  >
                    <FolderOpen className="h-3.5 w-3.5" />
                  </button>
                )}

                {hasSubtitles(item) && (
                  <button
                    className="cursor-pointer rounded-lg p-2 text-violet-500 transition-all hover:bg-violet-500/10"
                    onClick={() =>
                      entrySubtitles(item).then((srt) => {
                        if (srt) {
                          downloadBlobAsFile(
                            srtBlob(srt),
                            `${entryFileBase(item)}.srt`
                          );
                        }
                      })
                    }
                    title="Tải phụ đề .srt"
                    type="button"
                  >
                    <Captions className="h-3.5 w-3.5" />
                  </button>
                )}

                {/* Delete Entry */}
                <button
                  className="cursor-pointer rounded-lg p-2 text-muted-foreground opacity-80 transition-all hover:bg-rose-500/10 hover:text-rose-500 group-hover:opacity-100"
                  onClick={() => onDeleteItem(item.id)}
                  title="Xóa mục này"
                  type="button"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

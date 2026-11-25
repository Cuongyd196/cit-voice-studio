import type React from "react";
import { useEffect, useMemo, useRef } from "react";
import {
  clampSelection,
  computePeaks,
  REF_MAX_SECONDS,
  REF_MIN_SECONDS,
  REF_USED_SECONDS,
  type RefSelection,
} from "../ref-audio";

interface ReferenceTrimmerProps {
  disabled?: boolean;
  onChange: (selection: RefSelection) => void;
  sampleRate: number;
  samples: Float32Array;
  selection: RefSelection;
}

// Số cột dạng sóng: đủ mịn cho khung rộng nhất của tab, tính một lần cho cả file.
const PEAK_BUCKETS = 600;
const HEIGHT = 64;

const fmt = (s: number) => `${s.toFixed(1)}s`;

/**
 * Chọn đoạn giọng mẫu trên dạng sóng (issue #2): file dài hơn mẫu cần thì người
 * dùng tự chọn đoạn nói rõ nhất, thay vì app luôn lấy vài giây đầu file (đầu file
 * hay có nhạc intro, tiếng ồn, câu chào vấp).
 *
 * Bấm/kéo trên dạng sóng để dời đoạn chọn; hai thanh trượt chỉnh chính xác và
 * dùng được bằng bàn phím.
 */
export const ReferenceTrimmer: React.FC<ReferenceTrimmerProps> = ({
  samples,
  sampleRate,
  selection,
  onChange,
  disabled = false,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const duration = samples.length / sampleRate;
  const peaks = useMemo(() => computePeaks(samples, PEAK_BUCKETS), [samples]);

  // Vẽ lại theo kích thước thật của khung (và mật độ điểm ảnh), màu lấy từ CSS
  // (`currentColor`) để theo giao diện sáng/tối.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const draw = () => {
      const dpr = window.devicePixelRatio || 1;
      const width = canvas.clientWidth;
      canvas.width = Math.max(1, Math.round(width * dpr));
      canvas.height = Math.round(HEIGHT * dpr);
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        return;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, HEIGHT);
      ctx.fillStyle = getComputedStyle(canvas).color;
      const max = peaks.reduce((m, v) => (v > m ? v : m), 0) || 1;
      const barW = width / peaks.length;
      const mid = HEIGHT / 2;
      for (let i = 0; i < peaks.length; i++) {
        const h = Math.max(1, (peaks[i] / max) * (HEIGHT - 4));
        ctx.fillRect(i * barW, mid - h / 2, Math.max(1, barW - 0.5), h);
      }
    };
    draw();
    const observer = new ResizeObserver(draw);
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [peaks]);

  const moveTo = (clientX: number, el: HTMLElement) => {
    const rect = el.getBoundingClientRect();
    const t = ((clientX - rect.left) / rect.width) * duration;
    onChange(
      clampSelection(
        { start: t - selection.length / 2, length: selection.length },
        duration
      )
    );
  };

  const left = (selection.start / duration) * 100;
  const width = (selection.length / duration) * 100;
  const usedWidth =
    (Math.min(selection.length, REF_USED_SECONDS) / duration) * 100;
  const maxLen = Math.min(REF_MAX_SECONDS, duration);
  const minLen = Math.min(REF_MIN_SECONDS, maxLen);

  return (
    <div className="space-y-2">
      <div
        className={`relative select-none overflow-hidden rounded-lg border border-border/70 bg-secondary/30 ${disabled ? "opacity-60" : "cursor-pointer"}`}
        onPointerDown={(e) => {
          if (disabled) {
            return;
          }
          e.currentTarget.setPointerCapture(e.pointerId);
          moveTo(e.clientX, e.currentTarget);
        }}
        onPointerMove={(e) => {
          if (!disabled && e.currentTarget.hasPointerCapture(e.pointerId)) {
            moveTo(e.clientX, e.currentTarget);
          }
        }}
        style={{ height: HEIGHT }}
      >
        <canvas
          className="absolute inset-0 h-full w-full text-muted-foreground/50"
          ref={canvasRef}
        />
        {/* Đoạn chọn; phần đậm hơn là phần mô hình thực sự dùng (8 giây đầu). */}
        <div
          className="pointer-events-none absolute inset-y-0 border-brand-500 border-x-2 bg-brand-500/10"
          style={{ left: `${left}%`, width: `${width}%` }}
        />
        <div
          className="pointer-events-none absolute inset-y-0 bg-brand-500/15"
          style={{ left: `${left}%`, width: `${usedWidth}%` }}
        />
      </div>

      <div className="grid grid-cols-[auto_1fr_auto] items-center gap-x-2 gap-y-1.5 text-[12px] text-muted-foreground">
        <label htmlFor="ref-start">Bắt đầu</label>
        <input
          className="h-1.5 cursor-pointer appearance-none rounded-lg bg-secondary accent-brand-500"
          disabled={disabled || duration <= selection.length}
          id="ref-start"
          max={Math.max(0, duration - selection.length)}
          min={0}
          onChange={(e) =>
            onChange(
              clampSelection(
                { start: Number(e.target.value), length: selection.length },
                duration
              )
            )
          }
          step={0.1}
          type="range"
          value={selection.start}
        />
        <span className="w-12 text-right font-mono">
          {fmt(selection.start)}
        </span>

        <label htmlFor="ref-length">Độ dài</label>
        <input
          className="h-1.5 cursor-pointer appearance-none rounded-lg bg-secondary accent-brand-500"
          disabled={disabled || maxLen <= minLen}
          id="ref-length"
          max={maxLen}
          min={minLen}
          onChange={(e) =>
            onChange(
              clampSelection(
                { start: selection.start, length: Number(e.target.value) },
                duration
              )
            )
          }
          step={0.5}
          type="range"
          value={selection.length}
        />
        <span className="w-12 text-right font-mono">
          {fmt(selection.length)}
        </span>
      </div>

      {selection.length > REF_USED_SECONDS && (
        <p className="text-[12px] text-amber-700 dark:text-amber-300">
          Mô hình chỉ dùng {REF_USED_SECONDS} giây đầu của đoạn chọn (phần tô
          đậm).
        </p>
      )}
    </div>
  );
};

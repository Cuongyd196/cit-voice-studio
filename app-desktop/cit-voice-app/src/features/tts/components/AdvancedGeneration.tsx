import type React from "react";
import { useId } from "react";
import { useModelCaps } from "../model-caps";
import { InfoTip } from "./InfoTip";

// Mặc định của tác giả VieNeu cho mô hình v3 (bản Gradio gốc của VieNeu-TTS).
export const DEFAULT_TEMPERATURE = 0.8;

interface AdvancedGenerationProps {
  disabled?: boolean;
  onChangeTemperature: (value: number) => void;
  temperature: number;
}

/**
 * Cảm xúc hiển thị trực tiếp như bản Gradio của tác giả, mặc định 0,8.
 * Ẩn với Supertonic vì mô hình này bỏ qua temperature.
 */
export const AdvancedGeneration: React.FC<AdvancedGenerationProps> = ({
  disabled,
  onChangeTemperature,
  temperature,
}) => {
  const multilingual = useModelCaps().languages.length > 0;
  // TTS Studio và Hội thoại cùng nằm trong DOM: id cố định sẽ bị trùng.
  const inputId = useId();
  if (multilingual) {
    return null;
  }
  return (
    <div className="studio-advanced rounded-xl border border-border/80 bg-card px-3 py-2 shadow-sm">
      <div className="space-y-1.5">
        <div className="info-tip-row flex items-center justify-between gap-2 text-xs">
          <span className="flex items-center gap-1">
            <label className="font-medium text-foreground/80" htmlFor={inputId}>
              Cảm xúc (Temperature)
            </label>
            <InfoTip label="Cảm xúc">
              <strong>Độ biến tấu ngữ điệu.</strong>
              <span>
                Tác giả VieNeu khuyên 0,7–0,8; mặc định 0,8 ổn định nhất.
              </span>
              <span>
                Thấp hơn: đều, ít biểu cảm. Cao hơn: biểu cảm hơn, dễ lỗi.
              </span>
              <span>Mô hình Nano không dùng thông số này.</span>
            </InfoTip>
          </span>
          <div className="flex items-center gap-1">
            <span className="font-bold font-mono text-brand-600 dark:text-brand-400">
              {temperature.toLocaleString("vi-VN", {
                minimumFractionDigits: 1,
              })}
            </span>
            <button
              className="ml-1 h-6 rounded border border-border/80 bg-background px-2 font-semibold text-muted-foreground text-xs transition-colors hover:bg-secondary hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
              disabled={disabled || temperature === DEFAULT_TEMPERATURE}
              onClick={() => onChangeTemperature(DEFAULT_TEMPERATURE)}
              type="button"
            >
              Mặc định
            </button>
          </div>
        </div>
        <input
          aria-describedby={`${inputId}-hint`}
          className="h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-secondary accent-brand-500"
          disabled={disabled}
          id={inputId}
          max="1.5"
          min="0.1"
          onChange={(e) =>
            onChangeTemperature(Number.parseFloat(e.target.value))
          }
          step="0.1"
          type="range"
          value={temperature}
        />
        {/* Chú thích theo bản Gradio của tác giả, dùng dấu phẩy thập phân tiếng Việt. */}
        <p
          className="text-[12px] text-muted-foreground leading-relaxed"
          id={`${inputId}-hint`}
        >
          0,7 - 0,8: Tự nhiên nhất
        </p>
      </div>
    </div>
  );
};

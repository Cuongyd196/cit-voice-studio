import { Laugh, Megaphone, Pause, Sparkles, Wind } from "lucide-react";
import type React from "react";
import { useModelCaps } from "../model-caps";

interface EmotionBarProps {
  disabled?: boolean;
  onInsertTag: (tag: string) => void;
}

const EMOTIONS = [
  {
    tag: "[cười]",
    label: "Cười",
    icon: Laugh,
    color:
      "text-amber-800 dark:text-amber-400 hover:bg-amber-500/25 border-amber-500/45 hover:border-amber-500/70 bg-amber-500/15",
  },
  {
    tag: "[hắng giọng]",
    label: "Hắng giọng",
    icon: Megaphone,
    color:
      "text-purple-800 dark:text-purple-300 hover:bg-purple-500/25 border-purple-500/45 hover:border-purple-500/70 bg-purple-500/15",
  },
  {
    tag: "[thở dài]",
    label: "Thở dài",
    icon: Wind,
    color:
      "text-sky-800 dark:text-sky-300 hover:bg-sky-500/25 border-sky-500/45 hover:border-sky-500/70 bg-sky-500/15",
  },
];

// The goc cua Supertonic (mo hinh nhieu ngon ngu): chen thang, may chu giu nguyen.
const SUPERTONIC_EMOTIONS = [
  { ...EMOTIONS[0], tag: "<laugh>" },
  {
    tag: "<breath>",
    label: "Lấy hơi",
    icon: Wind,
    color:
      "text-emerald-800 dark:text-emerald-300 hover:bg-emerald-500/25 border-emerald-500/45 hover:border-emerald-500/70 bg-emerald-500/15",
  },
  { ...EMOTIONS[2], tag: "<sigh>" },
];

const PAUSE_TAG = "[nghỉ 1s]";

export const EmotionBar: React.FC<EmotionBarProps> = ({
  onInsertTag,
  disabled,
}) => {
  // Mo hinh doc nhieu ngon ngu (Supertonic) dung the rieng <laugh> <breath> <sigh>.
  const { languages, supportsEmotions } = useModelCaps();
  const multilingual = languages.length > 0;
  // Kokoro khong co the cam xuc: chi con nut chen the nghi.
  let emotions = multilingual ? SUPERTONIC_EMOTIONS : EMOTIONS;
  if (!supportsEmotions) {
    emotions = [];
  }
  return (
    <div className="flex flex-wrap items-center justify-between gap-1.5 rounded-lg border border-border/60 bg-secondary/25 px-2.5 py-1 sm:py-1.5">
      <div className="flex items-center gap-1.5 font-medium text-foreground/90 text-xs sm:text-[13px]">
        <Sparkles
          aria-hidden="true"
          className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400"
        />
        <span>Cảm xúc:</span>
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        {emotions.map((item) => (
          <button
            className={`inline-flex select-none items-center gap-1.5 rounded-md border px-2.5 py-1 font-semibold text-xs shadow-xs transition-all active:scale-95 sm:text-[13px] ${
              item.color
            } ${disabled ? "cursor-not-allowed opacity-40" : "cursor-pointer"}`}
            disabled={disabled}
            key={item.tag}
            onClick={() => onInsertTag(item.tag)}
            title={`Chèn thẻ cảm xúc ${item.tag}`}
            type="button"
          >
            <item.icon aria-hidden="true" className="h-3.5 w-3.5" />
            <span>{item.label}</span>
            <code className="ml-0.5 font-mono text-[12px] opacity-75 sm:text-[12px]">
              {item.tag}
            </code>
          </button>
        ))}
        {/* The nghi: server tach van ban tai the va chen dung so giay im lang.
            Chay voi moi mo hinh, khong rieng v3 Turbo. Sua so giay sau khi chen. */}
        <button
          className={`inline-flex select-none items-center gap-1.5 rounded-md border border-slate-500/45 bg-slate-500/15 px-2.5 py-1 font-semibold text-slate-600 text-xs shadow-xs transition-all hover:border-slate-500/70 hover:bg-slate-500/25 active:scale-95 sm:text-[13px] dark:text-slate-300 ${disabled ? "cursor-not-allowed opacity-40" : "cursor-pointer"}`}
          disabled={disabled}
          onClick={() => onInsertTag(PAUSE_TAG)}
          title="Chèn khoảng nghỉ. Sửa số giây trong thẻ: [nghỉ 2s], [nghỉ 0.5s], [nghỉ 500ms] - tối đa 10 giây."
          type="button"
        >
          <Pause className="h-3.5 w-3.5" />
          <span>Khoảng nghỉ</span>
          <code className="ml-0.5 font-mono text-[12px] opacity-75 sm:text-[12px]">
            {PAUSE_TAG}
          </code>
        </button>
      </div>
    </div>
  );
};

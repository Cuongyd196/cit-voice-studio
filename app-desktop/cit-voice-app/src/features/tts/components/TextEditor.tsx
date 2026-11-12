import {
  BookOpen,
  Clipboard,
  Copy,
  Eraser,
  Sparkles,
  Trash2,
  Undo2,
} from "lucide-react";
import type React from "react";
import { useEffect, useState } from "react";
import { useModelCaps } from "../model-caps";
import { cleanMarkdown } from "../text-tools";
import { useCaretInsert } from "../use-caret-insert";
import { EmotionBar } from "./EmotionBar";

/** Thời gian hiện dòng thông báo cạnh nút Làm sạch. */
const NOTICE_MS = 3000;

interface TextEditorProps {
  disabled?: boolean;
  onChange: (val: string) => void;
  /** Mở từ điển phát âm (KTX → ký túc xá...). */
  onOpenDictionary?: () => void;
  text: string;
}

const PRESET_SAMPLES = [
  {
    label: "Giới thiệu",
    text: "Xin chào các bạn! Chào mừng bạn đến với CIT Voice Studio. Đây là giọng đọc trí tuệ nhân tạo tiếng Việt chất lượng cao, phát âm tự nhiên và truyền cảm.",
  },
  {
    label: "Cảm xúc",
    text: "Xin chào cả nhà! Hôm nay tôi có một tin cực kỳ vui muốn chia sẻ. [cười] Dự án của chúng ta đã chính thức hoàn thành xuất sắc! [thở dài] Nhưng thật sự cũng khá là vất vả đấy nhé.",
  },
  {
    label: "Thuyết minh",
    text: "[hắng giọng] Kính thưa quý vị đại biểu, hôm nay chúng tôi xin trân trọng giới thiệu công nghệ VieNeu-TTS v3 Turbo với khả năng tổng hợp giọng nói thời gian thực.",
  },
  {
    label: "Kể chuyện",
    text: "Ngày xửa ngày xưa, ở một thảo nguyên bạt ngàn hoa dại, có một chú cáo nhỏ luôn ước mơ được bay lượn trên bầu trời xanh thẳm. [thở dài] Biết bao giờ ước mơ mới thành hiện thực?",
  },
  {
    label: "Quảng cáo",
    text: "Khám phá ngay công cụ lồng tiếng video ngắn tự động với âm thanh chuẩn 48kHz sắc nét. [cười] Nhanh chóng, chuyên nghiệp và hoàn toàn miễn phí!",
  },
];

// Mo hinh nhieu ngon ngu (Supertonic) dung cho van ban tieng nuoc ngoai, nen mau
// la tieng Anh (ngon ngu mac dinh) va dung the cam xuc rieng cua no.
const PRESET_SAMPLES_FOREIGN = [
  {
    label: "Giới thiệu",
    text: "Hello everyone! Welcome to CIT Voice Studio. This is a high-quality AI voice that sounds natural and expressive.",
  },
  {
    label: "Cảm xúc",
    text: "Hi everyone! I have some really exciting news to share today. <laugh> Our project has officially been completed! <sigh> But honestly, it was quite a lot of work.",
  },
  {
    label: "Thuyết minh",
    text: "Ladies and gentlemen, <breath> today we are proud to present a speech technology that runs in real time on an ordinary computer.",
  },
  {
    label: "Kể chuyện",
    text: "Once upon a time, on a vast meadow full of wildflowers, there lived a little fox who dreamed of flying across the deep blue sky. <sigh> When would that dream ever come true?",
  },
  {
    label: "Quảng cáo",
    text: "Discover an automatic voice-over tool for short videos, with crisp studio-quality sound. <laugh> Fast, professional and completely free!",
  },
];

export const TextEditor: React.FC<TextEditorProps> = ({
  text,
  onChange,
  onOpenDictionary,
  disabled,
}) => {
  const { languages, readsVietnamese } = useModelCaps();
  const multilingual = languages.length > 0;
  const charCount = text.length;
  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;
  const sentenceCount = text.trim()
    ? (text.match(/[^.!?]+[.!?]+/g) || [text]).length
    : 0;

  const handlePaste = async () => {
    try {
      const clipboardText = await navigator.clipboard.readText();
      if (clipboardText) {
        onChange(text ? `${text}\n${clipboardText}` : clipboardText);
      }
    } catch {
      // Giữ nguyên nội dung khi không đọc được bộ nhớ tạm
    }
  };

  const handleCopy = () => {
    if (text) {
      navigator.clipboard.writeText(text);
    }
  };

  const {
    textareaRef,
    onFocus,
    insertTag: handleInsertEmotion,
  } = useCaretInsert(text, onChange, disabled);
  // Hoàn tác chỉ có nghĩa khi văn bản vẫn đúng là bản vừa làm sạch; người dùng
  // sửa tiếp thì nút tự ẩn, tránh ghi đè mất phần họ vừa gõ.
  const [undo, setUndo] = useState<{ before: string; after: string } | null>(
    null
  );
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!notice) {
      return;
    }
    const timer = setTimeout(() => setNotice(null), NOTICE_MS);
    return () => clearTimeout(timer);
  }, [notice]);

  const handleClean = () => {
    const cleaned = cleanMarkdown(text);
    if (cleaned === text) {
      setNotice("Không có ký hiệu cần làm sạch");
      return;
    }
    setUndo({ before: text, after: cleaned });
    onChange(cleaned);
    setNotice("Đã làm sạch ký hiệu định dạng");
  };

  const canUndo = undo !== null && text === undo.after;
  const handleUndo = () => {
    if (!canUndo) {
      return;
    }
    onChange(undo.before);
    setUndo(null);
    setNotice(null);
  };

  return (
    <div className="studio-text-editor">
      <div className="studio-editor-heading">
        <h2>Đọc văn bản</h2>
        <span className="studio-editor-stats">
          {charCount.toLocaleString("vi-VN")} ký tự · {wordCount} từ ·{" "}
          {sentenceCount} câu · ~{Math.ceil(wordCount / 2.5)} giây
        </span>
      </div>
      <div className="studio-editor-toolbar">
        {/* Công cụ văn bản */}
        <div className="flex items-center gap-1.5">
          {notice && (
            <span className="hidden text-muted-foreground text-xs italic md:inline">
              {notice}
            </span>
          )}
          {canUndo && (
            <button
              className="flex items-center gap-1 rounded-md px-2 py-1 font-medium text-amber-600 text-xs transition-colors hover:bg-amber-500/10 disabled:opacity-50 dark:text-amber-400"
              disabled={disabled}
              onClick={handleUndo}
              title="Trả lại văn bản trước khi làm sạch"
              type="button"
            >
              <Undo2 className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Hoàn tác</span>
            </button>
          )}
          <button
            className="flex items-center gap-1 rounded-md px-2 py-1 font-medium text-muted-foreground text-xs transition-colors hover:bg-secondary/80 hover:text-foreground disabled:opacity-50"
            disabled={!text || disabled}
            onClick={handleClean}
            title="Bỏ ký hiệu định dạng khi dán từ ChatGPT/Gemini… (**đậm**, ## tiêu đề, > trích dẫn, link) để app không đọc thành tiếng"
            type="button"
          >
            <Eraser className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Làm sạch</span>
          </button>
          {/* Tu dien viet cach doc tieng Viet: an khi mo hinh khong doc tieng Viet (Kokoro). */}
          {onOpenDictionary && readsVietnamese && (
            <button
              className="flex items-center gap-1 rounded-md px-2 py-1 font-medium text-violet-600 text-xs transition-colors hover:bg-violet-500/10 dark:text-violet-400"
              onClick={onOpenDictionary}
              title="Từ điển phát âm - dạy app đọc từ viết tắt (KTX → ký túc xá)"
              type="button"
            >
              <BookOpen className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Từ điển</span>
            </button>
          )}
          <button
            className="flex items-center gap-1 rounded-md px-2 py-1 font-medium text-muted-foreground text-xs transition-colors hover:bg-secondary/80 hover:text-foreground disabled:opacity-50"
            disabled={disabled}
            onClick={handlePaste}
            title="Dán từ Clipboard"
            type="button"
          >
            <Clipboard className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Dán</span>
          </button>
          <button
            className="flex items-center gap-1 rounded-md px-2 py-1 font-medium text-muted-foreground text-xs transition-colors hover:bg-secondary/80 hover:text-foreground disabled:opacity-50"
            disabled={!text || disabled}
            onClick={handleCopy}
            title="Sao chép văn bản"
            type="button"
          >
            <Copy className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Chép</span>
          </button>
          <button
            className="flex items-center gap-1 rounded-md px-2 py-1 font-medium text-rose-500 text-xs transition-colors hover:bg-rose-500/10 disabled:opacity-50"
            disabled={!text || disabled}
            onClick={() => onChange("")}
            title="Xóa toàn bộ"
            type="button"
          >
            <Trash2 className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Xóa</span>
          </button>
        </div>
      </div>

      <div className="studio-emotions">
        <EmotionBar disabled={disabled} onInsertTag={handleInsertEmotion} />
      </div>
      {/* Ô văn bản tự cuộn, không làm cuộn trang. */}
      <div className="studio-textarea-area">
        <textarea
          aria-label="Văn bản cần đọc"
          className="studio-textarea"
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          onFocus={onFocus}
          placeholder={`Nhập hoặc dán nội dung văn bản ${multilingual ? "" : "tiếng Việt "}bạn muốn chuyển thành giọng nói tại đây...`}
          ref={textareaRef}
          spellCheck={false}
          value={text}
        />
      </div>

      {/* Các mẫu văn bản có sẵn */}
      <div className="flex flex-wrap items-center gap-1.5 border-border/40 border-t bg-muted/20 px-3 py-1.5 sm:px-3.5">
        <span className="mr-0.5 flex items-center gap-1 font-medium text-muted-foreground text-xs">
          <Sparkles className="h-3.5 w-3.5 text-amber-500" />
          Mẫu:
        </span>
        {(multilingual ? PRESET_SAMPLES_FOREIGN : PRESET_SAMPLES).map(
          (sample) => (
            <button
              className="rounded-full border border-border/60 bg-secondary/80 px-2.5 py-0.5 font-medium text-foreground/80 text-xs transition-all hover:border-brand-500/40 hover:bg-secondary hover:text-foreground active:scale-95"
              disabled={disabled}
              key={sample.label}
              onClick={() => onChange(sample.text)}
              type="button"
            >
              {sample.label}
            </button>
          )
        )}
      </div>
    </div>
  );
};

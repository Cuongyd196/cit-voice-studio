import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Copy,
  FileCheck,
  FileText,
  Loader2,
  MessagesSquare,
  Sparkles,
  Trash2,
  Upload,
} from "lucide-react";
import type React from "react";
import { useState } from "react";
import { extractPdfText, parseSrt, type SrtCue } from "../api";
import { readTextFile } from "../read-text-file";
import { cleanExtractedText, describeCleanup } from "../text-cleanup";
import type { HistoryEntry, PdfExtractionResult, VoiceOption } from "../types";
import { SrtDubbing } from "./SrtDubbing";

const FORMATS = ["PDF", "DOCX", "TXT", "SRT / VTT"];

interface DropzoneProps {
  busy: boolean;
  onFile: (file: File) => void;
}

/** Vùng thả file: cả khung là nút chọn file (input phủ kín, trong suốt). */
function DocDropzone({ busy, onFile }: DropzoneProps) {
  return (
    <div
      className="doc-dropzone"
      data-busy={busy || undefined}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        const file = e.dataTransfer.files?.[0];
        if (file) {
          onFile(file);
        }
      }}
    >
      <input
        accept=".pdf,.docx,.doc,.txt,.srt,.vtt"
        aria-label="Chọn file tài liệu hoặc phụ đề"
        className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
        disabled={busy}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) {
            onFile(file);
          }
          e.target.value = "";
        }}
        type="file"
      />
      <span aria-hidden="true" className="doc-dropzone-icon">
        {busy ? (
          <Loader2 className="animate-spin" size={26} />
        ) : (
          <Upload size={26} />
        )}
      </span>
      <p className="doc-dropzone-title">
        {busy ? "Đang đọc tài liệu..." : "Kéo thả file vào đây"}
      </p>
      {!busy && (
        <p className="doc-dropzone-hint">
          hoặc <span className="doc-dropzone-link">bấm để chọn file</span>
        </p>
      )}
      <div className="doc-formats">
        {FORMATS.map((f) => (
          <span key={f}>{f}</span>
        ))}
      </div>
    </div>
  );
}

const STEPS = [
  ["Chọn file", "PDF, Word, TXT để đọc; SRT/VTT để lồng tiếng."],
  ["Kiểm tra nội dung", "Sửa chữ, bấm Làm sạch nếu cần."],
  ["Tạo giọng đọc", "Gửi sang Đọc văn bản hoặc Hội thoại."],
];

function DocGuide() {
  return (
    <div className="studio-tab-card doc-guide">
      <h4>Cách dùng</h4>
      <ol>
        {STEPS.map(([title, desc], i) => (
          <li key={title}>
            <span className="doc-step">{i + 1}</span>
            <span>
              <strong>{title}</strong>
              {desc}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

interface PdfReaderTabProps {
  apiUrl: string;
  defaultVoiceId: string;
  onAddHistory: (entry: HistoryEntry) => void;
  onSendToConversation: (text: string) => void;
  onSendToTts: (text: string) => void;
  voices: VoiceOption[];
}

interface SrtFile {
  cues: SrtCue[];
  durationSeconds: number;
  name: string;
  text: string;
}

const SUBTITLE_FILE = /\.(srt|vtt)$/i;

export const PdfReaderTab: React.FC<PdfReaderTabProps> = ({
  apiUrl,
  defaultVoiceId,
  onAddHistory,
  onSendToTts,
  onSendToConversation,
  voices,
}) => {
  const [srtFile, setSrtFile] = useState<SrtFile | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isExtracting, setIsExtracting] = useState<boolean>(false);
  const [extractResult, setExtractResult] =
    useState<PdfExtractionResult | null>(null);
  const [cleanedText, setCleanedText] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [copySuccess, setCopySuccess] = useState<boolean>(false);
  const [cleanNotice, setCleanNotice] = useState<string | null>(null);

  // Handle File selection
  const handleFileSelect = async (file: File) => {
    setIsExtracting(true);
    setErrorMessage(null);
    setCleanNotice(null);

    // File phu de: chuyen sang che do long tieng theo moc thoi gian.
    if (SUBTITLE_FILE.test(file.name)) {
      try {
        const text = await readTextFile(file);
        const parsed = await parseSrt(apiUrl, text);
        setSrtFile({ ...parsed, name: file.name, text });
      } catch (err) {
        setErrorMessage(
          err instanceof Error ? err.message : "Không đọc được file phụ đề."
        );
      } finally {
        setIsExtracting(false);
      }
      return;
    }

    setSelectedFile(file);
    setExtractResult(null);
    try {
      const res = await extractPdfText(apiUrl, file, file.name);
      setExtractResult(res);
      setCleanedText(res.text);
    } catch (err: any) {
      setErrorMessage(
        err.message || "Không thể trích xuất văn bản từ tài liệu này."
      );
    } finally {
      setIsExtracting(false);
    }
  };

  // Lam sach: bo dong trong, gach dau dong, cho trong de dien; noi dong bi ngat
  // giua cau. Giu nguyen cong thuc - xem text-cleanup.ts.
  const handleCleanFormatting = () => {
    if (!cleanedText) {
      return;
    }
    const { text, stats } = cleanExtractedText(cleanedText);
    setCleanedText(text);
    setCleanNotice(
      describeCleanup(stats) || "Văn bản đã sạch, không có gì cần sửa."
    );
  };

  // Copy text
  const handleCopy = () => {
    if (cleanedText) {
      navigator.clipboard.writeText(cleanedText);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    }
  };

  const wordCount = cleanedText.trim()
    ? cleanedText.trim().split(/\s+/).length
    : 0;

  if (srtFile) {
    return (
      <SrtDubbing
        apiUrl={apiUrl}
        cues={srtFile.cues}
        defaultVoiceId={defaultVoiceId}
        durationSeconds={srtFile.durationSeconds}
        fileName={srtFile.name}
        onAddHistory={onAddHistory}
        onClose={() => setSrtFile(null)}
        srt={srtFile.text}
        voices={voices}
      />
    );
  }

  const hasText = Boolean(cleanedText);

  return (
    <div className="studio-tab-grid studio-document-layout fade-in-50 animate-in duration-300">
      {/* Cột trái: chọn file, thông tin file, hướng dẫn */}
      <div className="studio-span-5 flex flex-col gap-4">
        <div className="studio-tab-card doc-card">
          <div className="doc-card-head">
            <h3>Đọc file</h3>
            <p>Lấy chữ từ tài liệu hoặc lồng tiếng theo phụ đề.</p>
          </div>
          <DocDropzone busy={isExtracting} onFile={handleFileSelect} />

          {extractResult && selectedFile && (
            <div className="doc-file">
              <FileCheck aria-hidden="true" size={20} />
              <div className="min-w-0">
                <p className="truncate font-semibold">{selectedFile.name}</p>
                <p className="text-muted-foreground">
                  {extractResult.page_count
                    ? `${extractResult.page_count} trang · `
                    : ""}
                  {(selectedFile.size / 1024).toFixed(1)} KB
                </p>
              </div>
            </div>
          )}

          {errorMessage && (
            <div className="doc-error" role="alert">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}
        </div>
        {!hasText && <DocGuide />}
      </div>

      {/* Cột phải: nội dung trích xuất, sửa được trước khi đọc */}
      <div className="studio-span-7 flex flex-col">
        <div className="studio-tab-card doc-editor">
          <div className="doc-editor-head">
            <h3>
              <FileText size={18} />
              Nội dung
            </h3>
            <div className="doc-editor-tools">
              <button
                disabled={!hasText}
                onClick={handleCleanFormatting}
                title="Bỏ dòng trống, gạch đầu dòng, chỗ trống để điền (....., ___); nối dòng bị ngắt giữa câu. Giữ nguyên công thức như 1 + 1."
                type="button"
              >
                <Sparkles size={15} />
                Làm sạch
              </button>
              <button
                disabled={!hasText}
                onClick={handleCopy}
                title="Sao chép toàn bộ"
                type="button"
              >
                <Copy size={15} />
                {copySuccess ? "Đã chép!" : "Sao chép"}
              </button>
              <button
                aria-label="Xoá nội dung"
                className="doc-danger"
                disabled={!hasText}
                onClick={() => {
                  setCleanedText("");
                  setCleanNotice(null);
                }}
                title="Xoá nội dung"
                type="button"
              >
                <Trash2 size={15} />
              </button>
            </div>
          </div>

          {cleanNotice && (
            <div aria-live="polite" className="doc-notice" role="status">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span>{cleanNotice}</span>
            </div>
          )}

          <div className="doc-textarea-wrap">
            <textarea
              aria-label="Nội dung trích xuất"
              onChange={(e) => {
                setCleanedText(e.target.value);
                setCleanNotice(null);
              }}
              value={cleanedText}
            />
            {!hasText && (
              <div aria-hidden="true" className="doc-empty">
                <FileText size={34} />
                <p>Chưa có nội dung</p>
                <span>Chọn file bên trái, hoặc dán văn bản vào đây.</span>
              </div>
            )}
          </div>

          <div className="doc-footer">
            <span className="doc-stats">
              {cleanedText.length.toLocaleString("vi-VN")} ký tự ·{" "}
              {wordCount.toLocaleString("vi-VN")} từ · ~
              {Math.ceil(wordCount / 2.5)} giây audio
            </span>
            <div className="doc-send">
              <button
                className="doc-send-secondary"
                disabled={!hasText}
                onClick={() => onSendToConversation(cleanedText)}
                type="button"
              >
                <MessagesSquare size={16} />
                Sang Hội thoại
              </button>
              <button
                className="studio-primary doc-send-primary"
                disabled={!hasText}
                onClick={() => onSendToTts(cleanedText)}
                type="button"
              >
                Đọc văn bản này
                <ArrowRight size={16} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

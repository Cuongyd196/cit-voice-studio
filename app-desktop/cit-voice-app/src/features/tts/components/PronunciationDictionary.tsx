import {
  AlertCircle,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Download,
  FileDown,
  FileUp,
  Info,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Trash2,
  Volume2,
  X,
} from "lucide-react";
import type React from "react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import {
  fetchPronunciations,
  type PronunciationEntry,
  previewPronunciations,
  savePronunciations,
  synthesizeSpeech,
} from "../api";
import { downloadBlobAsFile } from "../audio-engine";
import {
  dictionaryToCsv,
  MAX_ENTRIES,
  parseDictionaryCsv,
  SAMPLE_DICTIONARY_ROWS,
  toCsv,
} from "../pronunciation-csv";
import { readTextFile } from "../read-text-file";

interface PronunciationDictionaryModalProps {
  apiUrl: string;
  isOpen: boolean;
  onClose: () => void;
}

// Mỗi dòng cần mã ổn định vì người dùng có thể sửa cả từ gốc.
interface Row extends PronunciationEntry {
  id: number;
}

let nextId = 1;
const toRows = (entries: PronunciationEntry[]): Row[] =>
  entries.map((e) => ({ ...e, id: nextId++ }));

const toEntries = (rows: Row[]): PronunciationEntry[] =>
  rows
    .filter((r) => r.word.trim() && r.reading.trim())
    .map(({ word, reading, match_case }) => ({
      word: word.trim(),
      reading: reading.trim(),
      match_case,
    }));

const errorText = (e: unknown) => (e instanceof Error ? e.message : String(e));

const csvBlob = (content: string) =>
  new Blob([content], { type: "text/csv;charset=utf-8" });

/** Gộp mục nhập từ CSV vào bản nháp: trùng từ gốc thì cập nhật, còn lại thêm lên đầu. */
function mergeRows(rows: Row[], imported: PronunciationEntry[]) {
  const byWord = new Map(imported.map((e) => [e.word, e]));
  let updated = 0;
  const merged = rows.map((r) => {
    const hit = byWord.get(r.word.trim());
    if (!hit) {
      return r;
    }
    byWord.delete(r.word.trim());
    updated++;
    return { ...r, ...hit };
  });
  const added = toRows([...byWord.values()]);
  return { rows: [...added, ...merged], added: added.length, updated };
}

/** Thông báo sau khi nhập: số từ mới/cập nhật và tối đa 3 dòng bị bỏ qua. */
function importSummary(
  added: number,
  updated: number,
  skipped: { line: number; reason: string }[]
): string {
  let text = `Đã nhập ${added} từ mới, cập nhật ${updated} từ.`;
  if (skipped.length) {
    const lines = skipped
      .slice(0, 3)
      .map((x) => `dòng ${x.line}: ${x.reason}`)
      .join("; ");
    const more = skipped.length > 3 ? "; ..." : "";
    text += ` Bỏ qua ${skipped.length} dòng (${lines}${more}).`;
  }
  return `${text} Bấm "Lưu từ điển" để áp dụng.`;
}

interface DictRowProps {
  onChange: (patch: Partial<PronunciationEntry>) => void;
  onPlay: () => void;
  onRemove: () => void;
  playDisabled: boolean;
  playing: boolean;
  row: Row;
}

const inputBorder = (missing: boolean) =>
  missing ? "border-rose-500" : "border-border";

function DictRow({
  row,
  playing,
  playDisabled,
  onChange,
  onPlay,
  onRemove,
}: DictRowProps) {
  const wordId = useId();
  const readingId = useId();
  const hasWord = Boolean(row.word.trim());
  const hasReading = Boolean(row.reading.trim());
  const half = hasWord !== hasReading;
  return (
    <div className="dictionary-row">
      <label className="dictionary-word" htmlFor={wordId}>
        <span>Từ gốc</span>
        <input
          aria-invalid={half && !hasWord}
          className={inputBorder(half && !hasWord)}
          id={wordId}
          maxLength={64}
          onChange={(e) => onChange({ word: e.target.value })}
          placeholder="Ví dụ: KTX"
          value={row.word}
        />
      </label>
      <ArrowRight aria-hidden="true" className="dictionary-arrow" size={16} />
      <label className="dictionary-reading" htmlFor={readingId}>
        <span>Cách đọc</span>
        <input
          aria-invalid={half && !hasReading}
          className={inputBorder(half && !hasReading)}
          id={readingId}
          maxLength={200}
          onChange={(e) => onChange({ reading: e.target.value })}
          placeholder="Ví dụ: ký túc xá"
          value={row.reading}
        />
      </label>
      <div className="dictionary-row-actions">
        <button
          aria-label="Phân biệt hoa/thường"
          aria-pressed={row.match_case}
          className={`rounded-lg border px-1.5 py-1 font-mono ${row.match_case ? "border-brand-500 bg-brand-500/10 text-brand-700 dark:text-brand-300" : "border-border text-muted-foreground"}`}
          onClick={() => onChange({ match_case: !row.match_case })}
          title={
            row.match_case
              ? "Chỉ khớp đúng kiểu viết hoa/thường"
              : "Khớp mọi kiểu viết hoa/thường"
          }
          type="button"
        >
          <span aria-hidden="true">Aa</span>
          <span className="dictionary-case-label">Hoa/thường</span>
        </button>
        <button
          aria-label={`Nghe thử ${row.word}`}
          className="rounded-lg p-1 text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-40"
          disabled={!hasReading || playDisabled}
          onClick={onPlay}
          title="Nghe thử cách đọc"
          type="button"
        >
          {playing ? (
            <RefreshCw className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Volume2 className="h-3.5 w-3.5" />
          )}
        </button>
        <button
          aria-label={`Xoá ${row.word}`}
          className="rounded-lg p-1 text-muted-foreground hover:bg-rose-500/10 hover:text-rose-500"
          onClick={onRemove}
          type="button"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

type Tone = "info" | "success" | "error";

const NOTICE_STYLE: Record<Tone, string> = {
  info: "border-border bg-muted/50 text-muted-foreground",
  success:
    "border-brand-500/40 bg-brand-500/10 text-brand-700 dark:text-brand-300",
  error: "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300",
};

function Notice({ text, tone }: { text: string; tone: Tone }) {
  const Icon = { info: Info, success: CheckCircle2, error: AlertCircle }[tone];
  return (
    <div
      aria-live={tone === "error" ? "assertive" : "polite"}
      className={`fade-in-50 flex shrink-0 animate-in items-start gap-2 rounded-xl border px-3 py-2 font-medium text-[13px] ${NOTICE_STYLE[tone]}`}
      role={tone === "error" ? "alert" : "status"}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{text}</span>
    </div>
  );
}

/** Nạp CSV vào bản nháp; lỗi thì trả lại nguyên `current` kèm lý do. */
function importCsv(
  current: Row[],
  text: string,
  filename: string
): { message: string; rows: Row[]; tone: Tone } {
  const { entries: imported, skipped } = parseDictionaryCsv(text);
  if (imported.length === 0) {
    return {
      rows: current,
      message: `Không có mục hợp lệ trong ${filename}. Xem "File mẫu" để biết cách điền.`,
      tone: "error",
    };
  }
  const result = mergeRows(current, imported);
  if (toEntries(result.rows).length > MAX_ENTRIES) {
    return {
      rows: current,
      message: `Từ điển tối đa ${MAX_ENTRIES} mục, file này vượt quá.`,
      tone: "error",
    };
  }
  return {
    rows: result.rows,
    message: importSummary(result.added, result.updated, skipped),
    // "info": thông báo "success" bị ẩn khi còn thay đổi chưa lưu, mà nhập xong luôn chưa lưu.
    tone: "info",
  };
}

interface DictionaryCsvToolsProps {
  disabled: boolean;
  entries: PronunciationEntry[];
  onImport: (text: string, filename: string) => void;
  onNotify: (text: string, tone: Tone) => void;
}

/** Nhập/xuất từ điển dạng CSV (soạn bằng Excel) và tải file mẫu. */
function DictionaryCsvTools({
  disabled,
  entries,
  onImport,
  onNotify,
}: DictionaryCsvToolsProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  const handleFile = async (file: File | undefined) => {
    if (inputRef.current) {
      inputRef.current.value = "";
    }
    if (!file) {
      return;
    }
    try {
      onImport(await readTextFile(file), file.name);
    } catch (e) {
      onNotify(`Không đọc được file: ${errorText(e)}`, "error");
    }
  };

  const handleExport = async () => {
    const done = await downloadBlobAsFile(
      csvBlob(dictionaryToCsv(entries)),
      "tu-dien-phat-am.csv"
    );
    if (done) {
      onNotify(`Đã xuất ${entries.length} mục ra file CSV.`, "success");
    }
  };

  return (
    <div className="dictionary-io">
      <input
        accept=".csv,text/csv"
        className="hidden"
        onChange={(e) => handleFile(e.target.files?.[0])}
        ref={inputRef}
        type="file"
      />
      <button
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        title="Nạp từ điển từ file CSV (Excel). Từ đã có sẽ được cập nhật."
        type="button"
      >
        <FileUp size={15} /> Nhập CSV
      </button>
      <button
        disabled={disabled || entries.length === 0}
        onClick={handleExport}
        title="Lưu danh sách từ ra file CSV để sửa trong Excel hoặc chuyển sang máy khác"
        type="button"
      >
        <FileDown size={15} /> Xuất CSV
      </button>
      <button
        onClick={() =>
          downloadBlobAsFile(
            csvBlob(toCsv(SAMPLE_DICTIONARY_ROWS)),
            "tu-dien-phat-am-mau.csv"
          )
        }
        title="Tải file CSV mẫu có sẵn vài từ để xem cách điền"
        type="button"
      >
        <Download size={15} /> File mẫu
      </button>
    </div>
  );
}

// Mỗi trang 20 dòng: danh sách dài (nhập từ CSV) vẫn dễ nhìn và không giật khi gõ.
const PAGE_SIZE = 20;

function filterRows(rows: Row[], filter: string): Row[] {
  const q = filter.trim().toLowerCase();
  if (!q) {
    return rows;
  }
  return rows.filter(
    (r) =>
      r.word.toLowerCase().includes(q) || r.reading.toLowerCase().includes(q)
  );
}

/** Cắt một trang; trang vượt quá (vừa xoá dòng cuối) thì lùi về trang cuối. */
function pageOf(list: Row[], page: number) {
  const pages = Math.max(1, Math.ceil(list.length / PAGE_SIZE));
  const current = Math.min(page, pages - 1);
  const from = current * PAGE_SIZE;
  return {
    current,
    from,
    items: list.slice(from, from + PAGE_SIZE),
    pages,
  };
}

function listHint(
  matched: number,
  total: number,
  shown: { from: number; items: Row[] }
): string {
  if (matched > PAGE_SIZE) {
    return `Hiển thị ${shown.from + 1}–${shown.from + shown.items.length} / ${matched} mục`;
  }
  return `Hiển thị ${matched}/${total} mục`;
}

interface PagerProps {
  current: number;
  onChange: (page: number) => void;
  pages: number;
}

function DictionaryPager({ current, pages, onChange }: PagerProps) {
  if (pages <= 1) {
    return null;
  }
  return (
    <nav aria-label="Phân trang từ điển" className="dictionary-pager">
      <button
        aria-label="Trang trước"
        disabled={current === 0}
        onClick={() => onChange(current - 1)}
        type="button"
      >
        <ChevronLeft size={16} />
      </button>
      {Array.from({ length: pages }, (_, i) => i)
        .filter((i) => i === 0 || i === pages - 1 || Math.abs(i - current) <= 1)
        .map((i, idx, shown) => (
          <span className="dictionary-pager-item" key={i}>
            {idx > 0 && i - shown[idx - 1] > 1 && (
              <span aria-hidden="true" className="dictionary-pager-gap">
                …
              </span>
            )}
            <button
              aria-current={i === current ? "page" : undefined}
              onClick={() => onChange(i)}
              type="button"
            >
              {i + 1}
            </button>
          </span>
        ))}
      <button
        aria-label="Trang sau"
        disabled={current === pages - 1}
        onClick={() => onChange(current + 1)}
        type="button"
      >
        <ChevronRight size={16} />
      </button>
    </nav>
  );
}

function closeDictionary(dirty: boolean, ready: boolean, onClose: () => void) {
  if (
    dirty &&
    ready &&
    // biome-ignore lint/suspicious/noAlert: Giữ xác nhận bỏ thay đổi hiện có.
    !window.confirm("Từ điển có thay đổi chưa lưu. Đóng và bỏ thay đổi?")
  ) {
    return;
  }
  onClose();
}

function handleDictionaryKey(
  event: KeyboardEvent,
  dialog: HTMLElement,
  onClose: () => void
) {
  if (event.key === "Escape") {
    event.stopPropagation();
    onClose();
  }
  if (event.key !== "Tab") {
    return;
  }
  const elements = Array.from(
    dialog.querySelectorAll<HTMLElement>(
      "button:not(:disabled), input:not(:disabled), textarea:not(:disabled), summary"
    )
  ).filter((element) => element.getClientRects().length > 0);
  const first = elements[0];
  const last = elements.pop();
  if (!dialog.contains(document.activeElement)) {
    event.preventDefault();
    first?.focus();
    return;
  }
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last?.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first?.focus();
  }
}

const SAVED_FLASH_MS = 2500;

const SAMPLE_TEXT = "Học sinh nhận SGK tại KTX.";
const SAMPLE_MAX = 500;

interface DictionaryPreviewProps {
  filePath: string;
  onPlay: () => void;
  onSampleChange: (value: string) => void;
  playing: string | null;
  preview: string;
  ready: boolean;
  sample: string;
  sampleId: string;
}
function DictionaryPreview({
  ready,
  sample,
  sampleId,
  preview,
  playing,
  filePath,
  onSampleChange,
  onPlay,
}: DictionaryPreviewProps) {
  return (
    <aside aria-label="Thử cách đọc và hướng dẫn" className="dictionary-aside">
      <div className="dictionary-aside-title">
        <Volume2 size={18} />
        <h3>Thử cách đọc</h3>
      </div>
      <p className="dictionary-help">
        Xem trước theo các thay đổi đang nhập, chưa cần lưu.
      </p>
      {ready && (
        <div className="dictionary-preview-card">
          <label
            className="block font-semibold text-foreground/90"
            htmlFor={sampleId}
          >
            Văn bản thử nghiệm
          </label>
          <textarea
            className="w-full resize-none rounded-lg border border-border bg-background/60 px-2 py-1.5 outline-none focus:border-brand-500"
            id={sampleId}
            maxLength={SAMPLE_MAX}
            onChange={(e) => onSampleChange(e.target.value)}
            rows={4}
            value={sample}
          />
          <div className="dictionary-preview-result">
            <p className="min-w-0 flex-1 text-muted-foreground">
              Kết quả thay từ:{" "}
              <span className="text-foreground">
                {preview ||
                  (sample.trim() ? "Đang cập nhật..." : "Nhập văn bản để thử.")}
              </span>
            </p>
            <button
              className="flex shrink-0 items-center gap-1 rounded-lg border border-border bg-secondary px-2 py-1 font-medium hover:bg-secondary/80 disabled:opacity-40"
              disabled={!preview || preview.startsWith("⚠️") || playing !== null}
              onClick={onPlay}
              type="button"
            >
              {playing === "sample" ? (
                <RefreshCw className="h-3 w-3 animate-spin" />
              ) : (
                <Volume2 className="h-3 w-3" />
              )}
              Nghe thử
            </button>
          </div>
        </div>
      )}
      <div className="dictionary-guide">
        <h4>Cách dùng từ điển</h4>
        <p>
          <strong>KTX → ký túc xá</strong>
          <br />
          Giúp ứng dụng đọc đúng nghĩa thay vì đánh vần.
        </p>
        <p>
          <strong>Chỉ thay nguyên từ</strong>
          <br />
          Từ bên trong một từ dài hơn sẽ không bị thay.
        </p>
        <p>
          <strong>Phân biệt hoa/thường (Aa)</strong>
          <br />
          Bật: chỉ khớp đúng kiểu chữ, ví dụ “AI” khác “ai”. Tắt: khớp mọi kiểu
          viết hoa/thường.
        </p>
        <p>
          <strong>Nhập/xuất file CSV</strong>
          <br />
          Soạn nhiều từ trong Excel: tải "File mẫu", mỗi dòng một từ (Từ gốc,
          Cách đọc, Phân biệt hoa thường: có/không), lưu dạng CSV rồi bấm "Nhập
          CSV". Từ đã có sẽ được cập nhật.
        </p>
        <p>Sau khi lưu, từ điển áp dụng cho lần tạo giọng tiếp theo.</p>
      </div>
      {filePath && (
        <details className="dictionary-file">
          <summary>Vị trí lưu từ điển</summary>
          <p>
            <code>{filePath}</code>
          </p>
          <p>Có thể sửa tệp trực tiếp. Ứng dụng tự đọc lại thay đổi.</p>
        </details>
      )}
    </aside>
  );
}

export const PronunciationDictionaryModal: React.FC<
  PronunciationDictionaryModalProps
> = ({ apiUrl, isOpen, onClose }) => {
  const [rows, setRows] = useState<Row[]>([]);
  const [saved, setSaved] = useState<string>("[]");
  const [defaults, setDefaults] = useState<PronunciationEntry[]>([]);
  const [filePath, setFilePath] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "saving" | "error">(
    "loading"
  );
  const [message, setMessage] = useState("");
  const [tone, setTone] = useState<Tone>("info");
  const [justSaved, setJustSaved] = useState(false);
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(0);
  const [sample, setSample] = useState(SAMPLE_TEXT);
  const [preview, setPreview] = useState("");
  const [playing, setPlaying] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const sampleId = useId();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);

  // Mỗi lần mở đều tải lại để nhận các thay đổi sửa trực tiếp trong tệp.
  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const controller = new AbortController();
    setStatus("loading");
    setMessage("");
    setFilter("");
    setPage(0);
    setSample(SAMPLE_TEXT);
    fetchPronunciations(apiUrl, controller.signal)
      .then((res) => {
        if (controller.signal.aborted) {
          return;
        }
        setRows(toRows(res.entries));
        setSaved(JSON.stringify(res.entries));
        setDefaults(res.defaults ?? []);
        setFilePath(res.path);
        setStatus("idle");
      })
      .catch(() => {
        if (controller.signal.aborted) {
          return;
        }
        setStatus("error");
        setTone("error");
        setMessage(
          "Không đọc được từ điển phát âm. Hãy kiểm tra kết nối tới server."
        );
      });
    return () => controller.abort();
  }, [apiUrl, isOpen]);

  // Dừng âm thanh khi đóng hộp thoại.
  useEffect(() => {
    if (!isOpen) {
      audioRef.current?.pause();
      setPlaying(null);
    }
  }, [isOpen]);

  const entries = useMemo(() => toEntries(rows), [rows]);
  const incomplete = rows.some(
    (r) => Boolean(r.word.trim()) !== Boolean(r.reading.trim())
  );
  // Dòng chưa điền đủ vẫn tính là thay đổi để nút lưu báo lỗi rõ ràng.
  const dirty = incomplete || JSON.stringify(entries) !== saved;
  const ready = status === "idle" || status === "saving";

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const previous = document.activeElement;
    closeRef.current?.focus();
    return () => {
      if (previous instanceof HTMLElement) {
        previous.focus();
      }
    };
  }, [isOpen]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!(isOpen && dialog)) {
      return;
    }
    const handleKey = (event: KeyboardEvent) =>
      handleDictionaryKey(event, dialog, () =>
        closeDictionary(dirty, ready, onClose)
      );
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [isOpen, dirty, ready, onClose]);

  // Xem trước theo bản nháp chưa lưu.
  useEffect(() => {
    setPreview("");
    if (!(isOpen && ready)) {
      return;
    }
    const controller = new AbortController();
    const t = setTimeout(() => {
      previewPronunciations(apiUrl, sample, entries, controller.signal)
        .then((text) => {
          if (!controller.signal.aborted) {
            setPreview(text);
          }
        })
        .catch((e) => {
          if (!controller.signal.aborted) {
            setPreview(`⚠️ ${errorText(e)}`);
          }
        });
    }, 300);
    return () => {
      clearTimeout(t);
      controller.abort();
    };
  }, [apiUrl, entries, isOpen, ready, sample]);

  // Nút lưu hiển thị trạng thái thành công trong vài giây.
  useEffect(() => {
    if (!justSaved) {
      return;
    }
    const t = setTimeout(() => setJustSaved(false), SAVED_FLASH_MS);
    return () => clearTimeout(t);
  }, [justSaved]);

  if (!isOpen) {
    return null;
  }

  const updateRow = (id: number, patch: Partial<PronunciationEntry>) =>
    setRows((rs) => rs.map((r) => (r.id === id ? { ...r, ...patch } : r)));

  const addRow = () => {
    setFilter("");
    setPage(0);
    setRows((rs) => [
      { id: nextId++, word: "", reading: "", match_case: true },
      ...rs,
    ]);
    // Dòng mới nằm đầu danh sách để người dùng thấy ngay.
    listRef.current?.scrollTo({ top: 0 });
    requestAnimationFrame(() => {
      listRef.current?.querySelector<HTMLInputElement>("input")?.focus();
    });
  };

  const handleClose = () => closeDictionary(dirty, ready, onClose);

  const notify = (text: string, t: Tone = "info") => {
    setMessage(text);
    setTone(t);
  };

  const handleSave = async () => {
    if (incomplete) {
      notify(
        "Có dòng còn thiếu từ hoặc cách đọc. Hãy điền đủ hoặc xoá dòng đó.",
        "error"
      );
      return;
    }
    setStatus("saving");
    notify("Đang lưu từ điển...");
    try {
      const res = await savePronunciations(apiUrl, entries);
      setRows(toRows(res.entries));
      setSaved(JSON.stringify(res.entries));
      notify(
        `Đã lưu ${res.entries.length} mục. Áp dụng ngay cho lần đọc tiếp theo.`,
        "success"
      );
      setJustSaved(true);
    } catch (e) {
      notify(`Không lưu được: ${errorText(e)}`, "error");
    } finally {
      setStatus("idle");
    }
  };
  const play = async (key: string, text: string) => {
    audioRef.current?.pause();
    setPlaying(key);
    try {
      const res = await synthesizeSpeech(apiUrl, {
        text,
        usePronunciationDict: false,
      });
      const url = URL.createObjectURL(res.blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => {
        URL.revokeObjectURL(url);
        setPlaying(null);
      };
      await audio.play();
    } catch (e) {
      setPlaying(null);
      notify(`Không nghe thử được: ${errorText(e)}`, "error");
    }
  };

  const visible = filterRows(rows, filter);
  const shown = pageOf(visible, page);
  const goToPage = (p: number) => {
    setPage(p);
    listRef.current?.scrollTo({ top: 0 });
  };
  const saving = status === "saving";
  // Đang tải hoặc đang lưu: khoá các thao tác sửa danh sách.
  const locked = !ready || saving;
  const showSaved = justSaved && !dirty;
  let saveLabel: React.ReactNode = "Lưu từ điển";
  if (saving) {
    saveLabel = "Đang lưu...";
  } else if (showSaved) {
    saveLabel = (
      <span className="flex items-center gap-1">
        <CheckCircle2 className="h-3.5 w-3.5" /> Đã lưu
      </span>
    );
  }

  return (
    <div
      aria-labelledby={titleId}
      aria-modal="true"
      className="settings-overlay fixed inset-0 z-[60]"
      ref={dialogRef}
      role="dialog"
    >
      <div className="settings-dialog dictionary-dialog">
        <header className="settings-header">
          <div className="flex items-center gap-3">
            <span className="settings-header-icon">
              <BookOpen size={22} />
            </span>
            <div>
              <h2 id={titleId}>Từ điển phát âm</h2>
              <p>Tuỳ chỉnh cách đọc từ viết tắt, tên riêng và thuật ngữ</p>
            </div>
          </div>
          <button
            aria-label="Đóng từ điển"
            className="studio-icon-button"
            onClick={handleClose}
            ref={closeRef}
            type="button"
          >
            <X size={20} />
          </button>
        </header>
        <div className="dictionary-body">
          <section aria-label="Danh sách từ" className="dictionary-editor">
            <div className="dictionary-toolbar">
              <div>
                <h3>
                  Danh sách từ{" "}
                  <span className="dictionary-count">{entries.length}</span>
                </h3>
                <p>Nhập cách đọc bằng chữ tiếng Việt.</p>
              </div>
              <div className="dictionary-toolbar-actions">
                <DictionaryCsvTools
                  disabled={locked}
                  entries={entries}
                  onImport={(text, filename) => {
                    const result = importCsv(rows, text, filename);
                    setFilter("");
                    setPage(0);
                    setRows(result.rows);
                    notify(result.message, result.tone);
                  }}
                  onNotify={notify}
                />
                <button
                  className="studio-primary dictionary-add"
                  disabled={locked}
                  onClick={addRow}
                  type="button"
                >
                  <Plus size={16} /> Thêm từ
                </button>
              </div>
            </div>
            <label className="dictionary-search">
              <Search aria-hidden="true" size={17} />
              <input
                aria-label="Tìm trong từ điển"
                disabled={!ready}
                onChange={(e) => {
                  setFilter(e.target.value);
                  setPage(0);
                }}
                placeholder="Tìm từ gốc hoặc cách đọc..."
                type="search"
                value={filter}
              />
            </label>
            {ready && (
              <p className="dictionary-list-hint">
                {listHint(visible.length, rows.length, shown)} · Bật Aa để phân
                biệt hoa/thường.
              </p>
            )}
            {status === "loading" && (
              <div className="dictionary-empty" role="status">
                <RefreshCw className="animate-spin" size={22} />
                Đang tải từ điển...
              </div>
            )}
            {ready && (
              <div className="dictionary-list" ref={listRef}>
                {visible.length === 0 && (
                  <p className="dictionary-empty">
                    {rows.length
                      ? "Không có mục nào khớp."
                      : "Từ điển trống - app đọc theo mặc định."}
                  </p>
                )}
                {shown.items.map((r) => (
                  <DictRow
                    key={r.id}
                    onChange={(patch) => updateRow(r.id, patch)}
                    onPlay={() => play(`row-${r.id}`, r.reading)}
                    onRemove={() =>
                      setRows((rs) => rs.filter((x) => x.id !== r.id))
                    }
                    playDisabled={playing !== null}
                    playing={playing === `row-${r.id}`}
                    row={r}
                  />
                ))}
              </div>
            )}
            {ready && (
              <DictionaryPager
                current={shown.current}
                onChange={goToPage}
                pages={shown.pages}
              />
            )}
            {message && !(tone === "success" && dirty) && (
              <Notice text={message} tone={tone} />
            )}
          </section>
          <DictionaryPreview
            filePath={filePath}
            onPlay={() => play("sample", preview)}
            onSampleChange={setSample}
            playing={playing}
            preview={preview}
            ready={ready}
            sample={sample}
            sampleId={sampleId}
          />
        </div>
        <footer className="settings-footer dictionary-footer">
          <div aria-live="polite" className="dictionary-footer-status">
            <span
              className={dirty ? "dictionary-unsaved" : "text-muted-foreground"}
            >
              {dirty && ready
                ? "Có thay đổi chưa lưu"
                : "Thay đổi có hiệu lực sau khi lưu"}
            </span>
            <button
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-border bg-card px-3 py-1.5 font-medium text-foreground shadow-sm transition-colors hover:bg-secondary focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-40"
              disabled={locked || defaults.length === 0}
              onClick={() => {
                setRows(toRows(defaults));
                notify('Đã nạp bộ mặc định. Bấm "Lưu từ điển" để áp dụng.');
              }}
              type="button"
            >
              <RotateCcw aria-hidden="true" size={14} />
              Khôi phục mặc định
            </button>
          </div>
          <div className="flex gap-2">
            <button
              className="rounded-xl border border-border px-4 py-1.5 text-muted-foreground transition-all hover:bg-secondary hover:text-foreground"
              onClick={handleClose}
              type="button"
            >
              Đóng
            </button>
            <button
              className="studio-primary rounded-xl px-4 py-1.5 font-medium shadow-sm transition-all active:scale-95 disabled:opacity-50"
              disabled={locked || !dirty}
              onClick={handleSave}
              type="button"
            >
              {saveLabel}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
};

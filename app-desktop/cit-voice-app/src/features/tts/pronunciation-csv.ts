import type { PronunciationEntry } from "./api";

// Giới hạn khớp vieneu_utils/pronunciation.py - quá thì server từ chối cả lần lưu.
export const MAX_WORD_LEN = 64;
export const MAX_READING_LEN = 200;
export const MAX_ENTRIES = 2000;

const HEADER = ["Từ gốc", "Cách đọc", "Phân biệt hoa thường"];

// Cột thứ ba: bỏ trống = có phân biệt (giống nút "Thêm từ").
const YES = new Set(["có", "co", "c", "x", "1", "true", "yes", "y", "bật"]);
const NO = new Set(["không", "khong", "k", "0", "false", "no", "n", "tắt"]);

/** File mẫu: mỗi dòng minh hoạ một cách dùng; cột ba bỏ trống = "có". */
export const SAMPLE_DICTIONARY_ROWS: string[][] = [
  HEADER,
  ["KTX", "ký túc xá", "có"],
  ["SGK", "sách giáo khoa", "có"],
  ["AI", "ây ai", "có"],
  ["Facebook", "phây búc", "không"],
  ["UBND", "ủy ban nhân dân", ""],
];

// BOM viết bằng mã để không thành ký tự vô hình trong mã nguồn.
const BOM = String.fromCharCode(0xfe_ff);
const NEEDS_QUOTE = /[",\r\n;]/;
const QUOTE = /"/g;
const LINE_BREAK = /\r?\n/;
const SPACES = /\s+/g;

const escapeCell = (value: string) =>
  NEEDS_QUOTE.test(value) ? `"${value.replace(QUOTE, '""')}"` : value;

/** CSV có BOM + CRLF để Excel mở đúng tiếng Việt. */
export function toCsv(rows: string[][]): string {
  return `${BOM}${rows.map((r) => r.map(escapeCell).join(",")).join("\r\n")}\r\n`;
}

export function dictionaryToCsv(entries: PronunciationEntry[]): string {
  return toCsv([
    HEADER,
    ...entries.map((e) => [e.word, e.reading, e.match_case ? "có" : "không"]),
  ]);
}

/** Excel bản tiếng Việt/châu Âu lưu CSV bằng dấu chấm phẩy; đoán theo dòng đầu. */
function detectDelimiter(text: string): string {
  const firstLine = text.split(LINE_BREAK, 1)[0] ?? "";
  const count = (ch: string) => firstLine.split(ch).length - 1;
  const candidates = [",", ";", "\t"];
  return candidates.reduce((best, ch) => (count(ch) > count(best) ? ch : best));
}

/** Đọc ô bọc ngoặc kép bắt đầu sau dấu `"` ở vị trí `start`; "" là một dấu ". */
function readQuoted(
  src: string,
  start: number
): { end: number; value: string } {
  let value = "";
  let i = start;
  while (i < src.length) {
    if (src[i] !== '"') {
      value += src[i];
      i++;
    } else if (src[i + 1] === '"') {
      value += '"';
      i += 2;
    } else {
      return { value, end: i + 1 };
    }
  }
  return { value, end: i };
}

/** Tách CSV theo RFC 4180: ô bọc ngoặc kép được chứa dấu phân cách và xuống dòng. */
export function parseCsv(text: string): string[][] {
  const src = text.startsWith(BOM) ? text.slice(1) : text;
  const delimiter = detectDelimiter(src);
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let i = 0;
  while (i < src.length) {
    const ch = src[i];
    if (ch === '"' && cell === "") {
      const quoted = readQuoted(src, i + 1);
      cell = quoted.value;
      i = quoted.end;
      continue;
    }
    if (ch === delimiter) {
      row.push(cell);
      cell = "";
    } else if (ch === "\n" || ch === "\r") {
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
      i += ch === "\r" && src[i + 1] === "\n" ? 1 : 0;
    } else {
      cell += ch;
    }
    i++;
  }
  if (cell !== "" || row.length > 0) {
    row.push(cell);
    rows.push(row);
  }
  return rows;
}

const isHeader = (cells: string[]) => {
  const first = (cells[0] ?? "").trim().toLowerCase();
  return first === "từ gốc" || first === "tu goc" || first === "word";
};

export interface CsvImportResult {
  entries: PronunciationEntry[];
  /** Số dòng (đánh số như Excel) bị bỏ qua và lý do. */
  skipped: { line: number; reason: string }[];
}

/** Đọc từ điển từ CSV. Trùng từ trong cùng file thì dòng sau thắng. */
export function parseDictionaryCsv(text: string): CsvImportResult {
  const rows = parseCsv(text);
  const byWord = new Map<string, PronunciationEntry>();
  const skipped: CsvImportResult["skipped"] = [];
  rows.forEach((cells, index) => {
    const line = index + 1;
    if (index === 0 && isHeader(cells)) {
      return;
    }
    // Ô nhiều dòng trong Excel thành một dòng: ô nhập trong app chỉ có một dòng.
    const word = (cells[0] ?? "").replace(SPACES, " ").trim();
    const reading = (cells[1] ?? "").replace(SPACES, " ").trim();
    const flag = (cells[2] ?? "").trim().toLowerCase();
    if (!(word || reading)) {
      return; // dòng trống
    }
    if (!(word && reading)) {
      skipped.push({ line, reason: "thiếu từ gốc hoặc cách đọc" });
      return;
    }
    if (word.length > MAX_WORD_LEN) {
      skipped.push({ line, reason: `từ gốc dài quá ${MAX_WORD_LEN} ký tự` });
      return;
    }
    if (reading.length > MAX_READING_LEN) {
      skipped.push({
        line,
        reason: `cách đọc dài quá ${MAX_READING_LEN} ký tự`,
      });
      return;
    }
    if (flag && !YES.has(flag) && !NO.has(flag)) {
      skipped.push({
        line,
        reason: `cột "Phân biệt hoa thường" phải là "có" hoặc "không"`,
      });
      return;
    }
    byWord.set(word, { word, reading, match_case: !NO.has(flag) });
  });
  return { entries: [...byWord.values()], skipped };
}

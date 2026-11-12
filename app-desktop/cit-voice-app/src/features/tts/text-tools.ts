// Xử lý văn bản trong ô soạn thảo: chèn thẻ tại con trỏ, làm sạch ký hiệu
// markdown khi dán từ ChatGPT/Gemini… Hàm thuần, không đụng DOM.

export interface InsertResult {
  /** Vị trí con trỏ sau khi chèn (ngay sau thẻ và dấu cách theo sau). */
  caret: number;
  text: string;
}

const SPACE_RE = /\s/;

/**
 * Chèn `tag` vào [start, end) - thay vùng đang bôi đen nếu có. Tự thêm dấu cách
 * hai bên khi dính chữ, để "chào[cười]bạn" không thành một từ lạ.
 */
export function insertAtCursor(
  text: string,
  start: number,
  end: number,
  tag: string
): InsertResult {
  const from = Math.max(0, Math.min(start, text.length));
  const to = Math.max(from, Math.min(end, text.length));
  const before = text.slice(0, from);
  const after = text.slice(to);
  const lead = before && !SPACE_RE.test(before.slice(-1)) ? " " : "";
  const trail = after && SPACE_RE.test(after[0]) ? "" : " ";
  const inserted = `${lead}${tag}${trail}`;
  return {
    text: `${before}${inserted}${after}`,
    caret: before.length + inserted.length,
  };
}

const ENTITIES: Record<string, string> = {
  amp: "&",
  lt: "<",
  gt: ">",
  quot: '"',
  apos: "'",
  nbsp: " ",
  hellip: "…",
  ndash: "–",
  mdash: "\u2014",
};

const FENCE_RE = /^\s*(```|~~~).*$/gm;
const IMAGE_RE = /!\[([^\]]*)\]\([^)]*\)/g;
const LINK_RE = /\[([^\]]+)\]\((?:https?:\/\/|www\.|\/|#|mailto:)[^)]*\)/g;
const INLINE_CODE_RE = /`([^`\n]+)`/g;
const HEADING_RE = /^[ \t]{0,3}#{1,6}[ \t]+/gm;
const QUOTE_RE = /^[ \t]*(?:>[ \t]?)+/gm;
const BULLET_RE = /^([ \t]*)[*+•][ \t]+/gm;
const RULE_RE = /^[ \t]*([-*_])(?:[ \t]*\1){2,}[ \t]*$/gm;
const TABLE_SEPARATOR_RE =
  /^[ \t]*\|?[ \t]*:?-{3,}:?[ \t]*(?:\|[ \t]*:?-{3,}:?[ \t]*)*\|?[ \t]*$/gm;
const TABLE_ROW_RE = /^[ \t]*\|(.*)\|[ \t]*$/gm;
// Đậm/nghiêng: ký hiệu phải bám sát chữ (không có khoảng trắng ngay bên trong),
// để phép tính "5 * 3 * 2" không bị hiểu nhầm.
const BOLD_ITALIC_RE = /(\*{1,3}|_{1,3})(?=\S)([^\n]*?\S)\1(?![*_\w])/g;
const STRIKE_RE = /~~(?=\S)([^\n]*?\S)~~/g;
const LEFTOVER_STARS_RE = /\*{2,}|_{3,}/g;
const HTML_BREAK_RE = /<br\s*\/?>/gi;
const HTML_TAG_RE = /<\/?[a-zA-Z][^<>]*>/g;
const ENTITY_RE = /&(#x?[0-9a-fA-F]+|[a-zA-Z]+);/g;
const TRAILING_SPACE_RE = /[ \t]+$/gm;
const MANY_BLANK_LINES_RE = /\n{3,}/g;
const WORD_CHAR_RE = /\w/;

function decodeEntity(match: string, body: string): string {
  if (body.startsWith("#")) {
    const hex = body[1] === "x" || body[1] === "X";
    const code = Number.parseInt(body.slice(hex ? 2 : 1), hex ? 16 : 10);
    return Number.isFinite(code) && code > 0
      ? String.fromCodePoint(code)
      : match;
  }
  return ENTITIES[body.toLowerCase()] ?? match;
}

function unwrapEmphasis(text: string): string {
  // Lặp vài lần cho các lớp lồng nhau: ***_đậm nghiêng_***.
  let out = text;
  for (let i = 0; i < 3; i++) {
    const next = out.replace(
      BOLD_ITALIC_RE,
      (whole, mark: string, inner: string, offset: number, all: string) => {
        // Gạch dưới giữa một từ (ten_bien_x) không phải nghiêng.
        const prev = all[offset - 1];
        if (mark.startsWith("_") && prev && WORD_CHAR_RE.test(prev)) {
          return whole;
        }
        return inner;
      }
    );
    if (next === out) {
      break;
    }
    out = next;
  }
  return out;
}

/**
 * Bỏ ký hiệu markdown/HTML mà app sẽ đọc thành tiếng ("sao sao", "thăng",
 * "lớn hơn", đánh vần cả đường link), giữ nguyên chữ. Không đụng thẻ cảm xúc,
 * thẻ nghỉ ([cười], [nghỉ 1s]) và ký hiệu đứng rời như "5 * 3", "#1".
 */
export function cleanMarkdown(text: string): string {
  let out = text.replace(/\r\n?/g, "\n");
  out = out.replace(FENCE_RE, "");
  out = out.replace(IMAGE_RE, "$1");
  out = out.replace(LINK_RE, "$1");
  out = out.replace(INLINE_CODE_RE, "$1");
  out = out.replace(RULE_RE, "");
  out = out.replace(TABLE_SEPARATOR_RE, "");
  out = out.replace(TABLE_ROW_RE, (_m, cells: string) =>
    cells
      .split("|")
      .map((c) => c.trim())
      .filter(Boolean)
      .join(", ")
  );
  out = out.replace(HEADING_RE, "");
  out = out.replace(QUOTE_RE, "");
  out = out.replace(BULLET_RE, "$1");
  out = unwrapEmphasis(out);
  out = out.replace(STRIKE_RE, "$1");
  out = out.replace(LEFTOVER_STARS_RE, "");
  out = out.replace(HTML_BREAK_RE, "\n");
  out = out.replace(HTML_TAG_RE, "");
  out = out.replace(ENTITY_RE, decodeEntity);
  out = out.replace(TRAILING_SPACE_RE, "");
  out = out.replace(MANY_BLANK_LINES_RE, "\n\n");
  return out.trim();
}

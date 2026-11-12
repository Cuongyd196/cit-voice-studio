// Tach van ban "Tao hang loat" thanh tung muc theo moc [P1], [P2]...
//
// Moc phai dung DAU DONG; noi dung co the cung dong ("[P1] Xin chao") hoac cac
// dong ben duoi, keo dai toi moc ke tiep. Chi nhan dung dang [P<so>] nen khong
// dung toi the cam xuc [cuoi] hay the nghi [nghi 2s] trong noi dung.

export interface BatchItem {
  /** Nhan hien thi va dat ten file, vd "P1"; "Mở đầu" cho phan truoc moc dau tien. */
  label: string;
  text: string;
}

export interface BatchParseResult {
  /** So moc khong co noi dung (bi bo qua). */
  emptyMarkers: number;
  /** false = khong tim thay moc nao: ca van ban la MOT muc. */
  hasMarkers: boolean;
  items: BatchItem[];
}

const MARKER = /^[ \t]*\[\s*[Pp]\s*(\d{1,4})\s*\][ \t]*:?[ \t]*/;
const NEWLINES = /\r\n?/g;
export const PREAMBLE_LABEL = "Mở đầu";

export function parseBatchScript(input: string): BatchParseResult {
  const items: BatchItem[] = [];
  let emptyMarkers = 0;
  let hasMarkers = false;
  let label: string | null = null;
  let buffer: string[] = [];

  const flush = () => {
    const text = buffer.join("\n").trim();
    if (text) {
      items.push({ label: label ?? PREAMBLE_LABEL, text });
    } else if (label !== null) {
      emptyMarkers++;
    }
    buffer = [];
  };

  for (const line of input.replace(NEWLINES, "\n").split("\n")) {
    const m = MARKER.exec(line);
    if (m) {
      flush();
      hasMarkers = true;
      label = `P${Number(m[1])}`;
      buffer.push(line.slice(m[0].length));
    } else {
      buffer.push(line);
    }
  }
  flush();
  if (!hasMarkers && items.length === 1) {
    items[0].label = "P1";
  }
  return { emptyMarkers, hasMarkers, items };
}

/** Ten file cho muc thu `index` (tu 0): "001-P1.wav" - so thu tu giu dung thu tu khi mo zip. */
export function batchFileName(
  index: number,
  total: number,
  label: string,
  ext: string
): string {
  const width = Math.max(3, String(total).length);
  const safe = label.replace(/[\\/:*?"<>|\s]+/g, "-");
  return `${String(index + 1).padStart(width, "0")}-${safe}.${ext}`;
}

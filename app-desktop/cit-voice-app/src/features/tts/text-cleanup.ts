// Lam sach van ban trich tu PDF / Word truoc khi doc.
//
// Nguyen tac: chi xoa thu CHAC CHAN la rac trinh bay, khong dung toi noi dung.
// Ky hieu toan hoc ("1 + 1", "a - b", "- 5 do", "x * y") phai giu nguyen, nen:
// - ky hieu dau dong chi bi bo khi dung DAU DONG va theo sau la CHU CAI;
// - khong bao gio sua dau o giua dong;
// - "..." (ba cham, ngat giong) duoc giu, chi bo chuoi tu 4 cham tro len.

export interface CleanupStats {
  blankLines: number;
  bullets: number;
  joinedLines: number;
  placeholders: number;
}

export interface CleanupResult {
  stats: CleanupStats;
  text: string;
}

// Cho trong de dien trong bieu mau: "......", "……", "____".
const PLACEHOLDER = /\.{4,}|(?:…\s*){2,}|_{3,}/g;
// Ky hieu gach dau dong thuong: chi khi co dau cach va theo sau la chu cai.
const DASH_BULLET = /^[-*+–\u2014]\s+(?=\p{L})/u;
// Ky hieu chi dung lam dau dong (khong phai phep toan): khong can dau cach.
const SYMBOL_BULLET = /^[•▪◦●○■□➢►✓✔]\s*(?=\p{L})/u;
const SPACES = /[ \t ]+/g;
// Dong ket thuc bang dau cau / dong ngoac thi la het y, khong noi voi dong sau.
const LINE_END = /[.!?:;…"”')\]]$/;
const STARTS_LOWER = /^\p{Ll}/u;
const NEWLINES = /\r\n?/g;

interface Line {
  hadBullet: boolean;
  text: string;
}

export function cleanExtractedText(input: string): CleanupResult {
  const stats: CleanupStats = {
    blankLines: 0,
    bullets: 0,
    joinedLines: 0,
    placeholders: 0,
  };

  const lines: Line[] = [];
  for (const raw of input.replace(NEWLINES, "\n").split("\n")) {
    let text = raw.replace(PLACEHOLDER, () => {
      stats.placeholders++;
      return " ";
    });
    text = text.replace(SPACES, " ").trim();

    let hadBullet = false;
    const withoutBullet = text
      .replace(DASH_BULLET, "")
      .replace(SYMBOL_BULLET, "");
    if (withoutBullet !== text) {
      hadBullet = true;
      stats.bullets++;
      text = withoutBullet;
    }

    if (!text) {
      stats.blankLines++;
      continue;
    }
    lines.push({ hadBullet, text });
  }

  // Noi dong bi ngat giua cau (PDF ngat theo kho trang). Khong noi vao muc danh
  // sach: "- phong a" / "- phong b" la hai y rieng, noi lai se mat cho nghi.
  const out: string[] = [];
  for (const line of lines) {
    // biome-ignore lint/style/useAtIndex: tsconfig lib chua co Array.prototype.at
    const prev = out.length ? out[out.length - 1] : undefined;
    if (
      prev !== undefined &&
      !line.hadBullet &&
      !LINE_END.test(prev) &&
      STARTS_LOWER.test(line.text)
    ) {
      out[out.length - 1] = `${prev} ${line.text}`;
      stats.joinedLines++;
    } else {
      out.push(line.text);
    }
  }

  return { stats, text: out.join("\n") };
}

/** Cau bao ket qua cho nguoi dung; "" neu khong co gi thay doi. */
export function describeCleanup(stats: CleanupStats): string {
  const parts = [
    stats.blankLines && `${stats.blankLines} dòng trống`,
    stats.bullets && `${stats.bullets} gạch đầu dòng`,
    stats.placeholders && `${stats.placeholders} chỗ trống để điền`,
  ].filter(Boolean);
  const joined = stats.joinedLines
    ? `nối ${stats.joinedLines} dòng bị ngắt giữa câu`
    : "";
  if (parts.length === 0 && !joined) {
    return "";
  }
  const removed = parts.length ? `bỏ ${parts.join(", ")}` : "";
  return `Đã ${[removed, joined].filter(Boolean).join("; ")}.`;
}

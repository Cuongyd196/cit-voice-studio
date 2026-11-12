import type { VoiceOption } from "./types";

// Mo ta tu /voices co dang "Nam · Bac · Phong cach tin tuc · 48 kHz". Doc thang
// ra "Nam · Nam" (gioi tinh · vung) de gay nham, nen tach lai thanh
// "Nam, miền Bắc · Tin tức" cho o chon (<select> chi hien duoc chu thuan).

// Phan thu 3 la phong cach, ghi theo hai kieu: "Phong cách tin tức" hoac
// "Giọng đọc tự nhiên" (Ngoc Huyen, Adam).
const STYLE_PREFIX = /^(phong cách|giọng đọc)\s+/i;
const KHZ = /\bkHz\b/i;

export function voiceStyle(v: VoiceOption): string {
  const parts = (v.description ?? "").split("·").map((p) => p.trim());
  const part = parts.length >= 3 ? parts[2] : "";
  if (!part || KHZ.test(part)) {
    return "";
  }
  const style = part.replace(STYLE_PREFIX, "");
  return style.charAt(0).toUpperCase() + style.slice(1);
}

/** "Nam, miền Bắc · Tin tức" - rỗng khi không có thông tin. */
export function voiceDetail(v: VoiceOption): string {
  if (v.isCloned) {
    return "Giọng nhân bản";
  }
  const who: string[] = [];
  if (v.gender === "male") {
    who.push("Nam");
  } else if (v.gender === "female") {
    who.push("Nữ");
  }
  if (v.region === "North") {
    who.push("miền Bắc");
  } else if (v.region === "South") {
    who.push("miền Nam");
  } else if (v.region === "Central") {
    who.push("miền Trung");
  }
  const style = voiceStyle(v);
  return [who.join(", "), style].filter(Boolean).join(" · ");
}

export function voiceOptionLabel(v: VoiceOption): string {
  const detail = voiceDetail(v);
  return detail ? `${v.name} - ${detail}` : v.name;
}

export interface VoiceGroup {
  label: string;
  voices: VoiceOption[];
}

/** Nhom cho <optgroup>: Nữ, Nam, nhân bản, khác - bỏ nhóm rỗng, giữ thứ tự gốc trong nhóm. */
export function groupVoices(voices: VoiceOption[]): VoiceGroup[] {
  const groups: VoiceGroup[] = [
    { label: "Giọng nữ", voices: [] },
    { label: "Giọng nam", voices: [] },
    { label: "Giọng nhân bản", voices: [] },
    { label: "Khác", voices: [] },
  ];
  for (const v of voices) {
    if (v.isCloned) {
      groups[2].voices.push(v);
    } else if (v.gender === "female") {
      groups[0].voices.push(v);
    } else if (v.gender === "male") {
      groups[1].voices.push(v);
    } else {
      groups[3].voices.push(v);
    }
  }
  return groups.filter((g) => g.voices.length > 0);
}

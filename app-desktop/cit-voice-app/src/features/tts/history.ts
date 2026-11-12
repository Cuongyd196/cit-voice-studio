import type { HistoryApiEntry } from "./api";
import { notifySaved } from "./desktop-files";
import type { HistoryEntry } from "./types";

// Lich su luu tren o dia qua server (apps/history_store.py), KHONG o trinh duyet:
// ban desktop chay PyWebView private_mode nen localStorage/IndexedDB bi xoa moi
// lan tat app.

const MODES = new Set(["tts", "clone", "conversation", "pdf"]);
const TRAILING_SLASHES = /\/+$/;

export function fromServer(apiUrl: string, e: HistoryApiEntry): HistoryEntry {
  const base = apiUrl.replace(TRAILING_SLASHES, "");
  return {
    id: e.id,
    serverId: e.id,
    audioBlobUrl: `${base}${e.audio_url}`,
    durationSeconds: e.duration_seconds,
    format: e.format,
    mode: MODES.has(e.mode) ? (e.mode as HistoryEntry["mode"]) : "tts",
    subtitlesUrl: e.subtitles_url ? `${base}${e.subtitles_url}` : undefined,
    text: e.text,
    timestamp: e.timestamp,
    voiceId: e.voice_id,
    voiceName: e.voice_name,
  };
}

/**
 * Tai audio cua muc lich su da luu tren o dia ma KHONG nap vao trinh duyet: ban
 * desktop de Python chep/chuyen MP3 thang tu file; trinh duyet thi de no tu tai qua
 * URL. Ban ~2 gio (~690 MB) di qua blob/base64 se vuot gioi han bo nho cua trinh duyet.
 */
export async function downloadHistoryAudio(
  apiUrl: string,
  entryId: string,
  filename: string,
  fmt: "wav" | "mp3"
): Promise<boolean> {
  // biome-ignore lint/suspicious/noExplicitAny: cau noi PyWebView khong co kieu
  const pywebview = (window as any).pywebview;
  if (typeof pywebview?.api?.save_history_audio === "function") {
    const res = await pywebview.api.save_history_audio(entryId, filename, fmt);
    if (res?.cancelled) {
      return false;
    }
    if (res?.success) {
      notifySaved(res);
      return true;
    }
    throw new Error(res?.error || "Không lưu được file.");
  }
  const base = apiUrl.replace(TRAILING_SLASHES, "");
  const id = encodeURIComponent(entryId);
  const link = document.createElement("a");
  link.href =
    fmt === "mp3"
      ? `${base}/api/history/${id}/mp3`
      : `${base}/api/history/${id}/audio?download=true`;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  return true;
}

/** Audio cua muc lich su: dung blob co san, hoac tai tu server (muc nap tu o dia). */
export async function entryBlob(entry: HistoryEntry): Promise<Blob> {
  if (entry.audioBlob) {
    return entry.audioBlob;
  }
  const response = await fetch(entry.audioBlobUrl);
  if (!response.ok) {
    throw new Error("Không tải được audio của bản này.");
  }
  return response.blob();
}

/** Noi dung SRT cua muc lich su, hoac null neu muc khong co phu de. */
export async function entrySubtitles(
  entry: HistoryEntry
): Promise<string | null> {
  if (entry.subtitles) {
    return entry.subtitles;
  }
  if (!entry.subtitlesUrl) {
    return null;
  }
  const response = await fetch(entry.subtitlesUrl);
  return response.ok ? response.text() : null;
}

export function hasSubtitles(entry: HistoryEntry): boolean {
  return Boolean(entry.subtitles || entry.subtitlesUrl);
}

/** Ten file tai ve thong nhat cho audio va phu de cua cung mot muc. */
export function entryFileBase(entry: HistoryEntry): string {
  return `cit_tts_${entry.voiceName || "voice"}_${entry.timestamp}`;
}

export function srtBlob(srt: string): Blob {
  // BOM UTF-8: mot so trinh phat / phan mem dung video cu doc sai dau tieng Viet neu thieu.
  return new Blob([`﻿${srt}`], { type: "application/x-subrip;charset=utf-8" });
}

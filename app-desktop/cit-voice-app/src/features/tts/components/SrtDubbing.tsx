import {
  AlertCircle,
  Captions,
  CheckCircle2,
  Clapperboard,
  Download,
  Loader2,
  Mic,
  Square,
  X,
} from "lucide-react";
import type React from "react";
import { useEffect, useRef, useState } from "react";
import { type DubStats, dubSrtToHistory, type SrtCue } from "../api";
import { downloadBlobAsFile } from "../audio-engine";
import { downloadHistoryAudio, fromServer, srtBlob } from "../history";
import { LanguageSelect } from "../model-caps";
import type { HistoryEntry, VoiceOption } from "../types";
import { groupVoices, voiceOptionLabel } from "../voice-label";

interface SrtDubbingProps {
  apiUrl: string;
  cues: SrtCue[];
  defaultVoiceId: string;
  durationSeconds: number;
  fileName: string;
  onAddHistory: (entry: HistoryEntry) => void;
  onClose: () => void;
  srt: string;
  voices: VoiceOption[];
}

interface DubResult {
  entryId: string;
  srt: string | null;
  stats: DubStats;
}

const EXTENSION = /\.[^.]+$/;

function clock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const p = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${p(m)}:${p(s % 60)}` : `${p(m)}:${p(s % 60)}`;
}

function describeStats(stats: DubStats): string {
  const parts = [`Đã lồng tiếng ${stats.cues} câu`];
  if (stats.sped_up > 0) {
    parts.push(`${stats.sped_up} câu được đọc nhanh hơn cho vừa mốc`);
  }
  if (stats.pushed > 0) {
    parts.push(
      `${stats.pushed} câu bị lùi mốc (tối đa ${stats.max_push_seconds.toLocaleString("vi-VN")} giây) - tải phụ đề đã chỉnh để khớp`
    );
  }
  return `${parts.join(", ")}.`;
}

const errorText = (e: unknown) => (e instanceof Error ? e.message : String(e));

export const SrtDubbing: React.FC<SrtDubbingProps> = ({
  apiUrl,
  cues,
  defaultVoiceId,
  durationSeconds,
  fileName,
  onAddHistory,
  onClose,
  srt,
  voices,
}) => {
  const [voiceId, setVoiceId] = useState(defaultVoiceId);
  const [speed, setSpeed] = useState(1.0);
  const [running, setRunning] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DubResult | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const baseName = fileName.replace(EXTENSION, "");

  useEffect(() => {
    if (!voiceId && voices.length > 0) {
      setVoiceId(voices[0].id);
    }
  }, [voiceId, voices]);

  useEffect(() => {
    if (!running) {
      return;
    }
    const started = Date.now();
    const timer = window.setInterval(
      () => setElapsed((Date.now() - started) / 1000),
      500
    );
    return () => window.clearInterval(timer);
  }, [running]);

  // Thoat tab/component thi huy request de server dung doc.
  useEffect(() => () => abortRef.current?.abort(), []);

  const handleDub = async () => {
    const controller = new AbortController();
    abortRef.current = controller;
    setRunning(true);
    setElapsed(0);
    setError(null);
    setResult(null);
    try {
      const voice = voices.find((v) => v.id === voiceId);
      const res = await dubSrtToHistory(
        apiUrl,
        { srt, voiceId, voiceName: voice?.name ?? voiceId, speed },
        controller.signal
      );
      setResult({ entryId: res.entry.id, srt: res.srt, stats: res.stats });
      onAddHistory(fromServer(apiUrl, res.entry));
    } catch (e) {
      if (!controller.signal.aborted) {
        setError(errorText(e));
      }
    } finally {
      abortRef.current = null;
      setRunning(false);
    }
  };

  const handleDownload = async (fmt: "wav" | "mp3") => {
    if (!result) {
      return;
    }
    try {
      await downloadHistoryAudio(
        apiUrl,
        result.entryId,
        `${baseName}_long-tieng.${fmt}`,
        fmt
      );
    } catch (e) {
      setError(errorText(e));
    }
  };

  const handleDownloadSrt = async () => {
    if (result?.srt) {
      await downloadBlobAsFile(
        srtBlob(result.srt),
        `${baseName}_long-tieng.srt`
      );
    }
  };

  return (
    <div className="fade-in-50 grid animate-in grid-cols-1 gap-6 duration-300 lg:grid-cols-12">
      <div className="space-y-4 lg:col-span-5">
        <div className="space-y-4 rounded-[14px] border border-border bg-card p-5 shadow-sm">
          <div className="flex items-center gap-2 border-border/60 border-b pb-3">
            <Clapperboard className="h-5 w-5 text-brand-500" />
            <h3 className="flex-1 font-bold text-foreground text-sm">
              Lồng tiếng theo phụ đề
            </h3>
            <button
              className="flex items-center gap-1 rounded-lg px-2 py-1 text-muted-foreground text-xs hover:bg-secondary/80 hover:text-foreground disabled:opacity-40"
              disabled={running}
              onClick={onClose}
              title="Chọn file khác"
              type="button"
            >
              <X className="h-3.5 w-3.5" />
              <span>Chọn file khác</span>
            </button>
          </div>

          <div className="doc-file">
            <Captions aria-hidden="true" size={20} />
            <div className="min-w-0">
              <p className="truncate font-semibold">{fileName}</p>
              <p className="text-muted-foreground">
                {cues.length} câu · dài {clock(durationSeconds)}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <LanguageSelect className="col-span-2" disabled={running} />
            <label className="col-span-2 space-y-1">
              <span className="font-semibold text-foreground/90">
                Giọng đọc
              </span>
              <select
                className="w-full rounded-lg border border-border/80 bg-background px-2.5 py-1.5 outline-none focus:border-brand-500"
                disabled={running}
                onChange={(e) => setVoiceId(e.target.value)}
                value={voiceId}
              >
                {groupVoices(voices).map((g) => (
                  <optgroup key={g.label} label={g.label}>
                    {g.voices.map((v) => (
                      <option key={v.id} value={v.id}>
                        {voiceOptionLabel(v)}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </label>
            <label className="col-span-2 space-y-1">
              <span className="font-semibold text-foreground/90">
                Tốc độ đọc: {speed.toFixed(2)}x
              </span>
              <input
                className="w-full accent-brand-500"
                disabled={running}
                max={1.3}
                min={0.8}
                onChange={(e) => setSpeed(Number(e.target.value))}
                step={0.05}
                type="range"
                value={speed}
              />
            </label>
          </div>

          <p className="text-[12px] text-muted-foreground leading-relaxed">
            Mỗi câu được đặt đúng mốc phụ đề. Câu dài hơn khung sẽ được đọc
            nhanh hơn (tối đa 1,5 lần); vẫn chưa vừa thì lấn sang khoảng lặng
            hoặc đẩy câu sau lùi lại, không cắt chữ.
          </p>

          {running ? (
            <button
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-2.5 font-semibold text-rose-600 text-xs transition-all hover:bg-rose-500/20 dark:text-rose-400"
              onClick={() => abortRef.current?.abort()}
              type="button"
            >
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Đang lồng tiếng… {clock(elapsed)} - bấm để dừng</span>
              <Square className="h-3.5 w-3.5" />
            </button>
          ) : (
            <button
              className="studio-primary flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-brand-500 to-teal-600 px-4 py-2.5 font-semibold text-white text-xs shadow-brand-500/20 shadow-md transition-all hover:from-brand-600 hover:to-teal-700 active:scale-95 disabled:opacity-50"
              disabled={!voiceId}
              onClick={handleDub}
              type="button"
            >
              <Mic className="h-4 w-4" />
              <span>Lồng tiếng</span>
            </button>
          )}

          {error && (
            <div className="flex items-center gap-2 rounded-xl border border-rose-500/20 bg-rose-500/10 p-3 text-rose-600 text-xs dark:text-rose-400">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {result && (
            <div className="space-y-2 rounded-xl border border-brand-500/40 bg-brand-500/10 p-3 text-xs">
              <div className="flex items-start gap-2 text-brand-700 dark:text-brand-300">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                <span>
                  {describeStats(result.stats)} Đã lưu vào Bản đã tạo, đang phát
                  ở thanh dưới.
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {(["wav", "mp3"] as const).map((fmt) => (
                  <button
                    className="flex items-center gap-1 rounded-lg border border-border bg-background px-2.5 py-1 font-semibold hover:bg-secondary"
                    key={fmt}
                    onClick={() => handleDownload(fmt)}
                    type="button"
                  >
                    <Download className="h-3.5 w-3.5" />
                    {fmt.toUpperCase()}
                  </button>
                ))}
                {result.srt && (
                  <button
                    className="flex items-center gap-1 rounded-lg border border-border bg-background px-2.5 py-1 font-semibold hover:bg-secondary"
                    onClick={handleDownloadSrt}
                    type="button"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Phụ đề đã chỉnh (.srt)
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="lg:col-span-7">
        <div className="srt-cues">
          <h3>
            Các câu thoại <span className="srt-count">{cues.length}</span>
          </h3>
          <div aria-hidden="true" className="srt-cue srt-cue-head">
            <span>#</span>
            <span>Thời gian</span>
            <span>Nội dung</span>
          </div>
          <ol>
            {cues.map((c, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: danh sach co dinh, khong sap xep lai
              <li className="srt-cue" key={i}>
                <span className="srt-index">{i + 1}</span>
                <span className="srt-time">
                  {clock(c.start)} → {clock(c.end)}
                </span>
                <span className="srt-text">{c.text}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  );
};

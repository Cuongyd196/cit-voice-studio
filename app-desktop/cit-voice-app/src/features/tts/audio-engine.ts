/**
 * Streaming Audio Engine for CIT Voice Studio
 * Supports:
 * - Real-time streaming playback via Web Audio API
 * - Audio analysis for real-time waveform visualization
 * - Full WAV blob construction for download & replay
 */

import { notifySaved } from "./desktop-files";
import { voicedWindow } from "./ref-audio";

export class StreamingAudioEngine {
  private audioCtx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private gainNode: GainNode | null = null;
  private playHead = 0;
  private activeSources: AudioBufferSourceNode[] = [];
  private accumulatedPCM: Int16Array[] = [];
  private sampleRate = 48_000;
  private leftover: Uint8Array = new Uint8Array(0);
  private headerConsumed = false;
  private isStreaming = false;
  private volume = 1.0;
  private playbackRate = 1.0;

  constructor(sampleRate = 48_000) {
    this.sampleRate = sampleRate;
  }

  public setSampleRate(rate: number): void {
    this.sampleRate = rate;
  }

  public setPlaybackRate(rate: number): void {
    this.playbackRate = rate;
    for (const src of this.activeSources) {
      try {
        src.playbackRate.setValueAtTime(rate, this.audioCtx?.currentTime || 0);
      } catch {
        // Ignored
      }
    }
  }

  public reset(): void {
    this.stop();
    this.prepare();
  }

  public getFrequencyData(): Uint8Array | null {
    return this.getVisualizerData();
  }

  public getCompleteAudioBlob(): Blob {
    return this.finishStreaming().blob;
  }

  private initContext(): {
    audioCtx: AudioContext;
    analyser: AnalyserNode;
    gainNode: GainNode;
  } {
    if (!this.audioCtx || this.audioCtx.state === "closed") {
      const AudioCtxClass =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext })
          .webkitAudioContext;
      this.audioCtx = new AudioCtxClass();

      this.analyser = this.audioCtx.createAnalyser();
      this.analyser.fftSize = 128;
      this.analyser.smoothingTimeConstant = 0.8;

      this.gainNode = this.audioCtx.createGain();
      this.gainNode.gain.setValueAtTime(this.volume, this.audioCtx.currentTime);

      this.gainNode.connect(this.analyser);
      this.analyser.connect(this.audioCtx.destination);
    }
    return {
      audioCtx: this.audioCtx,
      analyser: this.analyser!,
      gainNode: this.gainNode!,
    };
  }

  public async prepare(): Promise<void> {
    const { audioCtx } = this.initContext();
    if (audioCtx.state === "suspended") {
      await audioCtx.resume();
    }
    this.playHead = audioCtx.currentTime + 0.08;
    this.headerConsumed = false;
    this.leftover = new Uint8Array(0);
    this.accumulatedPCM = [];
    this.activeSources = [];
    this.isStreaming = true;
  }

  public setVolume(val: number): void {
    this.volume = Math.max(0, Math.min(1, val));
    if (this.gainNode && this.audioCtx) {
      this.gainNode.gain.setValueAtTime(this.volume, this.audioCtx.currentTime);
    }
  }

  public getVolume(): number {
    return this.volume;
  }

  public getVisualizerData(): Uint8Array | null {
    if (!this.analyser) {
      return null;
    }
    const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
    this.analyser.getByteFrequencyData(dataArray);
    return dataArray;
  }

  public feedChunk(chunk: Uint8Array): void {
    if (!this.isStreaming) {
      return;
    }
    const { audioCtx, gainNode } = this.initContext();

    let combined = chunk;
    if (this.leftover.length > 0) {
      combined = new Uint8Array(this.leftover.length + chunk.length);
      combined.set(this.leftover, 0);
      combined.set(chunk, this.leftover.length);
      this.leftover = new Uint8Array(0);
    }

    if (!this.headerConsumed) {
      if (combined.length < 44) {
        this.leftover = combined;
        return;
      }
      combined = combined.slice(44); // Bỏ qua 44 bytes header của chunk đầu
      this.headerConsumed = true;
    }

    const usable = combined.length - (combined.length % 2);
    if (usable < combined.length) {
      this.leftover = combined.slice(usable);
    }

    if (usable > 0) {
      const pcmBytes = combined.subarray(0, usable);
      const view = new DataView(
        pcmBytes.buffer,
        pcmBytes.byteOffset,
        pcmBytes.byteLength
      );
      const numSamples = Math.floor(usable / 2);
      const int16Array = new Int16Array(numSamples);

      const buffer = audioCtx.createBuffer(1, numSamples, this.sampleRate);
      const channelData = buffer.getChannelData(0);

      for (let i = 0; i < numSamples; i++) {
        const val = view.getInt16(i * 2, true);
        int16Array[i] = val;
        channelData[i] = Math.max(-1, Math.min(1, val / 32_768));
      }

      this.accumulatedPCM.push(int16Array);

      const source = audioCtx.createBufferSource();
      source.buffer = buffer;
      source.playbackRate.value = this.playbackRate;
      source.connect(gainNode);

      const startAt = Math.max(this.playHead, audioCtx.currentTime + 0.04);
      source.start(startAt);
      this.playHead = startAt + buffer.duration / this.playbackRate;
      this.activeSources.push(source);
    }
  }

  public stop(): void {
    this.isStreaming = false;
    for (const src of this.activeSources) {
      try {
        src.stop();
      } catch {
        // Ignored
      }
    }
    this.activeSources = [];
    if (this.audioCtx) {
      this.playHead = this.audioCtx.currentTime;
    }
  }

  public finishStreaming(): { blob: Blob; duration: number } {
    this.isStreaming = false;

    // Tính tổng số sample
    let totalSamples = 0;
    for (const arr of this.accumulatedPCM) {
      totalSamples += arr.length;
    }

    const mergedPCM = new Int16Array(totalSamples);
    let offset = 0;
    for (const arr of this.accumulatedPCM) {
      mergedPCM.set(arr, offset);
      offset += arr.length;
    }

    const duration = totalSamples / this.sampleRate;
    const wavBlob = this.encodeWAV(mergedPCM, this.sampleRate);

    return {
      blob: wavBlob,
      duration,
    };
  }

  private encodeWAV(samples: Int16Array, sampleRate: number): Blob {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    // RIFF chunk descriptor
    this.writeString(view, 0, "RIFF");
    view.setUint32(4, 36 + samples.length * 2, true);
    this.writeString(view, 8, "WAVE");

    // fmt sub-chunk
    this.writeString(view, 12, "fmt ");
    view.setUint32(16, 16, true); // Subchunk1Size (16 for PCM)
    view.setUint16(20, 1, true); // AudioFormat (1 for PCM)
    view.setUint16(22, 1, true); // NumChannels (1 = Mono)
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true); // ByteRate
    view.setUint16(32, 2, true); // BlockAlign
    view.setUint16(34, 16, true); // BitsPerSample

    // data sub-chunk
    this.writeString(view, 36, "data");
    view.setUint32(40, samples.length * 2, true);

    // Write PCM samples
    let index = 44;
    for (let i = 0; i < samples.length; i++) {
      view.setInt16(index, samples[i], true);
      index += 2;
    }

    return new Blob([buffer], { type: "audio/wav" });
  }

  private writeString(view: DataView, offset: number, string: string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }
}

function sanitizeFilename(name: string): string {
  // Loại bỏ các ký tự bị cấm trên Windows: \ / : * ? " < > |
  return name.replace(/[\\/:*?"<>|]/g, "_").trim();
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      resolve(reader.result as string);
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

/**
 * Tải file Blob về máy tính người dùng:
 * 1. Ưu tiên 1: Sử dụng Native Windows Save File Dialog qua PyWebView API (Desktop App EXE)
 * 2. Ưu tiên 2: Sử dụng File System Access API (showSaveFilePicker) trên Web Browser hiện đại (Edge/Chrome)
 * 3. Ưu tiên 3: Fallback thẻ <a download> chuẩn cho các môi trường khác
 */
export async function downloadBlobAsFile(
  blob: Blob,
  filename: string
): Promise<boolean> {
  const safeFilename = sanitizeFilename(filename);

  // 1. PyWebView Desktop App Bridge (Windows Native Save As Dialog)
  const pywebview = (window as any).pywebview;
  if (
    pywebview &&
    pywebview.api &&
    typeof pywebview.api.save_file === "function"
  ) {
    try {
      const base64Data = await blobToBase64(blob);
      const res = await pywebview.api.save_file(safeFilename, base64Data);
      if (res && res.cancelled) {
        return false;
      }
      if (res && res.success) {
        notifySaved(res);
        return true;
      }
    } catch (e) {
      console.warn("PyWebView save_file failed, falling back:", e);
    }
  }

  // 2. Modern Browser File System Access API (Native Save File Dialog)
  if (typeof (window as any).showSaveFilePicker === "function") {
    try {
      const isMp3 = safeFilename.toLowerCase().endsWith(".mp3");
      const isWav = safeFilename.toLowerCase().endsWith(".wav");

      const mimeType = isMp3
        ? "audio/mpeg"
        : isWav
          ? "audio/wav"
          : blob.type || "application/octet-stream";
      const ext = isMp3 ? ".mp3" : isWav ? ".wav" : "";
      const desc = isMp3
        ? "Audio MP3 (*.mp3)"
        : isWav
          ? "Audio WAV (*.wav)"
          : "Tệp âm thanh";

      const handle = await (window as any).showSaveFilePicker({
        suggestedName: safeFilename,
        types: ext
          ? [
              {
                description: desc,
                accept: {
                  [mimeType]: [ext],
                },
              },
            ]
          : undefined,
      });

      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      return true;
    } catch (err: any) {
      if (err && (err.name === "AbortError" || err.code === 20)) {
        // Người dùng nhấn Cancel / Hủy bỏ hộp thoại
        return false;
      }
      console.warn(
        "showSaveFilePicker failed, falling back to <a> download:",
        err
      );
    }
  }

  // 3. Fallback thẻ <a> download truyền thống
  try {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.style.display = "none";
    a.href = url;
    a.download = safeFilename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 1500);
    return true;
  } catch (err) {
    console.error("Lỗi khi tải file:", err);
    return false;
  }
}

// 4 MB đầu: ~4 phút MP3 128 kbps, ~24 giây WAV 44,1 kHz stereo - dư cho 15 giây mẫu.
const PARTIAL_DECODE_BYTES = 4 * 1024 * 1024;
// M4A ~96 kbps: 8 MB ~ 11 phút. File 5 phút giải mã trọn vẫn ổn, 30 phút thì không.
const FULL_DECODE_MAX_BYTES = 8 * 1024 * 1024;

/** File mẫu quá dài và không giải mã từng phần được. */
export class ReferenceTooLongError extends Error {
  constructor() {
    super("reference_too_long");
    this.name = "ReferenceTooLongError";
  }
}

/** Độ dài file qua thẻ <audio> (chỉ đọc metadata); null nếu không đo được. */
function mediaDuration(file: Blob): Promise<number | null> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const audio = new Audio();
    const done = (value: number | null) => {
      clearTimeout(timer);
      audio.removeAttribute("src");
      URL.revokeObjectURL(url);
      resolve(value);
    };
    const timer = setTimeout(() => done(null), 3000);
    audio.preload = "metadata";
    audio.onloadedmetadata = () =>
      done(Number.isFinite(audio.duration) ? audio.duration : null);
    audio.onerror = () => done(null);
    audio.src = url;
  });
}

/**
 * Chuyển đổi bất kỳ file âm thanh nào (WebM từ Mic, MP3, M4A, OGG, FLAC...)
 * thành định dạng WAV 16-bit PCM Mono chuẩn qua Web Audio API của trình duyệt.
 *
 * ``maxSeconds``: chỉ giữ chừng ấy giây, bắt đầu từ chỗ có tiếng đầu tiên (xem
 * ``voicedWindow``). ``duration`` là độ dài phần giữ lại, ``sourceDuration`` là
 * độ dài file gốc (``null`` khi chỉ giải mã phần đầu và không đo được).
 *
 * File lớn chỉ giải mã ``PARTIAL_DECODE_BYTES`` đầu (MP3/WAV/OGG/FLAC/M4A có
 * metadata ở đầu đều được). Giải mã trọn file ghi âm 30 phút làm trang không nạp
 * được audio nào nữa cho đến khi tải lại (đo trên Edge, 2026-09), nên file không
 * giải mã từng phần được mà lớn hơn ``FULL_DECODE_MAX_BYTES`` thì báo
 * ``ReferenceTooLongError`` thay vì giải mã trọn.
 */
export async function convertAudioToWav(
  audioInput: Blob | File,
  maxSeconds?: number
): Promise<{
  wavBlob: Blob;
  duration: number;
  sourceDuration: number | null;
}> {
  const AudioCtxClass =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext: typeof AudioContext })
      .webkitAudioContext;
  const audioCtx = new AudioCtxClass();

  try {
    let audioBuffer: AudioBuffer | null = null;
    let sourceDuration: number | null = null;
    if (maxSeconds !== undefined && audioInput.size > PARTIAL_DECODE_BYTES) {
      try {
        const head = await audioInput
          .slice(0, PARTIAL_DECODE_BYTES)
          .arrayBuffer();
        const decoded = await audioCtx.decodeAudioData(head);
        // Đủ maxSeconds thì dùng luôn (im lặng đầu dài thì phần giữ ngắn hơn).
        if (decoded.duration >= maxSeconds) {
          audioBuffer = decoded;
          sourceDuration = await mediaDuration(audioInput);
        }
      } catch {
        // Định dạng cần cả file (M4A có metadata ở cuối...): xét tiếp bên dưới.
      }
      if (!audioBuffer && audioInput.size > FULL_DECODE_MAX_BYTES) {
        throw new ReferenceTooLongError();
      }
    }
    if (!audioBuffer) {
      audioBuffer = await audioCtx.decodeAudioData(
        await audioInput.arrayBuffer()
      );
      sourceDuration = audioBuffer.duration;
    }
    const sampleRate = audioBuffer.sampleRate || 48_000;
    const [start, end] =
      maxSeconds === undefined
        ? [0, audioBuffer.length]
        : voicedWindow(audioBuffer.getChannelData(0), sampleRate, maxSeconds);
    const length = end - start;
    const duration = length / sampleRate;

    // Downmix về mono float32 - chỉ phần giữ lại, không phải cả file.
    const monoPCM = new Float32Array(length);
    const numChannels = audioBuffer.numberOfChannels;
    for (let c = 0; c < numChannels; c++) {
      const channelData = audioBuffer.getChannelData(c);
      for (let i = 0; i < length; i++) {
        monoPCM[i] += channelData[start + i] / numChannels;
      }
    }

    // Chuyển đổi sang PCM 16-bit
    const int16Samples = new Int16Array(length);
    for (let i = 0; i < length; i++) {
      const s = Math.max(-1, Math.min(1, monoPCM[i]));
      int16Samples[i] = s < 0 ? s * 0x80_00 : s * 0x7f_ff;
    }

    // Đóng gói WAV Header chuẩn
    const buffer = new ArrayBuffer(44 + int16Samples.length * 2);
    const view = new DataView(buffer);

    const writeString = (offset: number, str: string) => {
      for (let i = 0; i < str.length; i++) {
        view.setUint8(offset + i, str.charCodeAt(i));
      }
    };

    writeString(0, "RIFF");
    view.setUint32(4, 36 + int16Samples.length * 2, true);
    writeString(8, "WAVE");
    writeString(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true); // PCM format
    view.setUint16(22, 1, true); // 1 Channel (Mono)
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true); // Byte rate (sr * numChannels * 2)
    view.setUint16(32, 2, true); // Block align
    view.setUint16(34, 16, true); // 16 bits per sample
    writeString(36, "data");
    view.setUint32(40, int16Samples.length * 2, true);

    let index = 44;
    for (let i = 0; i < int16Samples.length; i++) {
      view.setInt16(index, int16Samples[i], true);
      index += 2;
    }

    const wavBlob = new Blob([buffer], { type: "audio/wav" });
    return { wavBlob, duration, sourceDuration };
  } finally {
    try {
      await audioCtx.close();
    } catch {
      // Ignored
    }
  }
}

import type {
  DialogueTurn,
  DownloadState,
  ModelOption,
  PdfExtractionResult,
  VoiceOption,
} from "./types";

export interface HealthResponse {
  backend?: string;
  device?: string;
  engine: string;
  /** Ngôn ngữ mô hình đọc được (Supertonic); rỗng với VieNeu. */
  languages?: LanguageOption[];
  /** Câu mô tả trạng thái để hiển thị trên màn hình chờ. */
  message?: string;
  precision?: string;
  sample_rate: number;
  /** "loading" khi máy chủ đã mở cổng nhưng mô hình chưa nạp xong, "ok", hoặc "error". */
  status: string;
  supports_cloning?: boolean;
  /** Mô hình hiểu thẻ cảm xúc không (Kokoro: không). */
  supports_emotions?: boolean;
  /** Mỗi lần tạo ngữ điệu khác nhau, nên seed cố định có tác dụng (Kokoro: không). */
  supports_seed?: boolean;
}

export interface LanguageOption {
  code: string;
  name: string;
}

// Ngon ngu nguoi dung chon cho mo hinh doc nhieu ngon ngu (Supertonic). Gui kem moi
// request doc; null = server tu nhan theo chu. VieNeu bo qua tham so nay. Dat qua
// ModelCapsProvider (model-caps.tsx) de khoi truyen props qua tung tab.
let requestLanguage: string | null = null;

export function setRequestLanguage(code: string | null): void {
  requestLanguage = code || null;
}

export interface SynthesisResult {
  blob: Blob;
  durationSeconds: number;
  elapsedSeconds: number;
  rtf?: number;
  sampleRate: number;
}

const clean = (url: string) => url.replace(/\/+$/, "");

export async function checkServerHealth(
  apiUrl: string,
  signal?: AbortSignal
): Promise<HealthResponse> {
  return fetchStartupJson<HealthResponse>(`${clean(apiUrl)}/health`, signal);
}

// Bound the entire request, including the response body. Never follow a timed-out
// health check with an unbounded /voices request: that prevents the next poll.
async function fetchStartupJson<T>(
  url: string,
  signal?: AbortSignal,
  init: RequestInit = {}
): Promise<T> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal?.addEventListener("abort", abort, { once: true });
  if (signal?.aborted) {
    controller.abort();
  }
  const timeoutId = setTimeout(abort, 10_000);
  try {
    const res = await fetch(url, {
      method: "GET",
      cache: "no-store",
      headers: { Accept: "application/json" },
      ...init,
      signal: controller.signal,
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    return await res.json();
  } finally {
    clearTimeout(timeoutId);
    signal?.removeEventListener("abort", abort);
  }
}

export async function fetchVoices(
  apiUrl: string,
  signal?: AbortSignal
): Promise<VoiceOption[]> {
  return fetchStartupJson<VoiceOption[]>(`${clean(apiUrl)}/voices`, signal);
}

export interface ServerPortSettings {
  active_port: number;
  port: number;
}

export function fetchServerPort(
  apiUrl: string,
  signal?: AbortSignal
): Promise<ServerPortSettings> {
  return fetchStartupJson(`${clean(apiUrl)}/api/settings/server-port`, signal);
}

export function saveServerPort(
  apiUrl: string,
  port: number
): Promise<ServerPortSettings> {
  return fetchStartupJson(
    `${clean(apiUrl)}/api/settings/server-port`,
    undefined,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ port }),
    }
  );
}

export interface GpuMemoryInfo {
  /** true khi đang chạy mô hình GPU (PyTorch/CUDA). */
  available: boolean;
  effective_limit_gb?: number;
  gpu_name?: string;
  graphs?: number;
  /** Mức người dùng đặt; null = tự động. */
  limit_gb: number | null;
  max_graphs?: number;
  min_gb: number;
  total_gb?: number;
  used_gb?: number | null;
}

export function fetchGpuMemory(
  apiUrl: string,
  signal?: AbortSignal
): Promise<GpuMemoryInfo> {
  return fetchStartupJson(`${clean(apiUrl)}/api/gpu/memory`, signal);
}

export function saveGpuMemory(
  apiUrl: string,
  limitGb: number | null
): Promise<GpuMemoryInfo> {
  return fetchStartupJson(`${clean(apiUrl)}/api/gpu/memory`, undefined, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ limit_gb: limitGb }),
  });
}

/** Tuỳ chọn giao diện lưu ở máy chủ: app desktop xoá localStorage mỗi lần tắt. */
export interface UiPrefs {
  autoPlayOnGenerate?: boolean;
  defaultVoiceId?: string;
  playbackSpeed?: number;
  silenceDuration?: number;
  theme?: "light" | "dark";
}

export function fetchUiPrefs(
  apiUrl: string,
  signal?: AbortSignal
): Promise<UiPrefs> {
  return fetchStartupJson(`${clean(apiUrl)}/api/ui/prefs`, signal);
}

export function saveUiPrefs(apiUrl: string, prefs: UiPrefs): Promise<UiPrefs> {
  return fetchStartupJson(`${clean(apiUrl)}/api/ui/prefs`, undefined, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(prefs),
  });
}

export interface PronunciationEntry {
  /** false = khớp mọi kiểu viết hoa/thường. */
  match_case: boolean;
  reading: string;
  word: string;
}

export interface PronunciationDictResponse {
  defaults?: PronunciationEntry[];
  entries: PronunciationEntry[];
  path: string;
}

async function pronunciationRequest<T>(
  url: string,
  init: RequestInit
): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", Accept: "application/json" },
  });
  if (!res.ok) {
    // FastAPI trả {"detail": "..."}: 400 = lỗi dữ liệu (câu tiếng Việt), 422 = sai kiểu.
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // giữ statusText
    }
    throw new Error(detail);
  }
  return res.json();
}

export function fetchPronunciations(
  apiUrl: string,
  signal?: AbortSignal
): Promise<PronunciationDictResponse> {
  return fetchStartupJson(`${clean(apiUrl)}/api/pronunciations`, signal);
}

export function savePronunciations(
  apiUrl: string,
  entries: PronunciationEntry[]
): Promise<PronunciationDictResponse> {
  return pronunciationRequest(`${clean(apiUrl)}/api/pronunciations`, {
    method: "PUT",
    body: JSON.stringify({ entries }),
  });
}

/** Văn bản sau khi thay theo `entries` (bản nháp chưa lưu). */
export async function previewPronunciations(
  apiUrl: string,
  text: string,
  entries: PronunciationEntry[],
  signal?: AbortSignal
): Promise<string> {
  const body = await pronunciationRequest<{ text: string }>(
    `${clean(apiUrl)}/api/pronunciations/preview`,
    { method: "POST", body: JSON.stringify({ text, entries }), signal }
  );
  return body.text;
}

export async function streamSpeechAudio(
  apiUrl: string,
  text: string,
  voiceId: string,
  onChunk: (chunk: Uint8Array) => void,
  signal?: AbortSignal
): Promise<void> {
  const cleanUrl = clean(apiUrl);
  const query = new URLSearchParams({
    text,
    voice_id: voiceId,
  });
  if (requestLanguage) {
    query.set("language", requestLanguage);
  }

  const response = await fetch(`${cleanUrl}/stream?${query.toString()}`, {
    method: "GET",
    signal,
  });

  if (!response.ok) {
    throw new Error(
      `Lỗi máy chủ HTTP ${response.status}: ${response.statusText}`
    );
  }

  if (!response.body) {
    throw new Error("Không hỗ trợ luồng truyền (ReadableStream).");
  }

  const reader = response.body.getReader();

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      if (value && value.length > 0) {
        onChunk(value);
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export async function synthesizeSpeech(
  apiUrl: string,
  params: {
    text: string;
    voiceId?: string;
    speed?: number;
    temperature?: number;
    silenceDuration?: number;
    format?: "wav" | "mp3";
    /** false khi text đã thay sẵn theo từ điển phát âm (nút "Nghe thử"). */
    usePronunciationDict?: boolean;
  },
  signal?: AbortSignal
): Promise<SynthesisResult> {
  const cleanUrl = clean(apiUrl);
  const response = await fetch(`${cleanUrl}/api/tts/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: params.text,
      voice_id: params.voiceId || null,
      language: requestLanguage,
      speed: params.speed || 1.0,
      temperature: params.temperature ?? 0.8,
      silence_duration: params.silenceDuration ?? 0.2,
      format: params.format || "wav",
      use_pronunciation_dict: params.usePronunciationDict ?? true,
    }),
    signal,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      `Lỗi tổng hợp giọng nói: ${errorText || response.statusText}`
    );
  }

  const durationSec = Number.parseFloat(
    response.headers.get("X-Duration-Seconds") || "0"
  );
  const elapsedSec = Number.parseFloat(
    response.headers.get("X-Elapsed-Seconds") || "0"
  );
  const rtf = Number.parseFloat(response.headers.get("X-RTF") || "0");
  const sampleRate = Number.parseInt(
    response.headers.get("X-Sample-Rate") || "48000",
    10
  );
  const blob = await response.blob();

  return {
    blob,
    durationSeconds: durationSec,
    elapsedSeconds: elapsedSec,
    rtf,
    sampleRate,
  };
}

export interface ConsentInfo {
  rights_statement: string;
  terms_version: string;
}

export async function fetchConsentInfo(apiUrl: string): Promise<ConsentInfo> {
  const response = await fetch(`${clean(apiUrl)}/api/voices/consent`);
  if (!response.ok) {
    throw new Error("Không đọc được cam kết quyền giọng từ máy chủ.");
  }
  return await response.json();
}

export async function addCustomVoice(
  apiUrl: string,
  params: {
    name: string;
    audioFile: File | Blob;
    denoise?: boolean;
    inputSource: "recording" | "file";
    rightsConfirmed: boolean;
    rightsVersion: string;
  }
): Promise<{ voice_id: string }> {
  const cleanUrl = clean(apiUrl);
  const formData = new FormData();
  formData.append("name", params.name);
  formData.append("ref_audio", params.audioFile, "reference_audio.wav");
  formData.append("denoise", params.denoise === false ? "false" : "true");
  formData.append("input_source", params.inputSource);
  formData.append("rights_confirmed", String(params.rightsConfirmed));
  formData.append("rights_version", params.rightsVersion);

  const response = await fetch(`${cleanUrl}/api/voices/custom`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => null);
    throw new Error(err?.detail || "Không lưu được giọng tuỳ chỉnh.");
  }

  return await response.json();
}

export async function deleteCustomVoice(
  apiUrl: string,
  name: string
): Promise<void> {
  const cleanUrl = clean(apiUrl);
  const response = await fetch(
    `${cleanUrl}/api/voices/custom/${encodeURIComponent(name)}`,
    { method: "DELETE" }
  );

  if (!response.ok) {
    const err = await response.json().catch(() => null);
    throw new Error(err?.detail || "Không xoá được giọng tuỳ chỉnh.");
  }
}

/** Câu mẫu đọc bằng giọng `voiceId` - backend cache trên đĩa nên lần sau phát ngay. */
export async function fetchVoicePreview(
  apiUrl: string,
  voiceId: string,
  signal?: AbortSignal
): Promise<Blob> {
  const cleanUrl = clean(apiUrl);
  const query = new URLSearchParams({ voice_id: voiceId });
  // Mo hinh nhieu ngon ngu doc cau mau bang ngon ngu dang chon.
  if (requestLanguage) {
    query.set("language", requestLanguage);
  }
  const response = await fetch(`${cleanUrl}/api/voices/preview?${query}`, {
    signal,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => null);
    throw new Error(err?.detail || "Không nghe thử được giọng này.");
  }

  return await response.blob();
}

export async function synthesizeConversation(
  apiUrl: string,
  params: {
    script?: string;
    turns?: DialogueTurn[];
    speakerMapping?: Record<string, string>;
    silenceDuration?: number;
    speed?: number;
    temperature?: number;
    format?: "wav" | "mp3";
  },
  signal?: AbortSignal
): Promise<SynthesisResult & { turnsCount?: number }> {
  const cleanUrl = clean(apiUrl);
  const response = await fetch(`${cleanUrl}/api/tts/conversation`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      script: params.script,
      turns: params.turns?.map((t) => ({
        speaker: t.speaker,
        text: t.text,
        voice_id: t.voiceId,
      })),
      speaker_mapping: params.speakerMapping,
      language: requestLanguage,
      silence_duration: params.silenceDuration ?? 0.4,
      speed: params.speed || 1.0,
      temperature: params.temperature ?? 0.8,
      format: params.format || "wav",
    }),
    signal,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Lỗi tạo hội thoại: ${errorText || response.statusText}`);
  }

  const durationSec = Number.parseFloat(
    response.headers.get("X-Duration-Seconds") || "0"
  );
  const elapsedSec = Number.parseFloat(
    response.headers.get("X-Elapsed-Seconds") || "0"
  );
  const sampleRate = Number.parseInt(
    response.headers.get("X-Sample-Rate") || "48000",
    10
  );
  const turnsCount = Number.parseInt(
    response.headers.get("X-Turns-Count") || "0",
    10
  );
  const blob = await response.blob();

  return {
    blob,
    durationSeconds: durationSec,
    elapsedSeconds: elapsedSec,
    sampleRate,
    turnsCount,
  };
}

export async function extractPdfText(
  apiUrl: string,
  file: File | Blob,
  filename: string
): Promise<PdfExtractionResult> {
  const cleanUrl = clean(apiUrl);
  const formData = new FormData();
  formData.append("file", file, filename);

  const response = await fetch(`${cleanUrl}/api/pdf/extract`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    // FastAPI trả {"detail": "..."} - hiện câu tiếng Việt, không in nguyên JSON.
    const raw = await response.text();
    let detail = raw || response.statusText;
    try {
      const body = JSON.parse(raw);
      if (typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // giữ nguyên văn bản gốc
    }
    throw new Error(detail);
  }

  return await response.json();
}

export async function convertToMp3(
  apiUrl: string,
  wavBlob: Blob
): Promise<Blob> {
  const cleanUrl = clean(apiUrl);
  const formData = new FormData();
  formData.append("file", wavBlob, "audio.wav");

  const response = await fetch(`${cleanUrl}/api/audio/mp3`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error("Không thể chuyển đổi sang định dạng MP3.");
  }

  return await response.blob();
}

export async function fetchModels(
  apiUrl: string
): Promise<{ current: any; models: ModelOption[] }> {
  const cleanUrl = clean(apiUrl);
  const response = await fetch(`${cleanUrl}/api/models`, { method: "GET" });
  if (!response.ok) {
    throw new Error("Không thể lấy danh sách mô hình.");
  }
  return await response.json();
}

export async function switchModel(
  apiUrl: string,
  modelName: string,
  device = "auto"
): Promise<{ status: string; current: any }> {
  const cleanUrl = clean(apiUrl);
  const response = await fetch(`${cleanUrl}/api/models/load`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model_name: modelName, device }),
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Lỗi chuyển đổi mô hình: ${err}`);
  }

  return await response.json();
}

export async function startModelDownload(
  apiUrl: string,
  modelId: string,
  autoApply = true,
  pack: string | null = null
): Promise<void> {
  const cleanUrl = clean(apiUrl);
  const response = await fetch(`${cleanUrl}/api/models/download`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model_id: modelId, auto_apply: autoApply, pack }),
  });

  if (!response.ok) {
    // 409 = đã có việc tải khác đang chạy; backend gửi kèm câu tiếng Việt.
    const err = await response.json().catch(() => null);
    throw new Error(err?.detail || "Không bắt đầu được việc tải mô hình.");
  }
}

export async function fetchDownloadStatus(
  apiUrl: string
): Promise<DownloadState> {
  const cleanUrl = clean(apiUrl);
  const response = await fetch(`${cleanUrl}/api/models/download`, {
    method: "GET",
  });
  if (!response.ok) {
    throw new Error("Không đọc được tiến trình tải.");
  }
  return await response.json();
}

export async function cancelModelDownload(apiUrl: string): Promise<void> {
  const cleanUrl = clean(apiUrl);
  const response = await fetch(`${cleanUrl}/api/models/download/cancel`, {
    method: "POST",
  });
  if (!response.ok) {
    const err = await response.json().catch(() => null);
    throw new Error(err?.detail || "Không huỷ được việc tải.");
  }
}

// ---------------------------------------------------------------------------
// Phu de (SRT) + lich su luu tren o dia
// ---------------------------------------------------------------------------

async function detailOf(response: Response, fallback: string): Promise<string> {
  const raw = await response.text().catch(() => "");
  try {
    const body = JSON.parse(raw);
    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // khong phai JSON
  }
  return raw || fallback;
}

export interface SubtitleCue {
  end: number;
  start: number;
  text: string;
}

/** Tao giong kem phu de: server doc theo tung cau de do moc thoi gian that. */
export async function synthesizeSpeechWithSubtitles(
  apiUrl: string,
  params: {
    text: string;
    voiceId?: string;
    speed?: number;
    temperature?: number;
    format?: "wav" | "mp3";
  },
  signal?: AbortSignal
): Promise<SynthesisResult & { cues: SubtitleCue[]; srt: string }> {
  const response = await fetch(
    `${clean(apiUrl)}/api/tts/generate-with-subtitles`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: params.text,
        voice_id: params.voiceId || null,
        language: requestLanguage,
        speed: params.speed || 1.0,
        temperature: params.temperature ?? 0.8,
        format: params.format || "wav",
      }),
      signal,
    }
  );
  if (!response.ok) {
    throw new Error(
      `Lỗi tổng hợp giọng nói: ${await detailOf(response, response.statusText)}`
    );
  }
  const body = await response.json();
  const bytes = Uint8Array.from(atob(body.audio_base64), (c) =>
    c.charCodeAt(0)
  );
  return {
    blob: new Blob([bytes], {
      type: body.format === "mp3" ? "audio/mpeg" : "audio/wav",
    }),
    durationSeconds: body.duration_seconds,
    elapsedSeconds: body.elapsed_seconds,
    rtf: body.rtf,
    sampleRate: body.sample_rate,
    srt: body.srt,
    cues: body.cues,
  };
}

export interface GenerateToHistoryResult {
  durationSeconds: number;
  elapsedSeconds: number;
  entry: HistoryApiEntry;
  rtf: number;
  sampleRate: number;
  srt: string | null;
}

/**
 * Tạo giọng rồi để server lưu thẳng vào lịch sử trên ổ đĩa; chỉ nhận thông tin mục
 * lịch sử, audio phát/tải qua URL. Không đưa cả khối audio vào trình duyệt: bài
 * ~2 giờ (~690 MB WAV) làm cửa sổ app trắng khi trình duyệt vừa giữ, vừa phát,
 * vừa tải ngược nó lên để lưu lịch sử (người dùng báo, 2026-09).
 */
export async function generateToHistory(
  apiUrl: string,
  params: {
    text: string;
    voiceId?: string;
    voiceName?: string;
    speed?: number;
    temperature?: number;
    silenceDuration?: number;
    subtitles?: boolean;
    seed?: number;
  },
  signal?: AbortSignal
): Promise<GenerateToHistoryResult> {
  const response = await fetch(`${clean(apiUrl)}/api/tts/generate-to-history`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: params.text,
      voice_id: params.voiceId || null,
      language: requestLanguage,
      voice_name: params.voiceName || "",
      speed: params.speed || 1.0,
      temperature: params.temperature ?? 0.8,
      silence_duration: params.silenceDuration ?? 0.2,
      subtitles: params.subtitles ?? false,
      mode: "tts",
      seed: params.seed ?? null,
    }),
    signal,
  });
  if (!response.ok) {
    const err = await response.json().catch(() => null);
    throw new Error(
      `Lỗi tổng hợp giọng nói: ${err?.detail || response.statusText}`
    );
  }
  return toHistoryResult(await response.json());
}

export interface SrtCue {
  end: number;
  start: number;
  text: string;
}

/** Doc truoc file phu de de hien danh sach cau (server kiem tra dinh dang). */
export async function parseSrt(
  apiUrl: string,
  srt: string
): Promise<{ cues: SrtCue[]; durationSeconds: number }> {
  const response = await fetch(`${clean(apiUrl)}/api/srt/parse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ srt }),
  });
  if (!response.ok) {
    throw new Error(await detailOf(response, "Không đọc được file phụ đề."));
  }
  const body = await response.json();
  return { cues: body.cues, durationSeconds: body.duration_seconds };
}

export interface DubStats {
  cues: number;
  max_push_seconds: number;
  pushed: number;
  sped_up: number;
}

/**
 * Long tieng theo moc phu de: server doc tung cau, khop vao moc (tang toc toi da
 * 1,5x, tran thi day cau sau lui) va luu thang mot file dai dung timeline vao lich su.
 */
export async function dubSrtToHistory(
  apiUrl: string,
  params: { srt: string; voiceId?: string; voiceName?: string; speed?: number },
  signal?: AbortSignal
): Promise<GenerateToHistoryResult & { stats: DubStats }> {
  const response = await fetch(`${clean(apiUrl)}/api/tts/dub-srt-to-history`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      srt: params.srt,
      voice_id: params.voiceId || null,
      language: requestLanguage,
      voice_name: params.voiceName || "",
      speed: params.speed || 1.0,
    }),
    signal,
  });
  if (!response.ok) {
    throw new Error(
      `Lỗi lồng tiếng: ${await detailOf(response, response.statusText)}`
    );
  }
  const body = await response.json();
  return { ...toHistoryResult(body), stats: body.stats };
}

// biome-ignore lint/suspicious/noExplicitAny: JSON tu server
function toHistoryResult(body: any): GenerateToHistoryResult {
  return {
    entry: body.entry,
    sampleRate: body.sample_rate,
    durationSeconds: body.duration_seconds,
    elapsedSeconds: body.elapsed_seconds,
    rtf: body.rtf,
    srt: body.srt ?? null,
  };
}

export interface HistoryApiEntry {
  audio_url: string;
  duration_seconds: number;
  format: "wav" | "mp3";
  has_subtitles: boolean;
  id: string;
  mode: string;
  subtitles_url?: string;
  text: string;
  timestamp: number;
  voice_id: string;
  voice_name: string;
}

export async function fetchHistory(apiUrl: string): Promise<HistoryApiEntry[]> {
  const response = await fetch(`${clean(apiUrl)}/api/history`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(
      await detailOf(response, "Không đọc được danh sách bản đã tạo.")
    );
  }
  return (await response.json()).entries;
}

export interface HistoryInfo {
  bytes: number;
  count: number;
  disk_free: number | null;
  folder: string;
  /** Lich su qua lon hoac o dia sap day: nen nhac nguoi dung don bot. */
  warn: boolean;
}

export async function fetchHistoryInfo(
  apiUrl: string,
  signal?: AbortSignal
): Promise<HistoryInfo> {
  const response = await fetch(`${clean(apiUrl)}/api/history/info`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw new Error(
      await detailOf(response, "Không đọc được danh sách bản đã tạo.")
    );
  }
  return response.json();
}

export async function openHistoryFolder(apiUrl: string): Promise<void> {
  const response = await fetch(`${clean(apiUrl)}/api/history/open-folder`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(
      await detailOf(response, "Không mở được thư mục bản đã tạo.")
    );
  }
}

export async function saveHistory(
  apiUrl: string,
  entry: {
    audio: Blob;
    durationSeconds: number;
    format: "wav" | "mp3";
    mode: string;
    subtitles?: string;
    text: string;
    voiceId: string;
    voiceName: string;
  }
): Promise<HistoryApiEntry> {
  const form = new FormData();
  form.append("audio", entry.audio, `audio.${entry.format}`);
  form.append("text", entry.text);
  form.append("voice_id", entry.voiceId);
  form.append("voice_name", entry.voiceName);
  form.append("duration_seconds", String(entry.durationSeconds || 0));
  form.append("format", entry.format);
  form.append("mode", entry.mode);
  if (entry.subtitles) {
    form.append("subtitles", entry.subtitles);
  }
  const response = await fetch(`${clean(apiUrl)}/api/history`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    throw new Error(await detailOf(response, "Không lưu được bản đã tạo."));
  }
  return response.json();
}

export async function deleteHistory(apiUrl: string, id: string): Promise<void> {
  const response = await fetch(
    `${clean(apiUrl)}/api/history/${encodeURIComponent(id)}`,
    { method: "DELETE" }
  );
  // 404 = da bi xoa (vd. tu don khi vuot gioi han) -> coi nhu thanh cong.
  if (!response.ok && response.status !== 404) {
    throw new Error(await detailOf(response, "Không xoá được bản này."));
  }
}

/** Mo thu muc chua file cua muc lich su (tren may chay server), chon san file do. */
export async function revealHistory(apiUrl: string, id: string): Promise<void> {
  const response = await fetch(
    `${clean(apiUrl)}/api/history/${encodeURIComponent(id)}/reveal`,
    { method: "POST" }
  );
  if (!response.ok) {
    throw new Error(
      await detailOf(response, "Không mở được thư mục chứa file.")
    );
  }
}

export async function clearHistory(apiUrl: string): Promise<void> {
  const response = await fetch(`${clean(apiUrl)}/api/history`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(await detailOf(response, "Không xoá được các bản đã tạo."));
  }
}

// ---- Cho may khac truy cap (LAN) + khoa API ----

export interface RemoteAccessInfo {
  /** IPv4 trong mang LAN cua may nay. */
  addresses: string[];
  api_key: string;
  /** Da luu "bat" (ap dung tu lan mo app sau neu listening_all con false). */
  enabled: boolean;
  /** Server hien dang lang nghe 0.0.0.0 (may khac ket noi toi duoc). */
  listening_all: boolean;
  port: number;
  /** IP card mang chinh (theo bang dinh tuyen); null neu khong co mang. */
  primary_address: string | null;
}

async function remoteAccessCall(
  url: string,
  init: RequestInit,
  fallback: string
): Promise<RemoteAccessInfo> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(await detailOf(response, fallback));
  }
  return response.json();
}

export function fetchRemoteAccess(
  apiUrl: string,
  signal?: AbortSignal
): Promise<RemoteAccessInfo> {
  return remoteAccessCall(
    `${clean(apiUrl)}/api/remote-access`,
    { signal },
    "Không đọc được cài đặt truy cập từ máy khác."
  );
}

export function saveRemoteAccess(
  apiUrl: string,
  enabled: boolean
): Promise<RemoteAccessInfo> {
  return remoteAccessCall(
    `${clean(apiUrl)}/api/remote-access`,
    {
      body: JSON.stringify({ enabled }),
      headers: { "Content-Type": "application/json" },
      method: "PUT",
    },
    "Không lưu được cài đặt truy cập từ máy khác."
  );
}

export function regenerateRemoteKey(apiUrl: string): Promise<RemoteAccessInfo> {
  return remoteAccessCall(
    `${clean(apiUrl)}/api/remote-access/regenerate-key`,
    { method: "POST" },
    "Không tạo được khoá mới."
  );
}

// ---- Phien ban + kiem tra ban moi (chi bao, khong tu tai) ----

export interface AppUpdateInfo {
  checked_at: number | null;
  /** Phien ban dang chay. */
  current: string;
  /** Tu kiem tra khi mo app (tat duoc trong Cai dat). */
  enabled: boolean;
  /** Loi mang khi hoi GitHub; giao dien chi hien khi nguoi dung tu bam kiem tra. */
  error: string | null;
  /** Tên các nhóm thay đổi (tiêu đề ### của ghi chú phát hành). */
  highlights?: string[];
  latest: string | null;
  newer: boolean;
  published_at: string | null;
  /** Người dùng đã bấm "Để sau" ở hộp thoại của đúng bản này. */
  skipped?: boolean;
  /** Trang phat hanh de tai ban moi. */
  url: string;
}

export async function checkAppUpdate(
  apiUrl: string,
  force = false,
  signal?: AbortSignal
): Promise<AppUpdateInfo> {
  const response = await fetch(
    `${clean(apiUrl)}/api/app/update${force ? "?force=true" : ""}`,
    { signal }
  );
  if (!response.ok) {
    throw new Error(await detailOf(response, "Không kiểm tra được bản mới."));
  }
  return response.json();
}

export async function saveUpdateCheck(
  apiUrl: string,
  enabled: boolean
): Promise<boolean> {
  const response = await fetch(`${clean(apiUrl)}/api/app/update-check`, {
    body: JSON.stringify({ enabled }),
    headers: { "Content-Type": "application/json" },
    method: "PUT",
  });
  if (!response.ok) {
    throw new Error(await detailOf(response, "Không lưu được cài đặt."));
  }
  const body = await response.json();
  return body.enabled === true;
}

/** "Để sau": không bật hộp thoại cập nhật cho bản này nữa. */
export async function skipAppUpdate(
  apiUrl: string,
  version: string
): Promise<void> {
  const response = await fetch(`${clean(apiUrl)}/api/app/update-skip`, {
    body: JSON.stringify({ version }),
    headers: { "Content-Type": "application/json" },
    method: "PUT",
  });
  if (!response.ok) {
    throw new Error(await detailOf(response, "Không lưu được."));
  }
}

// ---- Khoi dong lai ung dung (cai dat chi ap dung luc mo app) ----

export async function fetchRestartSupport(apiUrl: string): Promise<boolean> {
  const response = await fetch(`${clean(apiUrl)}/api/app/restart`);
  if (!response.ok) {
    return false;
  }
  const body = await response.json();
  return body.supported === true;
}

export async function restartApp(apiUrl: string): Promise<void> {
  const response = await fetch(`${clean(apiUrl)}/api/app/restart`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(
      await detailOf(response, "Không khởi động lại được ứng dụng.")
    );
  }
}

export interface TermsInfo {
  accepted: boolean;
  text: string;
  version: string;
}

export async function fetchTerms(apiUrl: string): Promise<TermsInfo> {
  const response = await fetch(`${clean(apiUrl)}/api/terms`);
  if (!response.ok) {
    throw new Error("Không đọc được điều khoản sử dụng.");
  }
  return await response.json();
}

export async function acceptTerms(apiUrl: string): Promise<void> {
  const response = await fetch(`${clean(apiUrl)}/api/terms/accept`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error("Không lưu được lựa chọn đồng ý. Thử lại.");
  }
}

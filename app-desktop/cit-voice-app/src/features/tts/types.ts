export interface VoiceOption {
  avatar?: string;
  description?: string;
  /** Giọng tác giả VieNeu chọn (xếp đầu danh sách). */
  featured?: boolean;
  gender?: "male" | "female" | "neutral";
  id: string;
  isCloned?: boolean;
  /** Tiếng mà giọng được huấn luyện (Kokoro: "en", "fr"...); không có với VieNeu/Supertonic. */
  language?: string;
  name: string;
  region?: "North" | "South" | "Central" | "Standard" | null;
}

export type PlaybackStatus =
  | "idle"
  | "generating"
  | "streaming"
  | "playing"
  | "paused"
  | "error";

export type ConnectionStatus = "connecting" | "connected" | "disconnected";

export type ActiveTab =
  | "tts"
  | "clone"
  | "conversation"
  | "pdf"
  | "batch"
  | "history"
  | "about";

export interface HistoryEntry {
  /** Co san khi vua tao; muc nap lai tu o dia thi tai ve khi can (xem history.ts). */
  audioBlob?: Blob;
  /** blob: URL khi vua tao, hoac URL cua server voi muc da luu. */
  audioBlobUrl: string;
  durationSeconds: number;
  format?: "wav" | "mp3";
  id: string;
  mode?: "tts" | "clone" | "conversation" | "pdf";
  /** Id cua muc tren server (lich su luu tren dia); chua co khi dang luu / luu loi. */
  serverId?: string;
  /** Noi dung phu de SRT (khi tao kem phu de). */
  subtitles?: string;
  /** URL tai phu de cua muc da luu tren server. */
  subtitlesUrl?: string;
  text: string;
  timestamp: number;
  voiceId: string;
  voiceName: string;
}

export interface AppSettings {
  apiUrl: string;
  autoPlayOnGenerate: boolean;
  /** Giọng mở sẵn khi vào app. Rỗng = giọng mặc định của mô hình. */
  defaultVoiceId?: string;
  modelName?: string;
  playbackSpeed: number;
  sampleRate: number;
  silenceDuration?: number;
}

export interface DialogueTurn {
  id: string;
  speaker: string;
  text: string;
  voiceId?: string;
}

export interface ModelOption {
  /** Dung lượng ước lượng phải tải, để hiện "Chưa tải - 453 MB". */
  approx_bytes?: number;
  /** Máy này có chạy được model đó không. Backend tự xác định (có CUDA, có torch...). */
  available?: boolean;
  /** Máy này chạy được model đó không. Tách bạch với downloaded. */
  compatible?: boolean;
  description: string;
  device: string;
  /** File model đã nằm đủ trong cache HF cục bộ chưa. */
  downloaded?: boolean;
  id: string;
  name: string;
  /** Đã tải mô hình nhưng chưa cài bộ tách âm (Kokoro). */
  needs_addon_setup?: boolean;
  needs_gpu_setup?: boolean;
  /** Ghi chú kèm theo, ví dụ FP32 phải tải thêm ~453MB ở lần chọn đầu. */
  note?: string | null;
  /** Gói ngôn ngữ tải thêm (Kokoro: tiếng Nhật, tiếng Trung). */
  packs?: LanguagePack[];
  precision: string;
  supports_cloning: boolean;
  supports_streaming: boolean;
  /** Lý do không dùng được, để hiển thị cho người dùng thay vì để họ đâm vào tường. */
  unavailable_reason?: string | null;
}

export interface PdfExtractionResult {
  filename: string;
  page_count: number;
  pages: string[];
  text: string;
}

/** Gói ngôn ngữ tải thêm cho một mô hình (Kokoro: tiếng Nhật, tiếng Trung). */
export interface LanguagePack {
  approx_bytes: number;
  code: string;
  installed: boolean;
  name: string;
}

/** Tiến trình của việc tải model đang chạy ở thread nền phía server. */
export interface DownloadState {
  current_file: string;
  done_bytes: number;
  message: string;
  model_id: string | null;
  /** Gói ngôn ngữ đang tải ("ja"/"zh"); null = tải cả mô hình. */
  pack?: string | null;
  percent: number;
  phase?: "model" | "gpu_setup" | "addon_setup";
  state: "idle" | "downloading" | "applying" | "ready" | "error" | "cancelled";
  total_bytes: number;
}

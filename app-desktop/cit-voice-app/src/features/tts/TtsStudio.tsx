import {
  AlertCircle,
  BookOpen,
  FileText,
  History,
  Info,
  ListOrdered,
  Mic,
  Settings,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import env from "@/config/env";
import {
  type AppUpdateInfo,
  checkAppUpdate,
  checkServerHealth,
  clearHistory,
  convertToMp3,
  deleteCustomVoice,
  deleteHistory,
  fetchHistory,
  fetchUiPrefs,
  fetchVoices,
  generateToHistory,
  type LanguageOption,
  revealHistory,
  saveHistory,
  saveUiPrefs,
  type UiPrefs,
} from "./api";
import { downloadBlobAsFile, StreamingAudioEngine } from "./audio-engine";
import { AboutTab } from "./components/AboutTab";
import {
  AdvancedGeneration,
  DEFAULT_TEMPERATURE,
} from "./components/AdvancedGeneration";
import {
  SidebarFooter,
  UpdateBanner,
  UpdateDialog,
} from "./components/AppUpdate";
import { AudioPlayerBar } from "./components/AudioPlayerBar";
import { BatchTab } from "./components/BatchTab";
import { ConversationTab } from "./components/ConversationTab";
import { Header } from "./components/Header";
import { HistoryList } from "./components/HistoryList";
import { HistoryStorageNote } from "./components/HistoryStorageNote";
import { InfoTip } from "./components/InfoTip";
import { LoadingScreen } from "./components/LoadingScreen";
import { PdfReaderTab } from "./components/PdfReaderTab";
import { PronunciationDictionaryModal } from "./components/PronunciationDictionary";
import { SavedFileToast } from "./components/SavedFileToast";
import { SettingsModal } from "./components/SettingsModal";
import { TermsGate } from "./components/TermsGate";
import { TextEditor } from "./components/TextEditor";
import { VoiceCloningTab } from "./components/VoiceCloningTab";
import { VoiceSelector } from "./components/VoiceSelector";
import {
  downloadHistoryAudio,
  entryBlob,
  entryFileBase,
  entrySubtitles,
  fromServer,
  srtBlob,
} from "./history";
import { LanguageSelect, ModelCapsProvider } from "./model-caps";
import { pauseOtherAudio, toggleAudioPlayback } from "./playback";
import { startStartupPolling } from "./startup-polling";
import type {
  ActiveTab,
  AppSettings,
  ConnectionStatus,
  HistoryEntry,
  PlaybackStatus,
  VoiceOption,
} from "./types";

const getInitialApiUrl = (): string => {
  // Vite dev (cổng 1420, mở bằng localhost hay 127.0.0.1) không có backend - trước chỉ
  // loại "http://localhost:1420" nên mở bằng 127.0.0.1 kẹt màn hình chờ.
  if (
    !import.meta.env.DEV &&
    typeof window !== "undefined" &&
    window.location.origin &&
    !window.location.origin.startsWith("file:")
  ) {
    return window.location.origin;
  }
  return env.API_URL || "http://127.0.0.1:8001";
};

const DEFAULT_SETTINGS: AppSettings = {
  apiUrl: getInitialApiUrl(),
  playbackSpeed: 1.0,
  autoPlayOnGenerate: true,
  sampleRate: 48_000,
  silenceDuration: 0.2,
};

const DEFAULT_TEXT =
  "Xin chào các bạn! Chào mừng đến với CIT Voice Studio. Đây là giải pháp trí tuệ nhân tạo tổng hợp giọng nói tiếng Việt với chất lượng phòng thu 48kHz, hỗ trợ đầy đủ các tính năng: Voice Cloning, Podcast đa người nói và đọc tài liệu PDF.";
// Doan mau khi dang dung mo hinh giong nuoc ngoai (Supertonic, mac dinh tieng Anh).
const DEFAULT_TEXT_FOREIGN =
  "Hello and welcome to CIT Voice Studio. This voice runs entirely on your computer, with no internet connection needed. Choose a language and a voice, then press the button to listen.";

// Seed dùng khi bật "Ổn định". Cố định (không ngẫu nhiên) để mở lại app vẫn ra
// đúng bản cũ; đổi giá trị này sẽ đổi giọng của mọi bản "Ổn định" về sau.
const STABLE_SEED = 20_251_021;

export const TtsStudio: React.FC = () => {
  useEffect(() => {
    const frame = requestAnimationFrame(() =>
      document.getElementById("bootstrap-screen")?.remove()
    );
    return () => cancelAnimationFrame(frame);
  }, []);
  // Điều hướng và các tab
  const [activeTab, setActiveTab] = useState<ActiveTab>("tts");
  const [restoredConversation, setRestoredConversation] = useState<{
    key: number;
    script: string;
  } | null>(null);

  // Cài đặt và giao diện sáng/tối
  const [settings, setSettings] = useState<AppSettings>(() => {
    const saved = localStorage.getItem("cit_voice_settings");
    return saved
      ? { ...DEFAULT_SETTINGS, ...JSON.parse(saved) }
      : DEFAULT_SETTINGS;
  });

  const [isDark, setIsDark] = useState<boolean>(() => {
    return (
      localStorage.getItem("cit_voice_theme") === "dark" ||
      window.matchMedia("(prefers-color-scheme: dark)").matches
    );
  });
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [settingsSection, setSettingsSection] = useState<
    "models" | undefined
  >();
  const [isDictionaryOpen, setIsDictionaryOpen] = useState(false);

  // Trạng thái máy chủ và màn hình khởi động
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("connecting");
  const [engineName, setEngineName] = useState<string>("VieNeu-TTS v3 Turbo");
  const [isInitialLoading, setIsInitialLoading] = useState<boolean>(true);
  const [loadingMessage, setLoadingMessage] = useState<string>(
    "Đang khởi động backend và nạp model..."
  );
  const [loadingState, setLoadingState] = useState<
    "starting" | "downloading" | "ready" | "failed"
  >("starting");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  // Phien ban + ban moi: hoi mot lan khi server san sang (server tu gioi han 1 lan/ngay).
  const [appUpdate, setAppUpdate] = useState<AppUpdateInfo | null>(null);
  const [updateDismissed, setUpdateDismissed] = useState(false);
  const [updateDialogOpen, setUpdateDialogOpen] = useState(false);
  const closeUpdateDialog = useCallback(() => setUpdateDialogOpen(false), []);
  // Người dùng tự bấm kiểm tra: có bản mới thì luôn mở hộp thoại, kể cả bản đã "Để sau".
  const handleUpdateChecked = useCallback((info: AppUpdateInfo) => {
    setAppUpdate(info);
    setUpdateDismissed(false);
    if (info.newer) {
      setUpdateDialogOpen(true);
    }
  }, []);

  // Dữ liệu đọc văn bản
  const [voices, setVoices] = useState<VoiceOption[]>([]);
  // Kha nang cua mo hinh dang chay (tu /health): ngon ngu doc duoc, co nhan ban khong.
  const [modelLanguages, setModelLanguages] = useState<LanguageOption[]>([]);
  const [supportsCloning, setSupportsCloning] = useState(true);
  const [supportsEmotions, setSupportsEmotions] = useState(true);
  const [selectedVoiceId, setSelectedVoiceId] = useState<string>("");
  // Giọng mở sẵn đã áp, để đổi danh sách giọng (vừa nhân bản...) không kéo lựa chọn
  // của người dùng về lại giọng này. Đổi mô hình thì xoá để áp lại.
  const appliedDefaultVoice = useRef("");
  const [text, setText] = useState<string>(DEFAULT_TEXT);
  const [speed, setSpeed] = useState<number>(1.0);
  const [temperature, setTemperature] = useState(DEFAULT_TEMPERATURE);
  const [volume, setVolume] = useState<number>(1.0);

  // Trạng thái âm thanh và phát lại
  const [playbackStatus, setPlaybackStatus] = useState<PlaybackStatus>("idle");
  const [ttfaMs, setTtfaMs] = useState<number | null>(null);
  const [genProgress, setGenProgress] = useState<{
    elapsedMs: number;
    percent: number;
  } | null>(null);
  const [currentAudioBlobUrl, setCurrentAudioBlobUrl] = useState<string | null>(
    null
  );
  const [currentAudioBlob, setCurrentAudioBlob] = useState<Blob | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  // Tao kem phu de .srt (doc theo tung cau de do moc thoi gian that).
  const [withSubtitles, setWithSubtitles] = useState(false);
  // "Ổn định": seed cố định nên cùng văn bản + giọng ra y hệt nhau, kể cả sau khi
  // mở lại app. Mặc định tắt để giữ cách đọc cũ (mỗi lần một ngữ điệu).
  const [stableVoice, setStableVoice] = useState(false);
  // Kokoro đọc lần nào cũng như nhau: ẩn "Ổn định" và không gửi seed.
  const [supportsSeed, setSupportsSeed] = useState(true);
  const [currentSubtitles, setCurrentSubtitles] = useState<string | null>(null);
  // Muc dang phat: chan ket qua tai cham (blob/SRT cua muc cu) ghi de len muc moi.
  const currentEntryIdRef = useRef<string | null>(null);
  const [currentAudioEntry, setCurrentAudioEntry] =
    useState<HistoryEntry | null>(null);
  const [isAudioPlaying, setIsAudioPlaying] = useState(false);
  const sharedAudioRef = useRef<HTMLAudioElement | null>(null);

  // Tham chiếu bộ phát và yêu cầu đang chạy
  const audioEngineRef = useRef<StreamingAudioEngine>(
    new StreamingAudioEngine(48_000)
  );
  const abortControllerRef = useRef<AbortController | null>(null);
  const genTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(
    () => () => {
      abortControllerRef.current?.abort();
      abortControllerRef.current = null;
      if (genTimerRef.current) {
        clearInterval(genTimerRef.current);
        genTimerRef.current = null;
      }
    },
    []
  );

  // Đồng bộ lớp giao diện tối trên tài liệu HTML
  useEffect(() => {
    const root = document.documentElement;
    if (isDark) {
      root.classList.add("dark");
      localStorage.setItem("cit_voice_theme", "dark");
    } else {
      root.classList.remove("dark");
      localStorage.setItem("cit_voice_theme", "light");
    }
  }, [isDark]);

  // Tuỳ chọn giao diện đã lưu ở máy chủ. App desktop (PyWebView chế độ riêng tư)
  // xoá localStorage mỗi lần tắt, nên localStorage chỉ là giá trị tạm lúc mở; file
  // trên đĩa mới là bản gốc. Chỉ đọc một lần khi mở app.
  const prefsApiUrl = useRef(settings.apiUrl);
  useEffect(() => {
    const controller = new AbortController();
    fetchUiPrefs(prefsApiUrl.current, controller.signal)
      .then((prefs) => {
        if (prefs.theme) {
          setIsDark(prefs.theme === "dark");
        }
        const { theme: _theme, ...rest } = prefs;
        if (Object.keys(rest).length > 0) {
          setSettings((prev) => {
            const next = { ...prev, ...rest };
            localStorage.setItem("cit_voice_settings", JSON.stringify(next));
            return next;
          });
        }
      })
      .catch(() => {
        // Máy chủ cũ / chưa chạy: giữ giá trị trong localStorage.
      });
    return () => controller.abort();
  }, []);

  const persistUiPrefs = useCallback(
    (prefs: UiPrefs) => {
      saveUiPrefs(settings.apiUrl, prefs).catch(() => {
        // Không lưu được xuống đĩa thì vẫn còn localStorage cho phiên này.
      });
    },
    [settings.apiUrl]
  );

  // Tuỳ chọn và danh sách giọng về không theo thứ tự cố định, nên chờ đủ cả hai. Giọng
  // không có trong mô hình này thì giữ giọng mặc định của mô hình.
  useEffect(() => {
    const voiceId = settings.defaultVoiceId;
    if (
      voiceId &&
      voiceId !== appliedDefaultVoice.current &&
      voices.some((voice) => voice.id === voiceId)
    ) {
      appliedDefaultVoice.current = voiceId;
      setSelectedVoiceId(voiceId);
    }
  }, [settings.defaultVoiceId, voices]);

  // Thêm vào lịch sử
  const handleAddHistory = (entry: HistoryEntry) => {
    setHistory((prev) => [entry, ...prev]);
    currentEntryIdRef.current = entry.id;
    setCurrentAudioEntry(entry);
    setCurrentAudioBlobUrl(entry.audioBlobUrl);
    setCurrentAudioBlob(entry.audioBlob ?? null);
    setCurrentSubtitles(entry.subtitles ?? null);
    if (!entry.audioBlob) {
      return;
    }
    // Luu xuong o dia qua server de con lai sau khi tat app. Loi thi van giu trong
    // phien hien tai, chi mat khi tat app.
    saveHistory(settings.apiUrl, {
      audio: entry.audioBlob,
      durationSeconds: entry.durationSeconds,
      format: entry.format ?? "wav",
      mode: entry.mode ?? "tts",
      subtitles: entry.subtitles,
      text: entry.text,
      voiceId: entry.voiceId,
      voiceName: entry.voiceName,
    })
      .then((saved) =>
        setHistory((prev) =>
          prev.map((e) =>
            e.id === entry.id ? { ...e, serverId: saved.id } : e
          )
        )
      )
      .catch((e) => console.warn("[History] Không lưu được lịch sử:", e));
  };

  const loadHistory = useCallback(async (apiUrl: string) => {
    try {
      const saved = (await fetchHistory(apiUrl)).map((e) =>
        fromServer(apiUrl, e)
      );
      // Giu muc chua luu kip (dang luu / luu loi) o dau danh sach.
      setHistory((prev) => [...prev.filter((e) => !e.serverId), ...saved]);
    } catch (e) {
      console.warn("[History] Không đọc được lịch sử đã lưu:", e);
    }
  }, []);

  const handlePlayHistory = (entry: HistoryEntry) => {
    const audio = sharedAudioRef.current;
    if (audio && currentAudioBlobUrl === entry.audioBlobUrl) {
      void toggleAudioPlayback(audio);
      return;
    }
    audio?.pause();
    setIsAudioPlaying(false);
    currentEntryIdRef.current = entry.id;
    setCurrentAudioEntry(entry);
    setCurrentAudioBlobUrl(entry.audioBlobUrl);
    setCurrentAudioBlob(entry.audioBlob ?? null);
    setCurrentSubtitles(entry.subtitles ?? null);
    setTtfaMs(null);
    // Muc nap tu o dia: KHONG tai ca khoi audio ve trinh duyet (ban ~2 gio lam
    // cua so trang) - nut WAV/MP3 tai thang tu file qua downloadHistoryAudio.
    if (!(entry.audioBlob || entry.serverId)) {
      entryBlob(entry)
        .then((blob) => {
          if (currentEntryIdRef.current === entry.id) {
            setCurrentAudioBlob(blob);
          }
        })
        .catch((e) => console.warn("[History]", e));
    }
    if (!entry.subtitles && entry.subtitlesUrl) {
      entrySubtitles(entry).then((srt) => {
        if (currentEntryIdRef.current === entry.id) {
          setCurrentSubtitles(srt);
        }
      });
    }
  };

  const clearCurrentAudio = () => {
    sharedAudioRef.current?.pause();
    setIsAudioPlaying(false);
    currentEntryIdRef.current = null;
    setCurrentSubtitles(null);
    setCurrentAudioEntry(null);
    setCurrentAudioBlobUrl(null);
    setCurrentAudioBlob(null);
    setTtfaMs(null);
  };

  const [connectionAttempt, setConnectionAttempt] = useState(0);
  const restartConnection = useCallback(() => {
    setIsInitialLoading(true);
    setConnectionAttempt((attempt) => attempt + 1);
  }, []);

  useEffect(() => {
    setConnectionStatus("connecting");
    setLoadingState("starting");
    setLoadingMessage("Đang kết nối tới dịch vụ giọng nói...");
    setErrorMessage(null);

    return startStartupPolling({
      check: async (signal) => {
        const health = await checkServerHealth(settings.apiUrl, signal);
        if (signal.aborted) {
          return "failed";
        }
        setErrorMessage(null);
        setEngineName(health.engine || "VieNeu-TTS v3 Turbo");
        setConnectionStatus("connecting");

        if (health.status === "loading") {
          setLoadingState("starting");
          setLoadingMessage(health.message || "Đang nạp mô hình giọng nói...");
          return "loading";
        }
        if (health.status === "error") {
          const message = health.message || "Không nạp được mô hình giọng nói.";
          setConnectionStatus("disconnected");
          setLoadingState("failed");
          setLoadingMessage(message);
          setErrorMessage(message);
          return "failed";
        }
        if (health.status !== "ok") {
          throw new Error("Trạng thái máy chủ không hợp lệ.");
        }

        setLoadingMessage("Đang lấy danh sách giọng đọc...");
        const voiceList = await fetchVoices(settings.apiUrl, signal);
        if (signal.aborted) {
          return "failed";
        }
        audioEngineRef.current.setSampleRate(health.sample_rate || 48_000);
        setModelLanguages(health.languages ?? []);
        // Doi doan mau theo mo hinh, chi khi nguoi dung chua sua doan mau.
        const foreign = (health.languages ?? []).length > 0;
        setText((current) => {
          if (foreign && current === DEFAULT_TEXT) {
            return DEFAULT_TEXT_FOREIGN;
          }
          if (!foreign && current === DEFAULT_TEXT_FOREIGN) {
            return DEFAULT_TEXT;
          }
          return current;
        });
        setSupportsCloning(health.supports_cloning ?? true);
        setSupportsEmotions(health.supports_emotions ?? true);
        setSupportsSeed(health.supports_seed ?? true);
        setSettings((previous) => ({
          ...previous,
          sampleRate: health.sample_rate || 48_000,
        }));
        setVoices(voiceList);
        setSelectedVoiceId((previous) =>
          voiceList.some((voice) => voice.id === previous)
            ? previous
            : (voiceList[0]?.id ?? "")
        );
        setConnectionStatus("connected");
        setLoadingState("ready");
        setErrorMessage(null);
        setIsInitialLoading(false);
        loadHistory(settings.apiUrl);
        return "ready";
      },
      onConnectionError: (error, willRetry) => {
        console.warn("[Frontend] Kết nối thất bại:", error);
        setConnectionStatus(willRetry ? "connecting" : "disconnected");
        setLoadingState(willRetry ? "starting" : "failed");
        const message = willRetry
          ? "Dịch vụ giọng nói chưa phản hồi. Ứng dụng đang tự kết nối lại..."
          : `Không thể kết nối tới ${settings.apiUrl}. Hãy bấm Thử lại hoặc kiểm tra địa chỉ trong Cài đặt.`;
        setLoadingMessage(message);
        setErrorMessage(willRetry ? null : message);
      },
    });
  }, [settings.apiUrl, connectionAttempt]);

  // Giọng tuỳ chỉnh đã được server lưu thật (xem VoiceCloningTab) - chỉ cần nạp
  // lại danh sách rồi chọn nó, không còn bookmark giả ở localStorage nữa.
  const handleAddCustomVoice = async (voiceId: string) => {
    const voiceList = await fetchVoices(settings.apiUrl);
    if (!voiceList.some((voice) => voice.id === voiceId)) {
      throw new Error(
        "Chưa tìm thấy giọng vừa lưu trên máy chủ. Vui lòng tải lại danh sách giọng."
      );
    }
    setVoices(voiceList);
    setSelectedVoiceId(voiceId);
  };

  // Xoá giọng nhân bản đã lưu rồi nạp lại danh sách. Giọng đang chọn bị xoá thì
  // chuyển về giọng đầu danh sách; các tab khác nhận danh sách mới qua `voices`.
  const handleDeleteCustomVoice = async (voiceId: string) => {
    await deleteCustomVoice(settings.apiUrl, voiceId);
    const voiceList = await fetchVoices(settings.apiUrl);
    setVoices(voiceList);
    setSelectedVoiceId((previous) =>
      voiceList.some((voice) => voice.id === previous)
        ? previous
        : (voiceList[0]?.id ?? "")
    );
  };

  // Chế độ tạo giọng dạng batch không có tiến độ thật từ server (một request
  // chờ đến khi xong), nên ước lượng theo độ dài văn bản + RTF điển hình của
  // engine đang dùng, để thanh tiến độ phản ánh gần đúng thay vì chỉ là spinner.
  const uocLuongMsXuLy = (soKyTu: number): number => {
    // Speed được áp dụng sau suy luận, không làm mô hình tạo âm thanh nhanh hơn.
    const giayNoi = soKyTu / 15;
    const ten = engineName.toLowerCase();
    let rtf = 0.5; // CPU int8, mặc định thận trọng
    if (ten.includes("gpu")) {
      rtf = 0.15;
    } else if (ten.includes("fp32")) {
      rtf = 0.6;
    }
    return Math.max(300, giayNoi * rtf * 1000);
  };

  // Handle Generate Full Audio (Tạo xong mới phát, không giật)
  const handleGenerateOrPlay = async () => {
    if (!text.trim()) {
      setErrorMessage(
        "Vui lòng nhập nội dung văn bản cần chuyển thành giọng nói!"
      );
      return;
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setPlaybackStatus("generating");
    setTtfaMs(null);
    setErrorMessage(null);

    const startTime = performance.now();
    const estimatedMs = uocLuongMsXuLy(text.trim().length);
    setGenProgress({ elapsedMs: 0, percent: 0 });
    if (genTimerRef.current) {
      clearInterval(genTimerRef.current);
    }
    genTimerRef.current = setInterval(() => {
      const elapsedMs = performance.now() - startTime;
      setGenProgress({
        elapsedMs,
        percent: Math.min(95, 100 * (1 - Math.exp(-elapsedMs / estimatedMs))),
      });
    }, 100);

    try {
      const selectedVoice = voices.find((v) => v.id === selectedVoiceId);
      // Server tạo xong thì tự lưu vào lịch sử trên ổ đĩa; trình duyệt chỉ nhận
      // mục lịch sử và phát/tải qua URL, không giữ cả khối audio (bài ~2 giờ làm
      // cửa sổ app trắng - xem generateToHistory).
      const res = await generateToHistory(
        settings.apiUrl,
        {
          text: text.trim(),
          voiceId: selectedVoiceId,
          voiceName: selectedVoice ? selectedVoice.name : selectedVoiceId,
          speed,
          temperature,
          silenceDuration: settings.silenceDuration ?? 0.2,
          subtitles: withSubtitles,
          seed: stableVoice && supportsSeed ? STABLE_SEED : undefined,
        },
        controller.signal
      );

      if (
        controller.signal.aborted ||
        abortControllerRef.current !== controller
      ) {
        return;
      }
      const elapsedMs = Math.round(performance.now() - startTime);
      setTtfaMs(elapsedMs);

      // Mục không có audioBlob: handleAddHistory không tải ngược audio lên nữa.
      handleAddHistory({
        ...fromServer(settings.apiUrl, res.entry),
        subtitles: res.srt ?? undefined,
      });

      setPlaybackStatus("idle");
    } catch (err: any) {
      if (abortControllerRef.current !== controller) {
        return;
      }
      if (err.name === "AbortError") {
        setPlaybackStatus("idle");
      } else {
        console.error("[TTS Error]", err);
        setPlaybackStatus("error");
        setErrorMessage(err.message || "Lỗi trong quá trình tạo giọng nói");
      }
    } finally {
      // Yêu cầu đã huỷ không được xoá tiến trình của yêu cầu mới hơn.
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
        if (genTimerRef.current) {
          clearInterval(genTimerRef.current);
          genTimerRef.current = null;
        }
        setGenProgress(null);
      }
    }
  };

  // Dừng tạo hoặc phát luồng âm thanh
  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (genTimerRef.current) {
      clearInterval(genTimerRef.current);
      genTimerRef.current = null;
    }
    setGenProgress(null);
    audioEngineRef.current.stop();
    setPlaybackStatus("idle");
  };

  // Ten goc chung cho WAV / MP3 / SRT cua cung mot ban audio: phan mem dung video
  // tu ghep phu de khi file .srt trung ten voi file audio.
  const currentFileBase = () => {
    if (currentAudioEntry) {
      return entryFileBase(currentAudioEntry);
    }
    const selectedVoice = voices.find((v) => v.id === selectedVoiceId);
    return `cit_tts_${selectedVoice ? selectedVoice.name : "voice"}_${Date.now()}`;
  };

  // Mục đã lưu trên đĩa: tải thẳng từ file, không qua trình duyệt.
  const downloadFromDisk = (fmt: "wav" | "mp3") => {
    const id = currentAudioEntry?.serverId;
    if (!id) {
      return false;
    }
    downloadHistoryAudio(
      settings.apiUrl,
      id,
      `${currentFileBase()}.${fmt}`,
      fmt
    ).catch((e) => setErrorMessage(e instanceof Error ? e.message : String(e)));
    return true;
  };

  // Tải WAV
  const handleDownloadWav = () => {
    if (currentAudioBlob) {
      downloadBlobAsFile(currentAudioBlob, `${currentFileBase()}.wav`);
      return;
    }
    downloadFromDisk("wav");
  };

  const handleDownloadSrt = () => {
    if (currentSubtitles) {
      downloadBlobAsFile(srtBlob(currentSubtitles), `${currentFileBase()}.srt`);
    }
  };

  // Tải MP3
  const handleDownloadMp3 = async () => {
    if (!currentAudioBlob) {
      downloadFromDisk("mp3");
      return;
    }
    try {
      const mp3Blob = await convertToMp3(settings.apiUrl, currentAudioBlob);
      downloadBlobAsFile(mp3Blob, `${currentFileBase()}.mp3`);
    } catch {
      handleDownloadWav();
    }
  };

  // Chuyển nội dung từ tab đọc file
  const handleSendToTtsFromPdf = (extractedText: string) => {
    setText(extractedText);
    setActiveTab("tts");
  };

  const handleSendToConversationFromPdf = () => {
    setActiveTab("conversation");
  };

  // Tên giọng đang chọn trên thanh trạng thái
  useEffect(() => {
    if (connectionStatus !== "connected" || appUpdate) {
      return;
    }
    const controller = new AbortController();
    checkAppUpdate(settings.apiUrl, false, controller.signal)
      .then((info) => {
        setAppUpdate(info);
        // Tự kiểm tra lúc mở app: chỉ bật hộp thoại một lần cho mỗi bản.
        if (info.newer && !info.skipped) {
          setUpdateDialogOpen(true);
        }
      })
      .catch(() => undefined); // mat mang / backend cu: im lang
    return () => controller.abort();
  }, [connectionStatus, settings.apiUrl, appUpdate]);

  const selectedVoiceName =
    voices.find((v) => v.id === selectedVoiceId)?.name ||
    selectedVoiceId ||
    "Mặc định";

  const isGenerating =
    playbackStatus === "generating" || playbackStatus === "streaming";

  return (
    <ModelCapsProvider
      languages={modelLanguages}
      supportsCloning={supportsCloning}
      supportsEmotions={supportsEmotions}
    >
      <div
        className="flex h-screen select-none flex-col overflow-hidden bg-background font-sans text-foreground"
        onPlayCapture={(event) => {
          if (event.target instanceof HTMLAudioElement) {
            pauseOtherAudio(
              event.target,
              event.currentTarget.querySelectorAll("audio")
            );
          }
        }}
      >
        <TermsGate apiUrl={settings.apiUrl} />

        {/* Thanh đầu trang */}
        <Header
          engineName={engineName}
          isDark={isDark}
          onOpenSettings={() => {
            setSettingsSection("models");
            setIsSettingsOpen(true);
          }}
          onRefresh={restartConnection}
          onToggleDark={() => {
            setIsDark(!isDark);
            persistUiPrefs({ theme: isDark ? "light" : "dark" });
          }}
          sampleRate={settings.sampleRate}
          status={connectionStatus}
        />

        {/* Thông báo lỗi chung */}
        {errorMessage && (
          <div className="slide-in-from-top-2 mx-6 mt-3 flex animate-in items-center justify-between rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-rose-600 text-xs shadow-sm dark:text-rose-400">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
            <button
              className="rounded-lg p-1 transition-colors hover:bg-rose-500/20"
              onClick={() => setErrorMessage(null)}
              type="button"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {!updateDismissed && (
          <UpdateBanner
            info={appUpdate}
            onDismiss={() => setUpdateDismissed(true)}
          />
        )}

        <div className="studio-body">
          <nav aria-label="Chức năng" className="studio-sidebar">
            <div className="studio-nav-groups">
              {[
                {
                  title: "Tạo",
                  items: [
                    { tab: "tts", label: "Đọc văn bản", icon: Mic },
                    { tab: "conversation", label: "Hội thoại", icon: Users },
                    {
                      tab: "pdf",
                      label: "Đọc file, lồng tiếng",
                      icon: FileText,
                    },
                    { tab: "batch", label: "Tạo hàng loạt", icon: ListOrdered },
                    { tab: "clone", label: "Nhân bản giọng", icon: Sparkles },
                  ],
                },
                {
                  title: "Thư viện",
                  items: [
                    {
                      tab: "dictionary",
                      label: "Từ điển phát âm",
                      icon: BookOpen,
                    },
                    { tab: "history", label: "Bản đã tạo", icon: History },
                  ],
                },
                {
                  title: "Hệ thống",
                  items: [
                    { tab: "settings", label: "Cài đặt", icon: Settings },
                    {
                      tab: "about",
                      label: "Thông tin và bản quyền",
                      icon: Info,
                    },
                  ],
                },
              ].map((group) => (
                <div className="studio-nav-group" key={group.title}>
                  <h2>{group.title}</h2>
                  {group.items.map((item) => (
                    <button
                      aria-current={activeTab === item.tab ? "page" : undefined}
                      className="studio-nav-item"
                      key={item.tab}
                      onClick={() => {
                        if (item.tab === "dictionary") {
                          setIsDictionaryOpen(true);
                        } else if (item.tab === "settings") {
                          setSettingsSection(undefined);
                          setIsSettingsOpen(true);
                        } else {
                          setActiveTab(item.tab as ActiveTab);
                        }
                      }}
                      type="button"
                    >
                      <item.icon aria-hidden="true" size={16} />
                      <span>{item.label}</span>
                      {item.tab === "history" && (
                        <span className="studio-nav-count">
                          {history.length}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              ))}
            </div>
            <SidebarFooter
              apiUrl={settings.apiUrl}
              info={appUpdate}
              onChecked={handleUpdateChecked}
            />
          </nav>
          <div
            className={`studio-workspace ${activeTab === "tts" ? "studio-workspace-tts" : ""}`}
          >
            {/* Vùng làm việc của từng tab */}
            <main className="studio-main">
              {/* Tab đọc văn bản một giọng */}
              {activeTab === "tts" && (
                <div className="studio-tts-layout">
                  {/* Cột giữa: văn bản và công cụ cảm xúc */}
                  <div className="studio-editor-area">
                    <TextEditor
                      disabled={isGenerating}
                      onChange={setText}
                      onOpenDictionary={() => setIsDictionaryOpen(true)}
                      text={text}
                    />
                  </div>

                  {/* Panel phải: giọng đọc và tuỳ chọn tạo */}
                  <div className="studio-properties">
                    <LanguageSelect
                      className="rounded-xl border border-border/80 bg-card px-3 py-2 shadow-sm"
                      disabled={isGenerating}
                    />
                    <div className="min-h-0 flex-1">
                      <VoiceSelector
                        apiUrl={settings.apiUrl}
                        disabled={isGenerating}
                        onChangeSpeed={(s) => {
                          setSpeed(s);
                          audioEngineRef.current.setPlaybackRate(s);
                        }}
                        onCloneVoice={() => setActiveTab("clone")}
                        onDeleteVoice={handleDeleteCustomVoice}
                        onSelectVoice={setSelectedVoiceId}
                        selectedVoiceId={selectedVoiceId}
                        speed={speed}
                        voices={voices}
                      />
                    </div>
                    <details className="studio-generation-options">
                      <summary className="cursor-pointer py-2 font-semibold text-sm">
                        Tuỳ chọn nâng cao
                      </summary>
                      <AdvancedGeneration
                        disabled={isGenerating}
                        onChangeTemperature={setTemperature}
                        temperature={temperature}
                      />
                      <label className="studio-switch-row">
                        <span className="flex items-center gap-1">
                          Kèm phụ đề .srt
                          <InfoTip label="Kèm phụ đề">
                            <strong>Tạo kèm file .srt</strong>
                            <span>
                              Mốc thời gian theo từng câu, để dựng video.
                            </span>
                            <span>Tải ở Xuất file → SRT.</span>
                          </InfoTip>
                        </span>
                        <input
                          checked={withSubtitles}
                          className="studio-switch"
                          disabled={isGenerating}
                          onChange={(event) =>
                            setWithSubtitles(event.target.checked)
                          }
                          type="checkbox"
                        />
                      </label>
                      {supportsSeed && (
                        <label className="studio-switch-row">
                          <span className="flex items-center gap-1">
                            Ổn định (giữ giọng giống nhau)
                            <InfoTip label="Ổn định">
                              <strong>Bật: tạo lại ra y hệt lần trước</strong>
                              <span>
                                Kể cả chỗ đọc lỗi - gặp lỗi thì tắt rồi tạo lại.
                              </span>
                              <span>
                                Tắt (mặc định): mỗi lần ngữ điệu hơi khác.
                              </span>
                            </InfoTip>
                          </span>
                          <input
                            checked={stableVoice}
                            className="studio-switch"
                            disabled={isGenerating}
                            onChange={(event) =>
                              setStableVoice(event.target.checked)
                            }
                            type="checkbox"
                          />
                        </label>
                      )}
                    </details>
                    <div className="studio-generate-area">
                      <button
                        className="studio-primary studio-generate"
                        data-busy={isGenerating || undefined}
                        disabled={
                          connectionStatus !== "connected" || isGenerating
                        }
                        onClick={handleGenerateOrPlay}
                        type="button"
                      >
                        <Sparkles size={16} />
                        {isGenerating ? "Đang tạo…" : "Tạo giọng đọc"}
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Tab nhân bản giọng */}
              <div hidden={activeTab !== "clone"}>
                <VoiceCloningTab
                  apiUrl={settings.apiUrl}
                  isActive={activeTab === "clone"}
                  onAddCustomVoice={handleAddCustomVoice}
                  onAddHistory={handleAddHistory}
                />
              </div>

              {/* Tab hội thoại nhiều người nói */}
              <div hidden={activeTab !== "conversation"}>
                <ConversationTab
                  active={activeTab === "conversation"}
                  apiUrl={settings.apiUrl}
                  onAddHistory={handleAddHistory}
                  restoredScript={restoredConversation}
                  voices={voices}
                />
              </div>

              {/* Tab 4: PDF Reader + long tieng SRT. Giu trong DOM (chi an): go ra khi doi
            tab se huy luot long tieng dang chay. */}
              <div hidden={activeTab !== "pdf"}>
                <PdfReaderTab
                  apiUrl={settings.apiUrl}
                  defaultVoiceId={selectedVoiceId}
                  onAddHistory={handleAddHistory}
                  onSendToConversation={handleSendToConversationFromPdf}
                  onSendToTts={handleSendToTtsFromPdf}
                  voices={voices}
                />
              </div>

              {/* Tao hang loat: LUON giu trong DOM (chi an) - go khoi DOM khi doi tab se
            huy tien trinh dang tao va mat cac file da tao. */}
              <div hidden={activeTab !== "batch"}>
                <BatchTab
                  apiUrl={settings.apiUrl}
                  defaultVoiceId={selectedVoiceId}
                  voices={voices}
                />
              </div>

              {/* Tab các bản đã tạo */}
              {activeTab === "history" && (
                <div className="space-y-4">
                  <HistoryStorageNote
                    apiUrl={settings.apiUrl}
                    refreshKey={history.length}
                  />
                  <HistoryList
                    items={history}
                    onClearAll={async () => {
                      // biome-ignore lint/suspicious/noAlert: xác nhận trước khi xóa toàn bộ file đã lưu
                      const confirmed = window.confirm(
                        "Xóa toàn bộ bản đã tạo và các file audio đã lưu?"
                      );
                      if (!confirmed) {
                        return;
                      }
                      const ids = new Set(history.map((item) => item.id));
                      try {
                        await clearHistory(settings.apiUrl);
                        if (
                          currentEntryIdRef.current &&
                          ids.has(currentEntryIdRef.current)
                        ) {
                          clearCurrentAudio();
                        }
                        setHistory((prev) =>
                          prev.filter((item) => !ids.has(item.id))
                        );
                      } catch {
                        setErrorMessage(
                          "Không xóa được các bản đã tạo. Vui lòng thử lại."
                        );
                      }
                    }}
                    onDeleteItem={async (id) => {
                      const item = history.find((h) => h.id === id);
                      try {
                        if (item?.serverId) {
                          await deleteHistory(settings.apiUrl, item.serverId);
                        }
                        if (currentEntryIdRef.current === id) {
                          clearCurrentAudio();
                        }
                        setHistory((prev) => prev.filter((h) => h.id !== id));
                      } catch {
                        setErrorMessage(
                          "Không xóa được bản này. Vui lòng thử lại."
                        );
                      }
                    }}
                    onDownloadItem={(item) => {
                      if (item.serverId && !item.audioBlob) {
                        downloadHistoryAudio(
                          settings.apiUrl,
                          item.serverId,
                          `${entryFileBase(item)}.${item.format ?? "wav"}`,
                          item.format ?? "wav"
                        ).catch((e) =>
                          setErrorMessage(
                            e instanceof Error ? e.message : String(e)
                          )
                        );
                        return;
                      }
                      entryBlob(item)
                        .then((blob) =>
                          downloadBlobAsFile(
                            blob,
                            `${entryFileBase(item)}.${item.format ?? "wav"}`
                          )
                        )
                        .catch((e) => console.warn("[History]", e));
                    }}
                    onPlayItem={handlePlayHistory}
                    onRestoreText={(item) => {
                      if (item.mode === "conversation") {
                        setRestoredConversation({
                          key: Date.now(),
                          script: item.text,
                        });
                        setActiveTab("conversation");
                        return;
                      }
                      setText(item.text);
                      setActiveTab("tts");
                    }}
                    onRevealItem={(item) => {
                      if (!item.serverId) {
                        return;
                      }
                      revealHistory(settings.apiUrl, item.serverId).catch((e) =>
                        // biome-ignore lint/suspicious/noAlert: bao loi ngan gon, hiem khi xay ra
                        window.alert(e instanceof Error ? e.message : String(e))
                      );
                    }}
                    playingId={
                      isAudioPlaying ? (currentAudioEntry?.id ?? null) : null
                    }
                  />
                </div>
              )}

              {/* Tab thông tin và bản quyền */}
              {activeTab === "about" && (
                <AboutTab
                  apiUrl={settings.apiUrl}
                  engineName={engineName}
                  onUpdateChecked={handleUpdateChecked}
                  sampleRate={settings.sampleRate}
                  update={appUpdate}
                />
              )}
            </main>

            {/* Trình phát dùng chung, giữ nguyên trong DOM khi đổi tab */}
            {/* Chi hien o tab Tao giong (soan + tao) va Lich su (nghe/tai lai). Cac tab
          nhan ban, hoi thoai, hang loat co nut tao + trinh phat rieng; nut "Tao giong
          noi" o day doc van ban tab Tao giong nen de bam nham. Van hien khi dang tao
          (con nut "Dung tao") hoac dang phat (con nut tam dung). */}
            <footer
              className="studio-player"
              hidden={
                !(
                  activeTab === "tts" ||
                  activeTab === "history" ||
                  playbackStatus === "generating" ||
                  isAudioPlaying
                )
              }
            >
              <AudioPlayerBar
                audioBlob={currentAudioBlob}
                audioBlobUrl={currentAudioBlobUrl}
                audioRef={sharedAudioRef}
                canDownload={Boolean(currentAudioEntry?.serverId)}
                disabled={connectionStatus !== "connected"}
                getVisualizerData={() =>
                  audioEngineRef.current.getFrequencyData()
                }
                isPlaying={isAudioPlaying}
                onChangeVolume={(v) => {
                  setVolume(v);
                  audioEngineRef.current.setVolume(v);
                }}
                onDownload={handleDownloadWav}
                onDownloadMp3={handleDownloadMp3}
                onDownloadSrt={currentSubtitles ? handleDownloadSrt : undefined}
                onGenerateOrPlay={undefined}
                onPlayingChange={setIsAudioPlaying}
                onStop={handleStop}
                playbackSpeed={speed}
                progress={genProgress}
                selectedVoiceName={
                  currentAudioEntry?.voiceName ?? selectedVoiceName
                }
                stableEnabled={stableVoice && supportsSeed}
                status={playbackStatus}
                subtitlesEnabled={withSubtitles}
                ttfaMs={ttfaMs}
                volume={volume}
              />
            </footer>
          </div>
        </div>

        <PronunciationDictionaryModal
          apiUrl={settings.apiUrl}
          isOpen={isDictionaryOpen}
          onClose={() => setIsDictionaryOpen(false)}
        />

        {/* Hộp thoại "Có bản mới". */}
        {updateDialogOpen && appUpdate?.newer && (
          <UpdateDialog
            apiUrl={settings.apiUrl}
            info={appUpdate}
            onClose={closeUpdateDialog}
          />
        )}

        {/* Thông báo "Đã lưu" sau mỗi lần lưu file (app desktop). */}
        <SavedFileToast />

        {/* Hộp thoại cài đặt */}
        <SettingsModal
          initialSection={settingsSection}
          isOpen={isSettingsOpen}
          onClose={() => setIsSettingsOpen(false)}
          onModelSwitched={(model) => {
            setEngineName(model);
            appliedDefaultVoice.current = "";
            restartConnection();
          }}
          onSaveSettings={(newSettings) => {
            setSettings(newSettings);
            localStorage.setItem(
              "cit_voice_settings",
              JSON.stringify(newSettings)
            );
            persistUiPrefs({
              autoPlayOnGenerate: newSettings.autoPlayOnGenerate,
              defaultVoiceId: newSettings.defaultVoiceId,
              playbackSpeed: newSettings.playbackSpeed,
              silenceDuration: newSettings.silenceDuration,
            });
          }}
          onUpdateChecked={handleUpdateChecked}
          settings={settings}
          voices={voices}
        />

        {/* Màn hình chờ khi khởi động */}
        {isInitialLoading && !isSettingsOpen && (
          <LoadingScreen
            isDark={isDark}
            message={loadingMessage}
            onOpenSettings={() => setIsSettingsOpen(true)}
            onRetry={restartConnection}
            status={loadingState}
          />
        )}
      </div>
    </ModelCapsProvider>
  );
};

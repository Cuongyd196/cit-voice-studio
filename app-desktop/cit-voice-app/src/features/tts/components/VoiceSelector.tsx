import {
  Check,
  Loader2,
  Play,
  Sliders,
  Square,
  Star,
  Trash2,
} from "lucide-react";
import React, { useEffect, useRef, useState } from "react";
import { fetchVoicePreview } from "../api";
import { describeVoice, useModelCaps } from "../model-caps";
import type { VoiceOption } from "../types";
import { voiceDetail } from "../voice-label";

// Mốc của thanh tốc độ.
const SPEED_MIN = 0.75;
const SPEED_MAX = 1.5;
const SPEED_NORMAL = 1.0;
const SPEED_STEP = 0.05;

/** Ép về trong khoảng và làm tròn 2 chữ số. Không làm tròn thì cộng dồn 0.05 kiểu
 *  dấu phẩy động cho ra 1.0500000000000003, hiện lên ô nhập rất xấu. */
const clampSpeed = (v: number): number => {
  if (!Number.isFinite(v)) {
    return SPEED_NORMAL;
  }
  return Math.round(Math.min(SPEED_MAX, Math.max(SPEED_MIN, v)) * 100) / 100;
};

const stepSpeed = (v: number, dir: number): number =>
  clampSpeed(v + dir * SPEED_STEP);

// Số bảng màu avatar trong global.css (.studio-voice-avatar[data-tone]).
const VOICE_TONES = 8;

/** Băm id giọng ra 0..7 để mỗi giọng luôn giữ một màu avatar. Tổng mã ký tự như
 *  trước dồn các tên gần giống nhau về cùng một màu. */
export const voiceColorIndex = (id: string): number => {
  let hash = 7;
  for (const char of id) {
    hash = (hash * 31 + (char.codePointAt(0) ?? 0)) % 2_147_483_647;
  }
  return hash % VOICE_TONES;
};

interface DeleteVoiceButtonProps {
  busy: boolean;
  disabled?: boolean;
  name: string;
  onDelete: () => void;
}

function DeleteVoiceButton({
  busy,
  disabled,
  name,
  onDelete,
}: DeleteVoiceButtonProps) {
  return (
    <button
      aria-label={`Xoá giọng ${name}`}
      className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-rose-500/10 hover:text-rose-500 disabled:opacity-40"
      disabled={disabled}
      onClick={(e) => {
        // Nut nam trong the giong: khong de cu bam xoa cung chon luon giong do.
        e.stopPropagation();
        onDelete();
      }}
      title="Xoá giọng nhân bản này (chỉ xoá được giọng của mô hình đang dùng)"
      type="button"
    >
      {busy ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        <Trash2 className="h-3.5 w-3.5" />
      )}
    </button>
  );
}

interface PreviewVoiceButtonProps {
  disabled?: boolean;
  name: string;
  onToggle: () => void;
  state: "idle" | "loading" | "playing";
}

function PreviewVoiceButton({
  disabled,
  name,
  onToggle,
  state,
}: PreviewVoiceButtonProps) {
  let icon = <Play className="h-3.5 w-3.5 fill-current" />;
  if (state === "loading") {
    icon = <Loader2 className="h-3.5 w-3.5 animate-spin" />;
  } else if (state === "playing") {
    icon = <Square className="h-3 w-3 fill-current" />;
  }
  return (
    <button
      aria-label={
        state === "idle" ? `Nghe thử giọng ${name}` : `Dừng nghe thử ${name}`
      }
      className={`flex h-7 w-7 items-center justify-center rounded-full transition-colors disabled:opacity-40 ${
        state === "idle"
          ? "text-muted-foreground hover:bg-secondary hover:text-brand-600 dark:hover:text-brand-400"
          : "bg-brand-500/10 text-brand-600 dark:text-brand-400"
      }`}
      disabled={disabled}
      onClick={(e) => {
        // Nút nằm trong thẻ giọng: nghe thử không được chọn luôn giọng đó.
        e.stopPropagation();
        onToggle();
      }}
      title={
        state === "loading"
          ? "Đang đọc mẫu (lần đầu mất vài giây)..."
          : "Nghe thử giọng này"
      }
      type="button"
    >
      {icon}
    </button>
  );
}

interface VoiceSelectorProps {
  /** Có thì hiện nút nghe thử trên từng giọng. */
  apiUrl?: string;
  disabled?: boolean;
  onChangeSpeed: (speed: number) => void;
  onCloneVoice?: () => void;
  /** Xoá giọng nhân bản đã lưu; không truyền thì không hiện nút xoá. */
  onDeleteVoice?: (voiceId: string) => Promise<void>;
  onSelectVoice: (voiceId: string) => void;
  selectedVoiceId: string;
  speed: number;
  voices: VoiceOption[];
}

export const VoiceSelector: React.FC<VoiceSelectorProps> = ({
  apiUrl,
  onCloneVoice,
  voices,
  selectedVoiceId,
  onSelectVoice,
  speed,
  onChangeSpeed,
  onDeleteVoice,
  disabled,
}) => {
  // Giong Supertonic doc moi ngon ngu: the giong ghi ngon ngu dang chon.
  const { language, languageName, languages, setLanguage } = useModelCaps();
  // Chon tieng o "Ngon ngu van ban" thi chi hien giong Kokoro cua tieng do. Giong
  // khong gan tieng (VieNeu, Supertonic, giong nhan ban) luon hien.
  const matchesLanguage = (voice: VoiceOption) =>
    !(language && voice.language) || voice.language === language;
  // Giong va tieng phai khop nhau. Ben nao vua doi thi ben kia theo:
  // - giong doi (bam chon, giong mo san trong Cai dat): tieng theo giong;
  // - tieng doi (o "Ngon ngu van ban"): chuyen sang giong dau tien cua tieng do,
  //   khong thi bam Doc van ra giong cu.
  const lastVoiceId = useRef(selectedVoiceId);
  useEffect(() => {
    const current = voices.find((v) => v.id === selectedVoiceId);
    const voiceChanged = lastVoiceId.current !== selectedVoiceId;
    lastVoiceId.current = selectedVoiceId;
    if (!(language && current?.language) || current.language === language) {
      return;
    }
    if (voiceChanged) {
      if (languages.some((l) => l.code === current.language)) {
        setLanguage(current.language);
      }
      return;
    }
    const first = voices.find((v) => v.language === language);
    if (first) {
      onSelectVoice(first.id);
    }
  }, [
    language,
    languages,
    voices,
    selectedVoiceId,
    onSelectVoice,
    setLanguage,
  ]);
  const selectVoice = (voice: VoiceOption) => onSelectVoice(voice.id);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Nghe thử: chỉ một giọng phát tại một thời điểm.
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [previewState, setPreviewState] = useState<"loading" | "playing">(
    "loading"
  );
  const [previewError, setPreviewError] = useState<string | null>(null);
  const previewAudioRef = useRef<HTMLAudioElement | null>(null);
  const previewUrlRef = useRef<string | null>(null);
  const previewAbortRef = useRef<AbortController | null>(null);

  const stopPreview = () => {
    previewAbortRef.current?.abort();
    previewAbortRef.current = null;
    if (previewAudioRef.current) {
      previewAudioRef.current.pause();
      previewAudioRef.current = null;
    }
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
    setPreviewId(null);
  };

  // biome-ignore lint/correctness/useExhaustiveDependencies: chỉ dọn khi rời trang
  useEffect(() => stopPreview, []);

  // Đang tạo giọng nói chính thì dừng nghe thử để hai âm thanh không chồng nhau.
  // biome-ignore lint/correctness/useExhaustiveDependencies: chỉ phản ứng theo disabled
  useEffect(() => {
    if (disabled) {
      stopPreview();
    }
  }, [disabled]);

  const togglePreview = async (voice: VoiceOption) => {
    const wasThis = previewId === voice.id;
    stopPreview();
    if (wasThis || !apiUrl) {
      return;
    }
    const controller = new AbortController();
    previewAbortRef.current = controller;
    setPreviewError(null);
    setPreviewId(voice.id);
    setPreviewState("loading");
    try {
      const blob = await fetchVoicePreview(apiUrl, voice.id, controller.signal);
      if (controller.signal.aborted) {
        return;
      }
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      previewUrlRef.current = url;
      previewAudioRef.current = audio;
      audio.onended = () => {
        if (previewAudioRef.current === audio) {
          stopPreview();
        }
      };
      await audio.play();
      setPreviewState("playing");
    } catch (e) {
      if (controller.signal.aborted) {
        return;
      }
      stopPreview();
      setPreviewError(
        `Không nghe thử được "${voice.name}": ${e instanceof Error ? e.message : String(e)}`
      );
    }
  };

  const handleDelete = async (voice: VoiceOption) => {
    if (
      !(
        onDeleteVoice &&
        // biome-ignore lint/suspicious/noAlert: xac nhan truoc thao tac khong hoan tac
        window.confirm(
          `Xoá giọng nhân bản "${voice.name}"?\nThao tác này không hoàn tác được.`
        )
      )
    ) {
      return;
    }
    setDeletingId(voice.id);
    setDeleteError(null);
    try {
      await onDeleteVoice(voice.id);
    } catch (e) {
      setDeleteError(
        `Không xoá được "${voice.name}": ${e instanceof Error ? e.message : String(e)}`
      );
    } finally {
      setDeletingId(null);
    }
  };
  // Tách khỏi vòng map để giữ độ phức tạp của component trong ngưỡng lint.
  const renderActions = (voice: VoiceOption, isSelected: boolean) => (
    <div className="flex items-center gap-1.5">
      {apiUrl && (
        <PreviewVoiceButton
          disabled={disabled}
          name={voice.name}
          onToggle={() => togglePreview(voice)}
          state={previewId === voice.id ? previewState : "idle"}
        />
      )}
      {onDeleteVoice && voice.isCloned && (
        <DeleteVoiceButton
          busy={deletingId === voice.id}
          disabled={disabled || deletingId !== null}
          name={voice.name}
          onDelete={() => handleDelete(voice)}
        />
      )}
      {isSelected && (
        <div className="zoom-in-50 flex h-4.5 w-4.5 animate-in items-center justify-center rounded-full bg-brand-600 text-white shadow-xs">
          <Check className="h-3 w-3 stroke-[3]" />
        </div>
      )}
    </div>
  );

  const [filterGender, setFilterGender] = useState<
    "all" | "female" | "male" | "cloned"
  >("all");

  // Ô nhập giữ bản nháp dạng chuỗi trong lúc gõ. Nếu ép kiểu số ngay từng phím thì
  // người dùng không xoá hết được để gõ lại, và "1." sẽ bị nhảy về 1 giữa chừng.
  const [speedDraft, setSpeedDraft] = useState<string>(speed.toFixed(2));
  const [speedFocused, setSpeedFocused] = useState(false);

  // Nút trượt / nút +- đổi giá trị thì ô nhập phải theo, trừ khi đang gõ dở.
  React.useEffect(() => {
    if (!speedFocused) {
      setSpeedDraft(speed.toFixed(2));
    }
  }, [speed, speedFocused]);

  const commitSpeedDraft = () => {
    setSpeedFocused(false);
    const parsed = Number.parseFloat(speedDraft.replace(",", "."));
    const next = Number.isFinite(parsed) ? clampSpeed(parsed) : speed;
    onChangeSpeed(next);
    setSpeedDraft(next.toFixed(2));
  };

  const filteredVoices = voices.filter((v) => {
    if (!matchesLanguage(v)) {
      return false;
    }
    if (filterGender === "cloned") {
      return v.isCloned;
    }
    if (filterGender === "female") {
      return v.gender === "female";
    }
    if (filterGender === "male") {
      return v.gender === "male";
    }
    return true;
  });

  const selectedRowRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (selectedVoiceId && filterGender) {
      selectedRowRef.current?.scrollIntoView({ block: "nearest" });
    }
  }, [selectedVoiceId, filterGender]);

  return (
    <div className="studio-voice-selector flex h-full flex-col">
      <div className="studio-voice-heading">
        <h2>Giọng đọc</h2>
        {onCloneVoice && (
          <button
            className="text-primary text-xs"
            onClick={onCloneVoice}
            type="button"
          >
            + Nhân bản giọng
          </button>
        )}
      </div>
      <fieldset aria-label="Lọc giọng đọc" className="studio-voice-filter">
        {(
          [
            { value: "all", label: "Tất cả" },
            { value: "male", label: "Nam" },
            { value: "female", label: "Nữ" },
            { value: "cloned", label: "Của tôi" },
          ] as const
        ).map((filter) => (
          <button
            aria-pressed={filterGender === filter.value}
            key={filter.value}
            onClick={() => setFilterGender(filter.value)}
            type="button"
          >
            {filter.label}
          </button>
        ))}
      </fieldset>

      {deleteError && (
        <div
          className="flex items-start gap-2 rounded-lg border border-rose-500/40 bg-rose-500/10 px-2.5 py-1.5 text-rose-700 text-xs dark:text-rose-300"
          role="alert"
        >
          <span className="min-w-0 flex-1">{deleteError}</span>
          <button
            aria-label="Đóng thông báo"
            className="font-bold"
            onClick={() => setDeleteError(null)}
            type="button"
          >
            ×
          </button>
        </div>
      )}

      {previewError && (
        <div
          className="flex items-start gap-2 rounded-lg border border-rose-500/40 bg-rose-500/10 px-2.5 py-1.5 text-rose-700 text-xs dark:text-rose-300"
          role="alert"
        >
          <span className="min-w-0 flex-1">{previewError}</span>
          <button
            aria-label="Đóng thông báo"
            className="font-bold"
            onClick={() => setPreviewError(null)}
            type="button"
          >
            ×
          </button>
        </div>
      )}

      {/* Danh sách giọng đọc */}
      <div className="studio-voice-list">
        {filteredVoices.length === 0 ? (
          <div className="flex h-20 flex-col items-center justify-center text-muted-foreground text-xs">
            <span>Không tìm thấy giọng đọc phù hợp</span>
          </div>
        ) : (
          filteredVoices.map((voice) => {
            const isSelected = selectedVoiceId === voice.id;

            return (
              <div
                className={`studio-voice-row ${isSelected ? "studio-voice-selected" : ""} ${disabled ? "opacity-60" : ""}`}
                key={voice.id}
                ref={isSelected ? selectedRowRef : undefined}
              >
                <button
                  aria-pressed={isSelected}
                  className="flex min-w-0 flex-1 items-center gap-2 text-left"
                  disabled={disabled}
                  onClick={() => selectVoice(voice)}
                  type="button"
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <div
                      className="studio-voice-avatar"
                      data-tone={voiceColorIndex(voice.id)}
                    >
                      {voice.name
                        .split(" ")
                        .map((part) => part[0])
                        .slice(-2)
                        .join("")}
                    </div>

                    {/* Thông tin giọng */}
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="truncate font-semibold text-[13px] text-foreground">
                          {voice.name}
                        </span>
                        {/* Vùng miền đã có ở dòng dưới; nhãn "Nam" riêng dễ đọc nhầm giới tính. */}
                        {voice.featured && (
                          <Star
                            aria-label="Giọng tác giả VieNeu-TTS chọn"
                            className="h-3 w-3 shrink-0 fill-amber-400 text-amber-400"
                          />
                        )}
                      </div>
                      <p className="line-clamp-1 text-muted-foreground text-xs">
                        {languages.length > 0
                          ? describeVoice(voice.description ?? "", languageName)
                          : voiceDetail(voice) || "Giọng đọc có sẵn"}
                      </p>
                    </div>
                  </div>
                </button>
                {renderActions(voice, isSelected)}
              </div>
            );
          })
        )}
      </div>

      {/* Tốc độ đọc */}
      <div className="studio-speed">
        <div className="flex items-center justify-between gap-2 text-xs sm:text-sm">
          <div className="flex items-center gap-1.5 font-medium text-foreground/80">
            <Sliders className="h-3.5 w-3.5 text-brand-500" />
            <span>
              Tốc độ ·{" "}
              {speed.toLocaleString("vi-VN", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
              ×
            </span>
          </div>

          <div className="flex items-center gap-1">
            <button
              aria-label="Giảm tốc độ"
              className="flex h-6 w-6 items-center justify-center rounded border border-border/80 bg-background font-bold text-foreground/70 text-sm leading-none transition-colors hover:bg-secondary hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
              disabled={disabled || speed <= SPEED_MIN}
              onClick={() => onChangeSpeed(stepSpeed(speed, -1))}
              type="button"
            >
              &minus;
            </button>
            <input
              className="h-6 w-14 rounded border border-border/80 bg-background px-1 text-center font-bold font-mono text-brand-600 text-xs outline-none focus:border-brand-500 disabled:opacity-40 dark:text-brand-400"
              disabled={disabled}
              max={SPEED_MAX}
              min={SPEED_MIN}
              onBlur={() => commitSpeedDraft()}
              onChange={(e) => setSpeedDraft(e.target.value)}
              onFocus={() => setSpeedFocused(true)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  commitSpeedDraft();
                  e.currentTarget.blur();
                }
              }}
              step={SPEED_STEP}
              type="number"
              value={speedDraft}
            />
            <button
              aria-label="Tăng tốc độ"
              className="flex h-6 w-6 items-center justify-center rounded border border-border/80 bg-background font-bold text-foreground/70 text-sm leading-none transition-colors hover:bg-secondary hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
              disabled={disabled || speed >= SPEED_MAX}
              onClick={() => onChangeSpeed(stepSpeed(speed, 1))}
              type="button"
            >
              +
            </button>
            <button
              className="ml-1 h-6 rounded border border-border/80 bg-background px-2 font-semibold text-muted-foreground text-xs transition-colors hover:bg-secondary hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
              disabled={disabled || speed === SPEED_NORMAL}
              onClick={() => onChangeSpeed(SPEED_NORMAL)}
              type="button"
            >
              Chuẩn
            </button>
          </div>
        </div>

        <input
          className="h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-secondary accent-brand-500"
          disabled={disabled}
          max={SPEED_MAX}
          min={SPEED_MIN}
          onChange={(e) =>
            onChangeSpeed(clampSpeed(Number.parseFloat(e.target.value)))
          }
          step={SPEED_STEP}
          type="range"
          value={speed}
        />

        <div className="flex justify-between px-0.5 text-muted-foreground text-xs">
          <span>0,75× · Chậm</span>
          <span>1,50× · Nhanh</span>
        </div>
      </div>
    </div>
  );
};

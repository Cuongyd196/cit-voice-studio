import { useEffect, useId, useRef } from "react";
import type { VoiceOption } from "../types";
import { voiceDetail } from "../voice-label";

interface DefaultVoicePickerProps {
  /** Mục cài đặt đang mở: lúc ẩn thì chưa đo được vị trí để cuộn tới giọng đang chọn. */
  active: boolean;
  onChange: (voiceId: string) => void;
  value: string;
  voices: VoiceOption[];
}

const ROW_CLASS =
  "flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 hover:bg-secondary has-checked:bg-brand-500/10";
const RADIO_CLASS = "h-4 w-4 shrink-0 accent-brand-600";

// Danh sách cuộn ngay trong thẻ thay vì <select>: popup của <select> do trình duyệt vẽ,
// không giới hạn được chiều cao nên 26 giọng tràn ra ngoài hộp Cài đặt.
export function DefaultVoicePicker({
  active,
  onChange,
  value,
  voices,
}: DefaultVoicePickerProps) {
  const name = useId();
  const listRef = useRef<HTMLDivElement>(null);
  const current = voices.some((voice) => voice.id === value) ? value : "";

  useEffect(() => {
    const list = listRef.current;
    const row = list?.querySelector("input:checked")?.parentElement;
    if (active && list && row) {
      list.scrollTop = row.offsetTop - list.clientHeight / 2;
    }
  }, [active]);

  return (
    <fieldset className="space-y-3">
      <legend className="settings-card-title">Giọng mở sẵn</legend>
      <p className="settings-help">
        Bạn vẫn đổi được giọng khác khi đọc, lần mở sau lại về giọng này.
      </p>
      <div
        className="relative max-h-64 overflow-y-auto rounded-xl border border-border p-1"
        ref={listRef}
      >
        <label className={ROW_CLASS}>
          <input
            checked={current === ""}
            className={RADIO_CLASS}
            name={name}
            onChange={() => onChange("")}
            type="radio"
          />
          <span className="font-medium text-sm">
            Giọng mặc định của mô hình
          </span>
        </label>
        {voices.map((voice) => (
          <label className={ROW_CLASS} key={voice.id}>
            <input
              checked={current === voice.id}
              className={RADIO_CLASS}
              name={name}
              onChange={() => onChange(voice.id)}
              type="radio"
            />
            <span className="min-w-0">
              <span className="block truncate font-medium text-sm">
                {voice.name}
              </span>
              <span className="block truncate text-muted-foreground text-xs">
                {voiceDetail(voice)}
              </span>
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

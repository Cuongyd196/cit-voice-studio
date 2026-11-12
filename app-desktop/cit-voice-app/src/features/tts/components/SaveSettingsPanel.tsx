import { FolderOpen } from "lucide-react";
import { useEffect, useId, useState } from "react";
import { desktopApi, type SaveSettings } from "../desktop-files";

interface SaveSettingsPanelProps {
  isOpen: boolean;
}

/** Cài đặt → Lưu file: thư mục lưu, hỏi Save As hay lưu thẳng, tự mở file sau
 *  khi lưu. Chỉ app desktop làm được; trong trình duyệt hiện một dòng giải thích. */
export function SaveSettingsPanel({ isOpen }: SaveSettingsPanelProps) {
  const askId = useId();
  const openId = useId();
  const [settings, setSettings] = useState<SaveSettings | null>(null);
  const [isDesktop, setIsDesktop] = useState<boolean | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    let alive = true;
    desktopApi().then(async (api) => {
      if (!alive) {
        return;
      }
      setIsDesktop(Boolean(api));
      if (api) {
        const current = await api.get_save_settings();
        if (alive) {
          setSettings(current);
        }
      }
    });
    return () => {
      alive = false;
    };
  }, [isOpen]);

  const update = async (
    patch: Partial<Pick<SaveSettings, "ask" | "folder" | "open_after">>
  ) => {
    const api = await desktopApi();
    if (!(api && settings)) {
      return;
    }
    setBusy(true);
    try {
      const res = await api.set_save_settings({
        ask: settings.ask,
        folder: settings.folder,
        open_after: settings.open_after,
        ...patch,
      });
      if (res.success) {
        setSettings(res);
        setMessage("✓ Đã lưu cài đặt.");
      } else {
        setMessage(res.error || "Không lưu được cài đặt.");
      }
    } finally {
      setBusy(false);
    }
  };

  const chooseFolder = async () => {
    const api = await desktopApi();
    const res = await api?.choose_save_folder();
    if (res?.success && res.folder) {
      await update({ folder: res.folder });
    } else if (res?.error) {
      setMessage(res.error);
    }
  };

  if (isDesktop === false) {
    return (
      <div className="settings-card">
        <p className="settings-help">
          Chọn thư mục lưu và tự mở file chỉ có trong ứng dụng desktop. Trong
          trình duyệt, file được lưu theo cài đặt tải xuống của trình duyệt.
        </p>
      </div>
    );
  }
  if (!settings) {
    return null;
  }

  return (
    <div className="space-y-3">
      <div className="settings-card space-y-3">
        <h4 className="settings-card-title">
          <FolderOpen size={16} />
          Thư mục lưu file
        </h4>
        <p
          className="break-all rounded-xl border border-border bg-secondary/50 px-3 py-2 font-mono text-xs"
          title={settings.effective_folder}
        >
          {settings.effective_folder}
        </p>
        {settings.folder && settings.folder !== settings.effective_folder && (
          <p className="text-amber-700 text-xs dark:text-amber-300">
            Không tìm thấy thư mục đã chọn ({settings.folder}), đang dùng thư
            mục mặc định.
          </p>
        )}
        <div className="settings-field-row">
          <button
            className="studio-primary rounded-xl px-3 py-2 disabled:opacity-50"
            disabled={busy}
            onClick={chooseFolder}
            type="button"
          >
            Chọn thư mục…
          </button>
          <button
            className="rounded-xl border border-border px-3 py-2 disabled:opacity-50"
            disabled={busy || !settings.folder}
            onClick={() => update({ folder: null })}
            type="button"
          >
            Dùng thư mục Tải về
          </button>
        </div>
      </div>

      <div className="settings-card space-y-3">
        <label className="flex items-start gap-3" htmlFor={askId}>
          <input
            checked={settings.ask}
            className="mt-1 h-4 w-4 accent-brand-600"
            disabled={busy}
            id={askId}
            onChange={(e) => update({ ask: e.target.checked })}
            type="checkbox"
          />
          <span>
            <span className="settings-card-title">Hỏi nơi lưu mỗi lần</span>
            <span className="settings-help block">
              Bật: hiện hộp thoại Lưu thành, mở sẵn ở thư mục trên. Tắt: lưu
              thẳng vào thư mục trên, trùng tên thì thêm số (1), (2)… chứ không
              ghi đè.
            </span>
          </span>
        </label>
        <label className="flex items-start gap-3" htmlFor={openId}>
          <input
            checked={settings.open_after}
            className="mt-1 h-4 w-4 accent-brand-600"
            disabled={busy}
            id={openId}
            onChange={(e) => update({ open_after: e.target.checked })}
            type="checkbox"
          />
          <span>
            <span className="settings-card-title">Tự mở file sau khi lưu</span>
            <span className="settings-help block">
              Mở bằng chương trình mặc định của máy. Dù tắt, thông báo "Đã lưu"
              vẫn có nút Mở file và Mở thư mục.
            </span>
          </span>
        </label>
        {message && (
          <p aria-live="polite" className="settings-help" role="status">
            {message}
          </p>
        )}
      </div>
    </div>
  );
}

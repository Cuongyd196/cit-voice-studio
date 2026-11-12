import {
  AlertTriangle,
  Copy,
  Eye,
  EyeOff,
  KeyRound,
  RefreshCw,
  Wifi,
} from "lucide-react";
import type React from "react";
import { useEffect, useState } from "react";
import {
  fetchRemoteAccess,
  type RemoteAccessInfo,
  regenerateRemoteKey,
  saveRemoteAccess,
} from "../api";
import { RestartNotice } from "./RestartNotice";

interface RemoteAccessPanelProps {
  apiUrl: string;
  isOpen: boolean;
}

const errorText = (e: unknown) => (e instanceof Error ? e.message : String(e));

// Trang thai hien tai: da luu bat/tat co the khac voi server dang lang nghe (bat can
// khoi dong lai app; tat thi may khac bi tu choi ngay, khoi dong lai chi de dong cong).
function statusOf(info: RemoteAccessInfo): {
  text: string;
  tone: "ok" | "muted";
  /** Co = da luu nhung can khoi dong lai: hien RestartNotice thay cho hop trang thai. */
  restart?: string;
} {
  if (info.enabled && info.listening_all) {
    return { text: "Đang mở - máy khác gọi được khi có khoá.", tone: "ok" };
  }
  if (info.enabled) {
    return {
      restart: "Đã lưu: bật cho máy khác truy cập.",
      text: "",
      tone: "muted",
    };
  }
  if (info.listening_all) {
    return {
      restart: "Đã lưu: tắt - máy khác đã bị từ chối ngay.",
      text: "",
      tone: "muted",
    };
  }
  return {
    text: "Đang tắt - chỉ phần mềm trên máy này gọi được API.",
    tone: "muted",
  };
}

export const RemoteAccessPanel: React.FC<RemoteAccessPanelProps> = ({
  apiUrl,
  isOpen,
}) => {
  const [info, setInfo] = useState<RemoteAccessInfo | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const controller = new AbortController();
    setError("");
    fetchRemoteAccess(apiUrl, controller.signal)
      .then(setInfo)
      .catch((e) => {
        if (!controller.signal.aborted) {
          setError(errorText(e));
        }
      });
    return () => controller.abort();
  }, [apiUrl, isOpen]);

  const run = async (action: () => Promise<RemoteAccessInfo>) => {
    setBusy(true);
    setError("");
    try {
      setInfo(await action());
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const copy = (label: string, value: string) => {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(label);
      setTimeout(() => setCopied(null), 1500);
    });
  };

  const handleRegenerate = () => {
    if (
      // biome-ignore lint/suspicious/noAlert: xac nhan ngan gon truoc thao tac khong hoan tac
      !window.confirm(
        "Tạo khoá mới? Các máy đang dùng khoá cũ sẽ bị từ chối cho tới khi cập nhật khoá mới."
      )
    ) {
      return;
    }
    run(() => regenerateRemoteKey(apiUrl));
  };

  const status = info ? statusOf(info) : null;
  const mainIp = info?.primary_address ?? info?.addresses[0] ?? null;
  const otherIps = info?.addresses.filter((ip) => ip !== mainIp) ?? [];
  const firstUrl = mainIp
    ? `http://${mainIp}:${info?.port}`
    : `http://<IP-máy-này>:${info?.port ?? 8001}`;

  return (
    <div className="settings-card space-y-3">
      <label className="settings-toggle">
        <span aria-hidden="true" className="settings-toggle-icon">
          <Wifi size={18} />
        </span>
        <span className="settings-toggle-text">
          <strong>Cho máy khác truy cập API (mạng LAN)</strong>
          <span>
            Máy khác chỉ gọi được API tạo giọng và phải kèm khoá. Phần mềm trên
            máy này không cần khoá.
          </span>
        </span>
        <input
          checked={Boolean(info?.enabled)}
          className="studio-switch"
          disabled={!info || busy}
          onChange={(e) =>
            run(() => saveRemoteAccess(apiUrl, e.target.checked))
          }
          type="checkbox"
        />
      </label>

      {status?.restart && (
        <>
          <RestartNotice apiUrl={apiUrl} message={status.restart} />
          {info?.enabled && (
            <p className="text-[12px] text-muted-foreground leading-relaxed">
              Sau khi khởi động lại, lần đầu Windows sẽ hỏi quyền tường lửa:
              chọn <strong>Cho phép (Allow)</strong> với mạng{" "}
              <strong>Riêng tư (Private)</strong>.
            </p>
          )}
        </>
      )}
      {status && !status.restart && (
        <p
          aria-live="polite"
          className="settings-status"
          data-tone={status.tone}
          role="status"
        >
          <span aria-hidden="true" className="settings-status-dot" />
          {status.text}
        </p>
      )}

      {info?.enabled && (
        <div className="space-y-2 text-[12px]">
          <div className="space-y-1">
            <span className="flex items-center gap-1 font-semibold text-foreground">
              <KeyRound className="h-3.5 w-3.5 text-amber-500" /> Khoá API
            </span>
            <div className="flex gap-1.5">
              <input
                className="min-w-0 flex-1 rounded-lg border border-border bg-secondary/50 px-2.5 py-1.5 font-mono text-[12px]"
                readOnly
                type={showKey ? "text" : "password"}
                value={info.api_key}
              />
              <button
                aria-label={showKey ? "Ẩn khoá" : "Hiện khoá"}
                className="rounded-lg border border-border px-2 hover:bg-secondary"
                onClick={() => setShowKey(!showKey)}
                title={showKey ? "Ẩn khoá" : "Hiện khoá"}
                type="button"
              >
                {showKey ? (
                  <EyeOff className="h-3.5 w-3.5" />
                ) : (
                  <Eye className="h-3.5 w-3.5" />
                )}
              </button>
              <button
                className="flex items-center gap-1 rounded-lg border border-border px-2 hover:bg-secondary"
                onClick={() => copy("key", info.api_key)}
                type="button"
              >
                <Copy className="h-3.5 w-3.5" />
                {copied === "key" ? "Đã chép" : "Chép"}
              </button>
              <button
                className="flex items-center gap-1 rounded-lg border border-border px-2 hover:bg-secondary disabled:opacity-50"
                disabled={busy}
                onClick={handleRegenerate}
                title="Tạo khoá mới, khoá cũ hết hiệu lực ngay"
                type="button"
              >
                <RefreshCw className="h-3.5 w-3.5" /> Khoá mới
              </button>
            </div>
          </div>

          <div className="space-y-1">
            <span className="font-semibold text-foreground">
              Địa chỉ cho máy khác
            </span>
            {mainIp ? (
              <p className="font-mono font-semibold text-foreground">
                http://{mainIp}:{info.port}
              </p>
            ) : (
              <p className="text-muted-foreground">
                Không tìm thấy IP mạng LAN - máy này có đang nối mạng không?
              </p>
            )}
            {otherIps.length > 0 && (
              <p className="text-muted-foreground leading-relaxed">
                IP khác của máy:{" "}
                <span className="font-mono">{otherIps.join(", ")}</span> -
                thường là card mạng ảo (VirtualBox, Hyper-V, VPN), máy khác
                không kết nối tới được. Chỉ thử nếu địa chỉ trên không được.
              </p>
            )}
          </div>

          <div className="space-y-1">
            <span className="font-semibold text-foreground">
              Thử từ máy khác (cmd hoặc PowerShell)
            </span>
            <div className="flex gap-1.5">
              <code className="min-w-0 flex-1 overflow-x-auto whitespace-nowrap rounded-lg bg-zinc-950 px-2.5 py-1.5 font-mono text-[12px] text-zinc-200">
                curl.exe -H "X-API-Key: {showKey ? info.api_key : "<khoá>"}"{" "}
                {firstUrl}/health
              </code>
              <button
                className="flex items-center gap-1 rounded-lg border border-border px-2 hover:bg-secondary"
                onClick={() =>
                  copy(
                    "curl",
                    `curl.exe -H "X-API-Key: ${info.api_key}" ${firstUrl}/health`
                  )
                }
                type="button"
              >
                <Copy className="h-3.5 w-3.5" />
                {copied === "curl" ? "Đã chép" : "Chép"}
              </button>
            </div>
            <p className="text-muted-foreground leading-relaxed">
              Gửi khoá qua header <code className="font-mono">X-API-Key</code>{" "}
              (hoặc <code className="font-mono">Authorization: Bearer</code>).
            </p>
          </div>

          <p className="flex items-start gap-1.5 rounded-lg border border-amber-500/30 bg-amber-500/5 px-2.5 py-2 text-amber-700 leading-relaxed dark:text-amber-300">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>
              Chỉ bật trong mạng tin cậy và đừng chia sẻ khoá công khai. Khoá đi
              qua HTTP không mã hoá - muốn đưa ra Internet, hãy dùng đường hầm
              HTTPS (Cloudflare Tunnel, ngrok) thay vì mở cổng router.
            </span>
          </p>
        </div>
      )}

      {error && (
        <p className="text-rose-600 dark:text-rose-400" role="alert">
          {error}
        </p>
      )}
    </div>
  );
};

import {
  AlertTriangle,
  CheckCircle2,
  Download,
  RefreshCw,
  X,
} from "lucide-react";
import type { DownloadState } from "../types";

interface ModelOperationStatusProps {
  busy: boolean;
  cancelling: boolean;
  error: string | null;
  modelName: string;
  onCancel: () => void;
  onRetry?: () => void;
  status: DownloadState;
}

function size(bytes: number): string {
  return bytes >= 1024 ** 3
    ? `${(bytes / 1024 ** 3).toFixed(1)} GB`
    : `${Math.round(bytes / 1024 ** 2)} MB`;
}

function titleFor(status: DownloadState, cancelling: boolean): string {
  if (cancelling && status.state === "downloading") {
    return "Đang huỷ tải…";
  }
  if (status.state === "applying") {
    return "Đang áp dụng mô hình…";
  }
  if (status.state === "downloading") {
    if (status.phase === "gpu_setup") {
      return "Đang cài bộ hỗ trợ GPU…";
    }
    if (status.phase === "addon_setup") {
      return "Đang cài bộ tách âm…";
    }
    return status.pack ? "Đang tải gói ngôn ngữ…" : "Đang tải mô hình…";
  }
  if (status.state === "ready") {
    return status.pack ? "Đã thêm ngôn ngữ" : "Mô hình đã sẵn sàng";
  }
  return status.state === "cancelled" ? "Đã huỷ tải" : "Chưa hoàn tất thao tác";
}

function helpFor(status: DownloadState, measured: boolean): string {
  if (status.state === "applying") {
    return "Đang nạp dữ liệu vào bộ nhớ.";
  }
  if (status.phase === "gpu_setup") {
    return "Đang chuẩn bị thư viện GPU. Lần đầu có thể mất vài phút.";
  }
  if (status.phase === "addon_setup") {
    return "Đang tải và cài bộ tách âm từ PyPI vào thư mục riêng. Lần đầu có thể mất vài phút.";
  }
  return measured
    ? "Tải xong, ứng dụng sẽ tự áp dụng mô hình."
    : "Đang kiểm tra các file cần tải. Tiến độ sẽ hiện khi bắt đầu nhận dữ liệu.";
}

function iconFor(running: boolean, failure: boolean, ready: boolean) {
  if (running) {
    return RefreshCw;
  }
  if (failure) {
    return AlertTriangle;
  }
  return ready ? CheckCircle2 : X;
}

export function ModelOperationStatus({
  busy,
  cancelling,
  error,
  modelName,
  onCancel,
  onRetry,
  status,
}: ModelOperationStatusProps) {
  const running = status.state === "downloading" || status.state === "applying";
  const failure = error || (status.state === "error" ? status.message : null);
  if (
    !(running || failure) &&
    status.state !== "ready" &&
    status.state !== "cancelled"
  ) {
    return null;
  }
  const Icon = iconFor(running, Boolean(failure), status.state === "ready");

  return (
    <section
      className="model-operation"
      data-state={failure ? "error" : status.state}
    >
      <div aria-live="polite" className="model-operation-heading" role="status">
        <Icon
          aria-hidden="true"
          className={running ? "motion-safe:animate-spin" : ""}
          size={20}
        />
        <div>
          <strong>{titleFor(status, cancelling)}</strong>
          <p className="model-operation-name">{modelName}</p>
        </div>
      </div>
      {running && (
        <OperationProgress
          cancelling={cancelling}
          onCancel={onCancel}
          status={status}
        />
      )}
      {failure && (
        <p className="model-operation-help" role="alert">
          {failure}
        </p>
      )}
      {!(running || failure) && status.message && (
        <p className="model-operation-help">{status.message}</p>
      )}
      {failure && !running && onRetry && (
        <button
          className="model-operation-button"
          disabled={busy}
          onClick={onRetry}
          type="button"
        >
          <Download aria-hidden="true" size={14} /> Thử lại
        </button>
      )}
    </section>
  );
}

function OperationProgress({
  status,
  cancelling,
  onCancel,
}: Pick<ModelOperationStatusProps, "status" | "cancelling" | "onCancel">) {
  const measured =
    status.state === "downloading" &&
    status.phase !== "gpu_setup" &&
    status.phase !== "addon_setup" &&
    status.total_bytes > 0;
  const percent = Math.min(100, Math.max(0, Math.round(status.percent)));
  return (
    <>
      <p className="model-operation-help">{helpFor(status, measured)}</p>
      <div
        aria-label={
          status.state === "applying"
            ? "Tiến trình áp dụng mô hình"
            : "Tiến trình tải mô hình"
        }
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={measured ? percent : undefined}
        aria-valuetext={
          measured ? `${percent}%` : "Đang xử lý, chưa có phần trăm tiến độ"
        }
        className="model-operation-track"
        role="progressbar"
      >
        <div
          className={measured ? "" : "motion-safe:animate-pulse"}
          style={{ width: measured ? `${percent}%` : "40%" }}
        />
      </div>
      <div className="model-operation-details">
        <span className="model-operation-file" title={status.current_file}>
          {status.current_file ||
            (status.state === "applying"
              ? "Đang khởi tạo mô hình"
              : "Đang chuẩn bị…")}
        </span>
        {measured && (
          <strong>
            {percent}% · {size(status.done_bytes)} / {size(status.total_bytes)}
          </strong>
        )}
      </div>
      {status.state === "downloading" && (
        <button
          className="model-operation-button"
          disabled={cancelling}
          onClick={onCancel}
          type="button"
        >
          <X aria-hidden="true" size={14} />
          {cancelling ? "Đang huỷ…" : "Huỷ tải"}
        </button>
      )}
    </>
  );
}

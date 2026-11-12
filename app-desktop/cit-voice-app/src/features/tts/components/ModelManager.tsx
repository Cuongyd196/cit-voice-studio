import {
  AlertTriangle,
  Ban,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Cpu,
  Download,
  Feather,
  Languages,
  Layers,
  RefreshCw,
  Zap,
} from "lucide-react";
import type React from "react";
import { useEffect, useRef, useState } from "react";
import { useModelDownload } from "../hooks/useModelDownload";
import type { LanguagePack, ModelOption } from "../types";
import { ModelOperationStatus } from "./model-operation-status";

interface ModelManagerProps {
  apiUrl: string;
  embedded?: boolean;
  enabled: boolean;
  initialExpanded?: boolean;
  onModelSwitched?: (modelName: string) => void;
}

function docGon(n: number): string {
  if (!n) {
    return "";
  }
  return n < 1024 ** 3
    ? `${Math.round(n / 1024 ** 2)} MB`
    : `${(n / 1024 ** 3).toFixed(1)} GB`;
}

interface TrangThai {
  kind: "ready" | "missing" | "setup" | "blocked";
  text: string;
}

function trangThai(m: ModelOption): TrangThai {
  if (m.compatible === false) {
    return {
      kind: "blocked",
      text: m.unavailable_reason ?? "Máy này không chạy được",
    };
  }
  if (m.downloaded) {
    if (m.needs_gpu_setup) {
      return { kind: "setup", text: "Đã tải mô hình · Chưa cài bộ hỗ trợ GPU" };
    }
    if (m.needs_addon_setup) {
      return { kind: "setup", text: "Đã tải mô hình · Chưa cài bộ tách âm" };
    }
    return { kind: "ready", text: "Đã tải" };
  }
  return { kind: "missing", text: `Chưa tải · ${docGon(m.approx_bytes ?? 0)}` };
}

// Nhãn nổi bật trong tên mô hình; các phần khác trong ngoặc là thông số thường.
const NHAN_NOI_BAT = new Map([
  ["Khuyến nghị", "brand"],
  ["Nhanh nhất", "brand"],
  ["Thử nghiệm", "warn"],
]);

const TEN_CO_NGOAC = /^(.*?)\s*\((.*)\)\s*$/;
const NGAN_NHAN = /\s+[·-]\s+/;

/** "VieNeu-TTS v3 Turbo (INT8 CPU - Khuyến nghị)" -> tên + các nhãn trong ngoặc. */
function tachTen(name: string): { tags: string[]; title: string } {
  const match = name.match(TEN_CO_NGOAC);
  if (!match) {
    return { title: name, tags: [] };
  }
  return {
    title: match[1],
    tags: match[2].split(NGAN_NHAN).filter(Boolean),
  };
}

function bieuTuong(m: ModelOption) {
  if (m.device === "cuda" || m.device === "gpu" || m.name.includes("GPU")) {
    return Zap;
  }
  if (m.name.startsWith("Supertonic") || m.name.startsWith("Kokoro")) {
    return Languages;
  }
  if (m.name.includes("Nano")) {
    return Feather;
  }
  return Cpu;
}

/** Thiếu thư viện (GPU hoặc bộ tách âm của Kokoro): bấm sẽ đi đường tải, server
 * bỏ qua file đã có trong cache và chỉ cài phần còn thiếu. */
function canCai(m: ModelOption): boolean {
  return Boolean(m.needs_gpu_setup || m.needs_addon_setup);
}

interface ModelRowProps {
  dangDung: boolean;
  disabled: boolean;
  model: ModelOption;
  onAction: (m: ModelOption) => void;
  onAddPack: (m: ModelOption, pack: LanguagePack) => void;
  pending?: "downloading" | "applying";
}

/** Gói ngôn ngữ tải thêm (Kokoro: Nhật, Trung) - chỉ hiện khi mô hình đã sẵn sàng. */
function PackList({
  model,
  disabled,
  onAddPack,
}: Pick<ModelRowProps, "model" | "disabled" | "onAddPack">) {
  if (!(model.packs?.length && model.downloaded) || model.needs_addon_setup) {
    return null;
  }
  return (
    <div className="model-card-packs">
      <span>Thêm ngôn ngữ:</span>
      {model.packs.map((p) =>
        p.installed ? (
          <span className="model-tag" data-highlight="brand" key={p.code}>
            {p.name} · Đã cài
          </span>
        ) : (
          <button
            className="model-pack-button"
            disabled={disabled}
            key={p.code}
            onClick={() => onAddPack(model, p)}
            type="button"
          >
            <Download size={12} />
            <span>
              {p.name} (~{docGon(p.approx_bytes)})
            </span>
          </button>
        )
      )}
    </div>
  );
}

function nhanNut(
  model: ModelOption,
  pending?: "downloading" | "applying"
): string {
  if (pending === "applying") {
    return "Đang áp dụng…";
  }
  if (pending) {
    return "Đang tải…";
  }
  if (model.needs_gpu_setup) {
    return "Cài hỗ trợ GPU";
  }
  if (!model.downloaded) {
    return "Tải về & Áp dụng";
  }
  return model.needs_addon_setup ? "Cài bộ tách âm" : "Áp dụng";
}

function ModelRow({
  model,
  dangDung,
  disabled,
  onAction,
  onAddPack,
  pending,
}: ModelRowProps) {
  const khongChayDuoc = model.compatible === false;
  const { title, tags } = tachTen(model.name);
  const tt = trangThai(model);
  const Icon = bieuTuong(model);
  // Ghi chú ngắn, hiển thị đầy đủ cạnh trạng thái và tự xuống dòng khi cần.
  const ghiChu = [
    model.needs_gpu_setup && !khongChayDuoc
      ? "Cài thêm thư viện GPU; cần mạng và ít nhất 12 GB trống."
      : "",
    model.needs_addon_setup && !khongChayDuoc
      ? "Cài thêm bộ tách âm (khoảng 22 MB, tải từ PyPI)."
      : "",
    model.note ?? "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <div
      className="model-card"
      data-active={dangDung || undefined}
      data-blocked={khongChayDuoc || undefined}
    >
      <span aria-hidden="true" className="model-card-icon">
        <Icon size={20} />
      </span>
      <div className="model-card-body">
        <div className="model-card-head">
          <p className="model-card-title">{title}</p>
          {tags.map((tag) => (
            <span
              className="model-tag"
              data-highlight={NHAN_NOI_BAT.get(tag)}
              key={tag}
            >
              {tag}
            </span>
          ))}
          {model.supports_cloning && !khongChayDuoc && (
            <span className="model-tag">Nhân bản giọng</span>
          )}
        </div>
        <p className="model-card-status" data-kind={tt.kind}>
          {tt.kind === "ready" && <CheckCircle2 size={14} />}
          {tt.kind === "missing" && <Download size={14} />}
          {tt.kind === "setup" && <AlertTriangle size={14} />}
          {tt.kind === "blocked" && <Ban size={14} />}
          <span className="model-card-status-text">{tt.text}</span>
          {ghiChu && <span className="model-card-note">{ghiChu}</span>}
        </p>
        <PackList disabled={disabled} model={model} onAddPack={onAddPack} />
      </div>

      {dangDung && (
        <span className="model-card-current">
          <Check size={14} strokeWidth={3} />
          Đang dùng
        </span>
      )}
      {!(dangDung || khongChayDuoc) && (
        <button
          className="model-card-action"
          data-download={!model.downloaded || canCai(model) || undefined}
          disabled={disabled}
          onClick={() => onAction(model)}
          type="button"
        >
          {pending ? (
            <RefreshCw className="motion-safe:animate-spin" size={14} />
          ) : (
            !model.downloaded && <Download size={14} />
          )}
          <span>{nhanNut(model, pending)}</span>
        </button>
      )}
    </div>
  );
}

/**
 * Danh sách mô hình với ba trạng thái tách bạch: đã tải, chưa tải, và không
 * tương thích với máy này. `<select>` native không nhét được badge + nút riêng
 * từng dòng, nên dùng danh sách hàng.
 */
export const ModelManager: React.FC<ModelManagerProps> = ({
  embedded = false,
  initialExpanded = false,
  apiUrl,
  enabled,
  onModelSwitched,
}) => {
  // Thu gon mac dinh, giong khoi API - phan lon nguoi dung khong can mo moi lan
  // vao Cai dat, va useModelDownload chi bat dau poll khi thuc su mo ra.
  const [isExpanded, setIsExpanded] = useState(initialExpanded);
  const {
    models,
    current,
    status,
    busy,
    cancelling,
    error,
    download,
    apply,
    cancel,
  } = useModelDownload(apiUrl, enabled && isExpanded);
  const previousModelRef = useRef<string | null>(null);
  const operationRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (busy) {
      operationRef.current?.scrollIntoView({ block: "nearest" });
    }
  }, [busy]);

  // Cài xong gói ngôn ngữ thì Kokoro được nạp lại cùng tên, nên effect bên dưới
  // không thấy đổi mô hình: báo riêng để giọng và ngôn ngữ mới hiện ra.
  // Chỉ báo khi chính lần mở này thấy chuyển từ đang cài sang xong. Server giữ
  // trạng thái "ready" của lần cài trước, mà Cài đặt dựng lại ModelManager mỗi
  // lần mở, nên dựa vào trạng thái hiện tại thì mở lần nào cũng nạp lại.
  const previousStateRef = useRef(status.state);
  useEffect(() => {
    const was = previousStateRef.current;
    previousStateRef.current = status.state;
    const vuaCaiXong =
      (was === "downloading" || was === "applying") &&
      status.state === "ready" &&
      Boolean(status.pack);
    if (vuaCaiXong && current) {
      onModelSwitched?.(current);
    }
  }, [status.state, status.pack, current, onModelSwitched]);

  // Chỉ cập nhật danh sách giọng sau khi server thực sự áp dụng mô hình.
  useEffect(() => {
    if (!current || previousModelRef.current === current) {
      return;
    }
    const previous = previousModelRef.current;
    previousModelRef.current = current;
    if (previous !== null) {
      onModelSwitched?.(current);
    }
  }, [current, onModelSwitched]);

  const dangChay =
    status.state === "downloading" || status.state === "applying";

  const xuLy = (m: ModelOption) => {
    void (m.downloaded && !canCai(m) ? apply(m.id) : download(m.id));
  };
  const operationModel = models.find((m) => m.id === status.model_id);
  // Thử lại đúng việc vừa hỏng: tải gói ngôn ngữ thì tải lại gói đó.
  const thuLai = (): void => {
    if (!operationModel) {
      return;
    }
    if (status.pack) {
      download(operationModel.id, status.pack);
    } else {
      xuLy(operationModel);
    }
  };
  const coTheThuLai =
    operationModel !== undefined && operationModel.compatible !== false;

  return (
    <div
      className={
        embedded
          ? "settings-model-manager"
          : "rounded-xl border border-border p-3"
      }
    >
      <button
        className="flex w-full items-center justify-between gap-2 text-left"
        hidden={embedded}
        onClick={() => setIsExpanded(!isExpanded)}
        type="button"
      >
        <span className="flex items-center gap-1.5 font-semibold text-foreground">
          <Layers className="h-4 w-4 text-brand-500" />
          <span>Quản lý mô hình AI</span>
        </span>
        {isExpanded ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        )}
      </button>

      {isExpanded && (
        <div className="mt-3 space-y-4">
          <div className="model-operation-anchor" ref={operationRef}>
            <ModelOperationStatus
              busy={busy}
              cancelling={cancelling}
              error={error}
              modelName={
                operationModel?.name ?? status.model_id ?? "Mô hình AI"
              }
              onCancel={cancel}
              onRetry={coTheThuLai ? thuLai : undefined}
              status={status}
            />
          </div>
          <div className="model-list">
            {models.map((m) => (
              <ModelRow
                dangDung={current === m.id}
                disabled={dangChay || busy}
                key={m.id}
                model={m}
                onAction={xuLy}
                onAddPack={(model, p) => {
                  download(model.id, p.code);
                }}
                pending={
                  status.model_id === m.id && dangChay
                    ? (status.state as "downloading" | "applying")
                    : undefined
                }
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

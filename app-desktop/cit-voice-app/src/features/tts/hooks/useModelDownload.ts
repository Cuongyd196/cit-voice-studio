import { useCallback, useEffect, useRef, useState } from "react";
import {
  cancelModelDownload,
  fetchDownloadStatus,
  fetchModels,
  startModelDownload,
  switchModel,
} from "../api";
import type { DownloadState, ModelOption } from "../types";

const TRANG_THAI_RONG: DownloadState = {
  state: "idle",
  model_id: null,
  percent: 0,
  done_bytes: 0,
  total_bytes: 0,
  current_file: "",
  message: "",
};

/** Khoảng poll khi đang tải. Đủ mượt cho thanh tiến trình, đủ rẻ cho backend. */
const NHIP_POLL_MS = 1000;

/**
 * Máy trạng thái cho việc tải & áp dụng mô hình.
 *
 * Việc tải sống ở thread nền phía server, nên đóng modal không ngắt nó - mở
 * lại, lần poll đầu tiên vẽ lại đúng tiến trình. Hook này không lưu gì cả.
 */
export function useModelDownload(apiUrl: string, enabled: boolean) {
  const [models, setModels] = useState<ModelOption[]>([]);
  const [current, setCurrent] = useState<string | null>(null);
  const [status, setStatus] = useState<DownloadState>(TRANG_THAI_RONG);
  const [busy, setBusy] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetchModels(apiUrl);
      if (res.models) {
        setModels(res.models);
      }
      if (res.current?.name) {
        setCurrent(res.current.name);
      }
    } catch {
      // Máy chủ chưa sẵn sàng là chuyện bình thường lúc mới mở app.
    }
  }, [apiUrl]);

  const dungPoll = useCallback(() => {
    if (timerRef.current !== null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const batPoll = useCallback(() => {
    if (timerRef.current !== null) {
      return;
    }
    timerRef.current = setInterval(async () => {
      try {
        const st = await fetchDownloadStatus(apiUrl);
        setStatus(st);
        if (st.state !== "downloading" && st.state !== "applying") {
          dungPoll();
          setBusy(false);
          setCancelling(false);
          setError(st.state === "error" ? st.message : null);
          await refresh(); // badge "Chưa tải" phải đổi thành "Đã tải"
        }
      } catch {
        dungPoll();
        setBusy(false);
      }
    }, NHIP_POLL_MS);
  }, [apiUrl, dungPoll, refresh]);

  // Lúc mở: nạp danh sách, và bắt lại nhịp poll nếu server đang tải dở.
  useEffect(() => {
    if (!enabled) {
      return;
    }
    let huy = false;

    void refresh();
    void (async () => {
      try {
        const st = await fetchDownloadStatus(apiUrl);
        if (huy) {
          return;
        }
        setStatus(st);
        if (st.state === "downloading" || st.state === "applying") {
          setBusy(true);
          batPoll();
        }
      } catch {
        // bỏ qua
      }
    })();

    return () => {
      huy = true;
      dungPoll();
    };
  }, [enabled, apiUrl, refresh, batPoll, dungPoll]);

  const download = useCallback(
    async (modelId: string, pack: string | null = null) => {
      setError(null);
      setCancelling(false);
      setBusy(true);
      setStatus({
        ...TRANG_THAI_RONG,
        state: "downloading",
        model_id: modelId,
        pack,
      });
      try {
        await startModelDownload(apiUrl, modelId, true, pack);
        batPoll();
      } catch (e) {
        setBusy(false);
        const message = e instanceof Error ? e.message : String(e);
        setStatus({
          ...TRANG_THAI_RONG,
          state: "error",
          model_id: modelId,
          message,
        });
        setError(message);
      }
    },
    [apiUrl, batPoll]
  );

  const apply = useCallback(
    async (modelId: string) => {
      setError(null);
      setCancelling(false);
      setBusy(true);
      setStatus({ ...TRANG_THAI_RONG, state: "applying", model_id: modelId });
      try {
        await switchModel(apiUrl, modelId, "auto");
        setStatus({
          ...TRANG_THAI_RONG,
          state: "ready",
          model_id: modelId,
          message: "Đã áp dụng mô hình. Bạn có thể bắt đầu tạo giọng đọc.",
        });
        await refresh();
      } catch (e) {
        const message = e instanceof Error ? e.message : String(e);
        setStatus({
          ...TRANG_THAI_RONG,
          state: "error",
          model_id: modelId,
          message,
        });
        setError(message);
      } finally {
        setBusy(false);
      }
    },
    [apiUrl, refresh]
  );

  const cancel = useCallback(async () => {
    setCancelling(true);
    try {
      await cancelModelDownload(apiUrl);
    } catch (e) {
      setCancelling(false);
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [apiUrl]);

  return {
    models,
    current,
    status,
    busy,
    cancelling,
    error,
    download,
    apply,
    cancel,
    refresh,
  };
}

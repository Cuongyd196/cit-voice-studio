"""Giới hạn VRAM cho mô hình GPU (v3 Turbo PyTorch/CUDA).

Vì sao cần: batch engine giữ lại mỗi CUDA graph đã capture (một graph cho mỗi tổ
hợp cỡ lô x độ dài cache x temperature...), mỗi graph ~370 MB KV cache + memory
pool. Đo trên RTX 3050: nạp model 0,6 GB, đọc vài bài với temperature khác nhau là
lên ~2,9 GB (chưa kể CUDA context) và không bao giờ giảm. Trên card 4 GB, driver
Windows không báo "out of memory" mà lặng lẽ tràn sang RAM hệ thống ("Sysmem
Fallback") - máy chậm như treo. Cỡ lô thì gần như không đổi đỉnh VRAM (lô 1-16 đều
~1,1-1,5 GB) mà lô 16 nhanh gấp 4 lần lô 1, nên ở đây giới hạn SỐ GRAPH, không giảm
cỡ lô.

Hai lớp chặn:
- ``max_fused_graphs`` (LRU) tính từ mức VRAM cho phép: vượt thì bỏ graph cũ nhất.
- ``torch.cuda.set_per_process_memory_fraction``: PyTorch báo OutOfMemoryError khi
  chạm trần thay vì tràn sang RAM; ``v3turbo._infer_chunks`` bắt lỗi đó, dọn graph
  và đọc lại với lô nhỏ hơn.

Cấu hình (``{"vram_limit_gb": null | số}``, null = tự động) nằm ở
``%LOCALAPPDATA%\\CitVoiceStudio\\gpu-memory.json``.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from apps.remote_access import require_this_machine

logger = logging.getLogger(__name__)

GB = 1 << 30
# Số đo trên RTX 3050 (xem docstring module). Một lần đọc với 1 graph cần thêm
# ~0,7 GB ngoài model; mỗi graph giữ thêm ~0,37 GB - làm tròn lên cho an toàn.
FIRST_GRAPH_BYTES = int(0.75 * GB)
PER_GRAPH_BYTES = int(0.4 * GB)
MAX_GRAPHS = 8
# Tự động: chừa phần cho Windows, WebView2, trình duyệt... cùng dùng card.
AUTO_RESERVE_TOTAL = 1 * GB      # luôn chừa ít nhất chừng này của tổng VRAM
AUTO_HEADROOM_FREE = GB // 2     # và chừa thêm chừng này so với VRAM còn trống
MIN_LIMIT_GB = 1.5
MAX_LIMIT_GB = 80.0

# web_stream gắn hàm trả engine đang chạy vào đây (tránh import vòng).
engine_getter: Callable[[], Any] | None = None
# Kết quả lần áp dụng gần nhất, cho GET /api/gpu/memory.
_state: Dict[str, Any] = {}


def settings_path() -> Path:
    return Path(os.getenv("LOCALAPPDATA") or Path.home()) / "CitVoiceStudio" / "gpu-memory.json"


def configured_limit_gb() -> Optional[float]:
    try:
        value = json.loads(settings_path().read_text(encoding="utf-8")).get("vram_limit_gb")
    except (OSError, ValueError, AttributeError):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool) and MIN_LIMIT_GB <= value <= MAX_LIMIT_GB:
        return float(value)
    return None


def save_limit_gb(limit_gb: Optional[float]) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as f:
            tmp = Path(f.name)
            json.dump({"vram_limit_gb": limit_gb}, f)
        os.replace(tmp, path)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def plan(total: int, free: int, reserved: int, model_bytes: int, limit_gb: Optional[float]) -> Dict[str, int]:
    """Tính trần VRAM (byte) và số graph được giữ. Hàm thuần, không đụng torch.

    ``free`` là VRAM còn trống của cả card lúc này; ``reserved`` là phần PyTorch của
    app đang giữ (đã nằm ngoài ``free``); ``model_bytes`` là phần model chiếm."""
    if limit_gb is None:
        limit = min(total - AUTO_RESERVE_TOTAL, free + reserved - AUTO_HEADROOM_FREE)
    else:
        limit = min(int(limit_gb * GB), total)
    limit = max(int(MIN_LIMIT_GB * GB), limit)
    spare = limit - model_bytes - FIRST_GRAPH_BYTES
    graphs = 1 + max(0, spare // PER_GRAPH_BYTES)
    return {"limit": int(limit), "graphs": int(min(MAX_GRAPHS, graphs))}


def _torch_engine(tts) -> Any:
    """Batch engine của model GPU đang chạy, hoặc None (CPU/ONNX, Nano, Supertonic)."""
    if tts is None or getattr(tts, "backend", None) != "pytorch":
        return None
    get = getattr(tts, "_get_batch_engine", None)
    return get() if get else None


def apply(tts, *, just_loaded: bool = True) -> Optional[Dict[str, Any]]:
    """Áp giới hạn cho model vừa nạp (``just_loaded``) hoặc khi người dùng đổi mức
    (có thể đang đọc dở). Không bao giờ làm hỏng việc nạp model: lỗi chỉ ghi log."""
    engine = _torch_engine(tts)
    if engine is None:
        _state.clear()
        return None
    try:
        import torch

        dev = torch.cuda.current_device()
        total = torch.cuda.get_device_properties(dev).total_memory
        limit_gb = configured_limit_gb()
        if just_loaded or "model_bytes" not in _state:
            # Đo phần model lúc chưa có graph nào. Khi đổi mức giữa chừng thì dùng
            # lại số này: lúc đó memory_allocated gồm cả bộ nhớ tạm của lần đọc.
            engine.trim_fused(0)
            model_bytes = torch.cuda.memory_allocated(dev)
        else:
            model_bytes = _state["model_bytes"]
        # free + reserved = phần card dành được cho app, dù app đang đọc hay rảnh.
        reserved = torch.cuda.memory_reserved(dev)
        free, _ = torch.cuda.mem_get_info(dev)
        p = plan(total, free, reserved, model_bytes, limit_gb)
        engine.max_fused_graphs = p["graphs"]
        # Graph đang chạy dở vẫn được giữ bởi biến cục bộ, bỏ khỏi bộ đệm là an toàn.
        engine.trim_fused(p["graphs"])
        torch.cuda.set_per_process_memory_fraction(min(1.0, p["limit"] / total), dev)
        _state.clear()
        _state.update(
            gpu_name=torch.cuda.get_device_name(dev), total=total, limit=p["limit"],
            graphs=p["graphs"], limit_gb=limit_gb, model_bytes=model_bytes,
        )
        logger.info(
            f"🎛️ VRAM: trần {p['limit'] / GB:.1f}/{total / GB:.1f} GB "
            f"({'tự động' if limit_gb is None else 'người dùng đặt'}), giữ tối đa {p['graphs']} CUDA graph"
        )
        return dict(_state)
    except Exception as e:  # noqa: BLE001 - cấu hình VRAM không được chặn việc chạy
        logger.warning(f"Không áp được giới hạn VRAM: {e}")
        return None


def _gb(x: Optional[int]) -> Optional[float]:
    return None if x is None else round(x / GB, 2)


def status() -> Dict[str, Any]:
    tts = engine_getter() if engine_getter else None
    engine = _torch_engine(tts)
    out: Dict[str, Any] = {"available": False, "limit_gb": configured_limit_gb(),
                           "min_gb": MIN_LIMIT_GB}
    if engine is None or not _state:
        return out
    used = None
    try:
        import torch
        used = torch.cuda.memory_reserved()
    except Exception:  # noqa: BLE001
        pass
    out.update(
        available=True, gpu_name=_state["gpu_name"], total_gb=_gb(_state["total"]),
        effective_limit_gb=_gb(_state["limit"]), used_gb=_gb(used),
        max_graphs=_state["graphs"], graphs=len(getattr(engine, "_fused", {})),
    )
    return out


router = APIRouter()


class GpuMemorySettings(BaseModel):
    limit_gb: Optional[float] = Field(default=None, description="null = tự động")


@router.get("/api/gpu/memory")
def get_gpu_memory():
    return status()


@router.put("/api/gpu/memory")
def put_gpu_memory(settings: GpuMemorySettings, request: Request):
    require_this_machine(request)
    limit = settings.limit_gb
    if limit is not None and not MIN_LIMIT_GB <= limit <= MAX_LIMIT_GB:
        raise HTTPException(status_code=400, detail=f"Giới hạn VRAM phải từ {MIN_LIMIT_GB:g} GB trở lên.")
    try:
        save_limit_gb(limit)
    except OSError as error:
        raise HTTPException(status_code=500, detail="Không lưu được cài đặt VRAM. Hãy kiểm tra quyền ghi cấu hình.") from error
    # Áp ngay cho model GPU đang chạy - không cần khởi động lại.
    apply(engine_getter() if engine_getter else None, just_loaded=False)
    return status()

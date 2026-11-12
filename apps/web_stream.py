"""
CIT Voice Studio - Comprehensive Backend API Server (FastAPI + VieNeu-TTS)
==========================================================================
Cung cấp toàn bộ các API tính năng tương đương bản Web Studio (Gradio UI):
- TTS Streaming thời gian thực (WAV 48kHz)
- TTS Batch / Standard chất lượng cao (WAV / MP3)
- Dùng giọng nhân bản đã lưu từ micro hoặc file âm thanh kèm cam kết quyền sử dụng trong ứng dụng
- Hội thoại & Podcast đa nhân vật (Multi-speaker conversation)
- Đọc & trích xuất tài liệu PDF / TXT
- Chuyển đổi định dạng âm thanh WAV sang MP3
- Quản lý và chuyển đổi Mô hình (v3 Turbo int8/fp32/GPU, v3 Nano)
"""
import base64
import io
import json
import os
import re
import sys
import time
import wave
import shutil
import tempfile
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Union

if sys.platform == "win32":
    if sys.stdout is None:
        sys.stdout = io.StringIO()
    else:
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if sys.stderr is None:
        sys.stderr = io.StringIO()
    else:
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


import numpy as np
import soundfile as sf
import uvicorn
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Thêm đường dẫn src vào sys.path (hỗ trợ cả PyInstaller frozen)
if getattr(sys, "frozen", False):
    ROOT_DIR = Path(sys._MEIPASS)
else:
    ROOT_DIR = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "src"))

# Cache Hugging Face dùng chung. Phải chạy TRƯỚC `from vieneu import Vieneu` vì
# huggingface_hub đọc HF_HOME ngay lúc import.
from apps.runtime_paths import setup_hf_home, fix_web_mime_types
setup_hf_home()

# Phải chạy TRƯỚC khi StaticFiles phục vụ file đầu tiên. Xem giải thích dài trong
# runtime_paths.fix_web_mime_types: registry Windows bẩn làm file .js bị trả về kiểu
# "text/plain", trình duyệt từ chối chạy module, giao diện trắng trơn không báo lỗi.
_mime_fixed = fix_web_mime_types()

# Nếu ở lần chạy trước đã tự cài PyTorch/CUDA vào venv riêng (bản .exe, xem
# apps/gpu_installer.py), nạp nó vào sys.path NGAY BÂY GIỜ - trước `import torch`
# đầu tiên trong tiến trình, ở bất cứ đâu (kể cả trong `vieneu`).
from apps.gpu_installer import activate_gpu_venv, run_gpu_selftest
activate_gpu_venv()
if os.getenv("CIT_GPU_SELFTEST") == "1":
    run_gpu_selftest()
if os.getenv("CIT_KOKORO_SELFTEST") == "1":
    from apps.kokoro_installer import run_selftest as run_kokoro_selftest
    run_kokoro_selftest()

from vieneu import Vieneu
from apps import ai_label, model_catalog, model_downloader
from apps.app_version import APP_VERSION

SAMPLE_RATE = 48_000

DOCS_DESCRIPTION = """
### 🤖 Tài Liệu Kết Nối Cho AI Agent & Lập Trình Viên

CIT Voice Studio tạo giọng nói trên máy người dùng. API công khai gồm:
- **Tạo audio WAV/MP3**, luồng WAV PCM16 và audio kèm phụ đề SRT.
- **Mô hình đang chạy**: VieNeu v3 Turbo (48 kHz), v3 Nano (24 kHz), Supertonic 3 (44,1 kHz, 31 ngôn ngữ) hoặc Kokoro (24 kHz, 8 ngôn ngữ, không có tiếng Việt). Kiểm tra `/health`, lấy giọng từ `/voices`; không gắn cứng giọng hay tần số.
- **Dùng giọng nhân bản đã lưu** qua `voice_id`. Tạo giọng ở tab **Nhân bản giọng** bằng micro hoặc file âm thanh kèm cam kết quyền sử dụng; giọng và cam kết chỉ lưu trên máy. Không có API nhân bản công khai từ file (`/api/tts/clone` đã bỏ). Supertonic 3 và Kokoro chỉ có giọng sẵn.
- **Cảm xúc**: VieNeu v3 Turbo dùng `[cười]`, `[hắng giọng]`, `[thở dài]`; Supertonic dùng `<laugh>`, `<breath>`, `<sigh>`; Kokoro không có thẻ cảm xúc. Thẻ nghỉ `[nghỉ 2s]` dùng với mọi mô hình.
- **Hội thoại & Podcast**: Ghép nối tự động các lượt thoại giữa nhiều nhân vật.

Chỉ gửi yêu cầu tạo giọng khi `/health` trả `status: "ok"`. `/stream` trả dữ liệu dần; độ trễ phụ thuộc mô hình và máy, Supertonic và Kokoro trả theo đoạn. Khi đang chạy Kokoro, văn bản tiếng Việt bị từ chối (400). Các API quản lý mô hình, tạo/xoá giọng và lịch sử là API nội bộ, không cung cấp cho phần mềm bên ngoài.

🔑 **Gọi từ máy khác** (khi đã bật trong Cài đặt của ứng dụng): gửi kèm header `X-API-Key: <khoá>`. Gọi từ chính máy này thì không cần khoá.

---
📥 **[Tải xuống file cit-voice-studio.md](/cit-voice-studio.md?download=1)** *(Tải trực tiếp file về máy để nạp vào Cursor, Claude, ChatGPT, AutoGen...)*  
📄 **[Xem trực tiếp tài liệu Markdown (/cit-voice-studio.md)](/cit-voice-studio.md)** *(Mở đọc và sao chép trực tiếp trên trình duyệt)*  
📋 **[Đặc tả OpenAPI JSON chuẩn (/openapi.json)](/openapi.json)**
"""

app = FastAPI(
    title="CIT Voice Studio TTS API",
    version=APP_VERSION,
    description=DOCS_DESCRIPTION,
)
from apps.server_settings import router as server_settings_router, setup_port
# API noi bo (chi giao dien cua app dung) an khoi /docs: tai lieu cho phan mem
# khac chi gom cac API tao giong. Van chay binh thuong, chi khong liet ke.
app.include_router(server_settings_router, include_in_schema=False)
from apps import pronunciation_settings
app.include_router(pronunciation_settings.router, include_in_schema=False)
from vieneu_utils.pause_tags import split_pauses
from vieneu_utils.subtitles import build_units, display_text, to_srt, unit_cues
from vieneu_utils import dubbing
from vieneu_utils.srt import SrtError, parse_srt
from vieneu_utils.time_stretch import time_stretch
from vieneu_utils.core_utils import V3_GAP_SILENCE, pause_pad_samples, split_into_sentences
from vieneu_utils.subtitles import CLOSING_MARKS, _NON_LATIN_STOP
from starlette.background import BackgroundTask
from apps import history_store
app.include_router(history_store.router, include_in_schema=False)
from apps import gpu_memory
app.include_router(gpu_memory.router, include_in_schema=False)
gpu_memory.engine_getter = lambda: vieneu
from apps import remote_access
app.include_router(remote_access.router, include_in_schema=False)
from apps import app_update
app.include_router(app_update.router, include_in_schema=False)
from apps import terms
app.include_router(terms.router, include_in_schema=False)
from apps import ui_prefs
app.include_router(ui_prefs.router, include_in_schema=False)

@app.get("/cit-voice-studio.md", response_class=FileResponse, tags=["Documentation"])
async def get_cit_voice_studio_doc(download: bool = False):
    """Tải xuống hoặc đọc file Markdown cit-voice-studio.md hướng dẫn kết nối API cho AI Agent."""
    from apps.runtime_paths import app_root
    # Bản đóng gói: cạnh file chạy, rồi trong gói (--add-data). Mã nguồn: docs/.
    candidates = (app_root() / "cit-voice-studio.md", ROOT_DIR / "cit-voice-studio.md",
                  ROOT_DIR / "docs" / "cit-voice-studio.md")
    doc_path = next((p for p in candidates if p.exists()), candidates[-1])
    if not doc_path.exists():
        raise HTTPException(status_code=404, detail="File cit-voice-studio.md không tồn tại.")
    disposition = "attachment" if download else "inline"
    return FileResponse(
        str(doc_path),
        media_type="text/markdown; charset=utf-8",
        filename="cit-voice-studio.md",
        headers={
            "Content-Disposition": f'{disposition}; filename="cit-voice-studio.md"',
            "Access-Control-Allow-Origin": "*",
        },
    )

# Enable CORS for desktop app & local web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Trình duyệt ở origin khác chỉ đọc được header được liệt kê ở đây.
    expose_headers=[ai_label.HEADER],
)
# Them TRUOC remote access => nam trong, chi gan header cho phan hoi audio that.
app.add_middleware(ai_label.AiHeaderMiddleware)
# Them SAU CORS => chay NGOAI CUNG: chan may khac truoc khi toi bat ky route nao.
app.add_middleware(remote_access.RemoteAccessMiddleware)

# Global State
vieneu = None
current_model_info = {
    "name": "VieNeu-TTS-v3-Turbo (int8)",
    "backend": "onnx",
    "precision": "int8",
    "device": "cpu",
    "sample_rate": SAMPLE_RATE,
}
model_lock = threading.Lock()

DIST_DIR = ROOT_DIR / "app-desktop" / "cit-voice-app" / "dist"

# Mount static assets if modern frontend build exists
if (DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

if _mime_fixed:
    print("[MIME] Registry Windows khai bao sai kieu file tinh, da sua: "
          + ", ".join(f"{e}={v}" for e, v in _mime_fixed.items()))


def cuda_is_available() -> bool:
    """Máy có GPU NVIDIA dùng được qua torch không.

    Bản cài mặc định là torch-free nên `import torch` hỏng là chuyện bình thường -
    khi đó coi như không có GPU. Dùng cho quyết định thời gian chạy thực (chọn
    model lúc khởi động, `gpu.available` hiển thị) - KHÔNG dùng cho việc hiện nút
    tải mô hình GPU, vì lúc đó torch có thể chưa cài (xem `_effective_has_cuda`).
    """
    global _torch_import_logged
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception as e:
        # Không có torch là bình thường; nhưng đã cài bộ GPU mà vẫn hỏng thì phải
        # để lại dấu vết trong log, nếu không máy khách chỉ thấy "không có GPU".
        if not _torch_import_logged and activate_gpu_venv():
            _torch_import_logged = True
            print(f"[GPU] Đã cài bộ hỗ trợ GPU nhưng không nạp được torch: {e!r}")
        return False


_torch_import_logged = False


def _effective_has_cuda() -> bool:
    """Cho hiển thị `/api/models`: coi là có GPU nếu torch báo có, HOẶC máy có GPU
    NVIDIA vật lý dù torch chưa cài (bản .exe tự cài lúc áp dụng, xem gpu_installer.py)."""
    if cuda_is_available():
        return True
    from apps.model_catalog import check_has_physical_nvidia_gpu
    return check_has_physical_nvidia_gpu()


def gpu_name() -> Optional[str]:
    try:
        import torch
        return torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception:
        return None


def _custom_voices_path() -> Path:
    """File JSON riêng cho giọng do người dùng lưu lại (khác file giọng có sẵn
    trong gói cài đặt, vốn có thể chỉ đọc) - cùng cách chọn thư mục với
    `setup_hf_home()`/`gpu_installer.gpu_venv_dir()`."""
    from apps.runtime_paths import app_root, _is_writable

    filename = "custom_voices_v3_nano.json" if "nano" in current_model_info.get("name", "").lower() else "custom_voices_v3_turbo.json"
    d = app_root() / "models"
    if _is_writable(d):
        return d / filename
    base = os.getenv("LOCALAPPDATA") or str(Path.home())
    p = Path(base) / "CitVoiceStudio" / filename
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _supertonic_dir() -> Path:
    """Thư mục snapshot của Supertonic 3 trong cache HF. Chỉ đọc cache: chưa tải thì
    báo người dùng bấm Tải về, không tự kéo ~400 MB giữa lúc đổi mô hình."""
    from huggingface_hub import snapshot_download

    try:
        return Path(snapshot_download(
            model_catalog.SUPERTONIC_REPO, revision=model_catalog.SUPERTONIC_REVISION,
            allow_patterns=list(model_catalog.SUPERTONIC_FILES), local_files_only=True))
    except Exception as e:
        raise RuntimeError(
            "Chưa tải mô hình Supertonic 3. Mở mục Mô hình và bấm Tải về (~400 MB).") from e


def _load_kokoro(gpu: bool = False):
    """Mô hình đa ngôn ngữ Kokoro. Bộ tách âm (có phần GPL) không nằm trong bản
    cài - phải được `kokoro_installer` cài vào máy người dùng từ trước (lúc bấm Tải về).

    `gpu`: trọng số PyTorch của hexgrad trên CUDA (apps/_kokoro_torch). Onnxruntime
    đóng gói chỉ có CPU và bản GPU trùng tên module, nên GPU phải đi đường torch."""
    from apps import kokoro_installer
    from apps.kokoro_engine import KokoroTTS
    from huggingface_hub import hf_hub_download

    if not kokoro_installer.activate():
        raise RuntimeError(
            "Chưa cài bộ tách âm cho Kokoro. Mở Cài đặt và bấm Tải về ở mô hình Kokoro "
            "để ứng dụng tự cài."
        )
    # Máy dev không có GPU: CIT_KOKORO_TORCH_DEVICE=cpu chạy đúng đường PyTorch trên
    # CPU để thử trọn luồng (tải, nạp, đọc) - chậm, chỉ để kiểm tra.
    device = os.getenv("CIT_KOKORO_TORCH_DEVICE", "cuda")
    if gpu and device == "cuda" and not cuda_is_available():
        raise RuntimeError(
            "Không tìm thấy GPU NVIDIA dùng được, hoặc PyTorch/CUDA chưa nạp xong. "
            "Hãy bấm lại nút Tải về ở mô hình Kokoro GPU để ứng dụng tự cài."
        )
    try:
        if gpu:
            model_path = hf_hub_download(model_catalog.KOKORO_TORCH_REPO, "kokoro-v1_0.pth", revision=model_catalog.KOKORO_TORCH_REVISION, local_files_only=True)
            config = hf_hub_download(model_catalog.KOKORO_TORCH_REPO, "config.json", revision=model_catalog.KOKORO_TORCH_REVISION, local_files_only=True)
        else:
            model_path = hf_hub_download(model_catalog.KOKORO_REPO, "onnx/model.onnx", revision=model_catalog.KOKORO_REVISION, local_files_only=True)
            config = None
        heart = hf_hub_download(model_catalog.KOKORO_REPO, "voices/af_heart.bin", revision=model_catalog.KOKORO_REVISION, local_files_only=True)
    except Exception as e:
        raise RuntimeError(
            "Chưa tải mô hình Kokoro. Mở Cài đặt và bấm Tải về ở mô hình Kokoro."
        ) from e
    cache = Path(os.getenv("LOCALAPPDATA") or Path.home()) / "CitVoiceStudio" / "kokoro"
    return KokoroTTS(model_path, Path(heart).parent, cache_dir=cache,
                     languages=kokoro_installer.ready_languages(),
                     torch_config=config, device=device)


def load_model_instance(model_name: str = "VieNeu-TTS-v3-Turbo (int8)", device: str = "auto"):
    global vieneu, current_model_info
    with model_lock:
        print(f"⏳ Đang tải mô hình: {model_name} (Thiết bị: {device})...")
        t0 = time.time()

        if model_name == model_catalog.SUPERTONIC_ID:
            from apps.supertonic_engine import LANGUAGES, SupertonicTTS
            vieneu = SupertonicTTS(_supertonic_dir())
            current_model_info = {
                "name": model_name, "backend": "onnx", "precision": "fp32",
                "device": "cpu", "sample_rate": vieneu.sample_rate,
                "languages": [{"code": k, "name": v} for k, v in LANGUAGES.items()],
            }
        elif model_catalog.is_kokoro(model_name):
            # Trước nhánh "gpu" bên dưới: id Kokoro GPU cũng chứa chữ "GPU".
            gpu = model_name == model_catalog.KOKORO_GPU_ID
            vieneu = _load_kokoro(gpu=gpu)
            # Như Supertonic: liệt kê ngôn ngữ (chỉ những thứ tiếng đã cài bộ tách âm),
            # nên `language` của API và ô chọn ngôn ngữ trên giao diện dùng chung.
            # Không có "vi": API từ chối văn bản tiếng Việt (_require_language).
            current_model_info = {
                "name": model_name, "backend": vieneu.backend, "precision": "fp32",
                "device": vieneu.device, "sample_rate": vieneu.sample_rate,
                "languages": [{"code": k, "name": v} for k, v in vieneu.languages.items()],
                "supports_emotions": False,
                # Ngữ điệu Kokoro tất định (chỉ có chút nhiễu ở bộ tạo sóng), nên "Ổn định"
                # không đổi được gì mà người nghe nhận ra.
                "supports_seed": False,
            }
            if gpu:
                current_model_info["gpu_name"] = gpu_name()
        elif model_name == "VieNeu-TTS-v3-Nano (preview)":
            vieneu = Vieneu(mode="v3nano")
            current_model_info = {
                "name": model_name, "backend": "onnx", "precision": "fp32",
                "device": "cpu", "sample_rate": 24_000,
            }
        elif "gpu" in model_name.lower():
            # v3 Turbo chạy PyTorch/CUDA. Đây là đường DUY NHẤT dùng được GPU cho v3:
            # engine ONNX hardcode CPUExecutionProvider. Nó cũng mở khoá static
            # batching (vieneu.v3_turbo_serve) - chỗ GPU thắng đậm nhất, dùng cho
            # chế độ Hội thoại/Podcast nhiều lượt.
            if not cuda_is_available():
                import sys
                if getattr(sys, "frozen", False):
                    raise RuntimeError(
                        "Không tìm thấy GPU NVIDIA dùng được, hoặc PyTorch/CUDA chưa nạp "
                        "xong. Hãy bấm lại nút Tải về ở mô hình GPU để ứng dụng tự cài."
                    )
                raise RuntimeError(
                    "Không tìm thấy GPU NVIDIA dùng được. Bản cài này là torch-free. "
                    "Mở Cài đặt và chọn Cài hỗ trợ GPU để tải thư viện cần thiết."
                )
            vieneu = Vieneu(mode="v3turbo", backend="pytorch", device="cuda")
            # Chặn VRAM phình theo số CUDA graph (card 4 GB treo máy): apps/gpu_memory.py
            gpu_memory.apply(vieneu)
            current_model_info = {
                "name": "VieNeu-TTS-v3-Turbo (GPU)",
                "backend": "pytorch",
                "precision": "fp32",
                "device": "cuda",
                "gpu_name": gpu_name(),
                "sample_rate": 48_000,
            }
        elif "int8" in model_name.lower():
            vieneu = Vieneu(mode="v3turbo", backend="onnx", precision="int8")
            current_model_info = {
                "name": "VieNeu-TTS-v3-Turbo (int8)",
                "backend": "onnx",
                "precision": "int8",
                "device": "cpu",
                "sample_rate": 48_000,
            }
        elif "fp32" in model_name.lower():
            vieneu = Vieneu(mode="v3turbo", backend="onnx", precision="fp32")
            current_model_info = {
                "name": "VieNeu-TTS-v3-Turbo (fp32)",
                "backend": "onnx",
                "precision": "fp32",
                "device": "cpu",
                "sample_rate": 48_000,
            }
        else:
            vieneu = Vieneu(backend="onnx")
            current_model_info = {
                "name": "VieNeu-TTS-v3-Turbo (int8)",
                "backend": "onnx",
                "precision": "int8",
                "device": "cpu",
                "sample_rate": 48_000,
            }

        elapsed = time.time() - t0
        print(f"✅ Mô hình đã sẵn sàng trong {elapsed:.2f}s! Backbone: {current_model_info['name']}")
        _remember_model(current_model_info["name"])

        # Nạp lại giọng tuỳ chỉnh người dùng đã lưu ở phiên trước (nếu engine hỗ trợ).
        # File này tách khỏi giọng có sẵn trong gói cài đặt, xem _custom_voices_path().
        if hasattr(vieneu, "load_extra_voices"):
            try:
                so_giong = vieneu.load_extra_voices(_custom_voices_path())
                if so_giong:
                    print(f"📢 Đã nạp thêm {so_giong} giọng tuỳ chỉnh đã lưu trước đó.")
            except Exception as e:
                print(f"⚠️ Không nạp được giọng tuỳ chỉnh đã lưu: {e}")


def _last_model_path() -> Path:
    return Path(os.getenv("LOCALAPPDATA") or Path.home()) / "CitVoiceStudio" / "last-model.json"


def _remember_model(model_id: str) -> None:
    """Ghi mô hình vừa nạp xong để lần mở app sau nạp lại đúng nó. Trước đây app luôn
    quay về Turbo int8 dù người dùng đã chuyển sang mô hình khác trong Cài đặt."""
    try:
        path = _last_model_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"model": model_id}), encoding="utf-8")
        tmp.replace(path)
    except OSError as e:
        print(f"⚠️ Không lưu được mô hình đang dùng: {e}")


def _saved_model() -> Optional[str]:
    """Mô hình đã dùng lần trước, nếu vẫn có trong danh mục và đã tải đủ file."""
    try:
        model_id = json.loads(_last_model_path().read_text(encoding="utf-8"))["model"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    spec = model_catalog.get(model_id)
    if spec is None or spec not in model_catalog.MODELS:
        return None
    try:
        return model_id if model_catalog.is_downloaded(spec) else None
    except Exception:
        return None


def _friendly_load_error(e: BaseException) -> str:
    """Đổi lỗi kỹ thuật sang câu người dùng hiểu và làm theo được."""
    from apps.runtime_paths import missing_vcredist, vcredist_error_message
    msg = str(e).lower()

    if "no module named 'torch'" in msg or "no module named 'torchaudio'" in msg or "no module named 'neucodec'" in msg:
        if model_catalog.frozen_gpu_autoinstall_possible():
            # Bình thường model_downloader đã tự cài trước khi tới đây (xem
            # apps/gpu_installer.py) - lọt tới đây nghĩa là lần cài trước lỗi/dở dang.
            return (
                "Chưa nạp được PyTorch/CUDA. Hãy bấm lại nút Tải về ở mô hình này để "
                "ứng dụng tự cài (cần mạng, khoảng 1.5GB, có thể mất vài phút)."
            )
        return (
            "Chưa có bộ hỗ trợ GPU và không tìm thấy công cụ cài tự động. "
            "Hãy cập nhật hoặc cài lại đầy đủ bộ CIT Voice Studio mới nhất."
        )

    if "onnxruntime" in msg or "dll load failed" in msg:
        miss = missing_vcredist()
        if miss:
            return vcredist_error_message(miss)
    root = _root_cause(e)
    if root is not e:
        # transformers nạp module kiểu lười và bọc lỗi thật thành "Could not import
        # module 'PretrainedConfig'" - không kèm lỗi gốc thì không chẩn đoán nổi.
        return f"Không nạp được mô hình: {e} (nguyên nhân: {type(root).__name__}: {root})"
    return f"Không nạp được mô hình: {e}"


def _root_cause(e: BaseException) -> BaseException:
    seen = set()
    while id(e) not in seen:
        seen.add(id(e))
        nxt = e.__cause__ or e.__context__
        if nxt is None:
            break
        e = nxt
    return e


# Lỗi khi nạp mô hình vừa tải xong phải đi qua đúng hàm dịch lỗi này, không thì
# máy thiếu VC++ Redist lại nhận được câu "Không tải được mô hình" vô nghĩa.
model_downloader.apply_error_formatter = _friendly_load_error


def _startup_load() -> None:
    """Nạp mô hình vào RAM mỗi lần chạy ứng dụng, dùng lại file đã tải trên đĩa."""
    global model_status
    model_status = {"state": "loading", "message": "Đang nạp mô hình giọng nói..."}
    # Mô hình người dùng chọn lần trước (đã tải đủ). Chưa có thì: GPU NVIDIA dùng được
    # thì GPU, không thì CPU int8 - máy cài kiểu mặc định (torch-free) rơi vào CPU.
    # Mô hình đã lưu nạp hỏng thì vẫn lùi về CPU int8 như dưới.
    name = _saved_model() or (
        "VieNeu-TTS-v3-Turbo (GPU)" if cuda_is_available() else "VieNeu-TTS-v3-Turbo (int8)")
    def update_loading_message(model_name: str) -> None:
        spec = model_catalog.get(model_name)
        cached = spec is not None and model_catalog.is_downloaded(spec)
        model_status["message"] = (
            f"Đang nạp {model_name} từ ổ đĩa vào bộ nhớ..."
            if cached else f"Đang chuẩn bị {model_name}, tải các file còn thiếu nếu cần..."
        )

    try:
        update_loading_message(name)
        load_model_instance(name)
    except Exception as e:
        if name != "VieNeu-TTS-v3-Turbo (int8)":
            print(f"⚠️ Không nạp được {name} ({e}). Chuyển sang CPU int8.")
            try:
                update_loading_message("VieNeu-TTS-v3-Turbo (int8)")
                load_model_instance("VieNeu-TTS-v3-Turbo (int8)")
            except Exception as e2:
                model_status = {"state": "error", "message": _friendly_load_error(e2)}
                return
        else:
            model_status = {"state": "error", "message": _friendly_load_error(e)}
            return
    model_status = {"state": "ok", "message": "Sẵn sàng"}


# Nạp mô hình trong thread NỀN, không chặn lúc import.
#
# Trước đây lệnh nạp chạy thẳng ở cấp module nên uvicorn chỉ mở cổng SAU khi mô hình
# đã sẵn sàng. Hệ quả: cửa sổ ứng dụng không hiện gì trong lúc chờ, người dùng không
# biết máy đang chạy hay đã treo - và nhánh "loading" của /health lẫn màn hình chờ
# của giao diện đều thành code chết vì không bao giờ tới lượt.
#
# Giờ server mở cổng ngay, /health báo "loading", giao diện hiện màn hình chờ thật.
model_status: Dict[str, str] = {"state": "loading", "message": "Đang khởi động..."}
# Test đặt CIT_SKIP_MODEL_AUTOLOAD=1 (tests/conftest.py): thread này nạp model THẬT
# và gán đè biến `vieneu` mà test đã mock - xong giữa chừng một test là test hỏng
# chập chờn; máy chưa có cache còn tải ~300 MB.
if os.getenv("CIT_SKIP_MODEL_AUTOLOAD") != "1":
    threading.Thread(target=_startup_load, name="model-loader", daemon=True).start()


def _pcm16(audio_f32: np.ndarray) -> bytes:
    """Chuyển đổi mảng numpy float32 sang PCM16 bytes."""
    return (np.asarray(audio_f32) * 32767).clip(-32768, 32767).astype(np.int16).tobytes()


def _open_output(target, sr: int, fmt: str = "WAV"):
    """Mở file/bộ đệm audio để GHI, gắn sẵn thẻ "tạo bởi AI" (apps/ai_label.py).
    Mọi audio server xuất ra đi qua đây hoặc ``wav_file_to_mp3``."""
    kw = {"subtype": "PCM_16"} if fmt == "WAV" else {}
    out = sf.SoundFile(target, "w", samplerate=sr, channels=1, format=fmt, **kw)
    ai_label.label(out)
    return out


def _wav_bytes(audio_f32: np.ndarray, sr: int = SAMPLE_RATE) -> bytes:
    """Tạo WAV bytes chất lượng cao từ numpy audio."""
    buf = io.BytesIO()
    with _open_output(buf, sr) as out:
        out.write(np.asarray(audio_f32, dtype=np.float32))
    return buf.getvalue()


def _mp3_bytes(audio_f32: np.ndarray, sr: int = SAMPLE_RATE) -> bytes:
    """Tạo MP3 bytes từ numpy audio."""
    buf = io.BytesIO()
    try:
        with _open_output(buf, sr, "MP3") as out:
            out.write(np.asarray(audio_f32, dtype=np.float32))
    except Exception:
        # libsndfile không có bộ mã MP3: trả WAV
        return _wav_bytes(audio_f32, sr)
    return buf.getvalue()


def _apply_speed(audio_f32: np.ndarray, speed: float) -> np.ndarray:
    """Tăng/giảm tốc độ âm thanh nếu khác 1.0, giữ cao độ (WSOLA, xem
    ``vieneu_utils.time_stretch`` - phase vocoder của librosa làm giọng rè)."""
    if abs(speed - 1.0) < 0.02 or len(audio_f32) == 0:
        return audio_f32
    sr = current_model_info.get("sample_rate", SAMPLE_RATE)
    return time_stretch(audio_f32, float(speed), sr)


def _reads_vietnamese() -> bool:
    """Mô hình đang chạy đọc được tiếng Việt không. VieNeu (không liệt kê ngôn ngữ) và
    Supertonic (có "vi") đọc được; Kokoro thì không."""
    codes = {item["code"] for item in current_model_info.get("languages", [])}
    return not codes or "vi" in codes


def _dict_applies() -> bool:
    """Từ điển phát âm viết cách đọc bằng chính tả tiếng Việt ("KTX" -> "ký túc xá").
    Đưa cho mô hình không đọc tiếng Việt (Kokoro) thì nó đọc thành âm lạ, nên bỏ qua."""
    return _reads_vietnamese()


# Chữ chỉ tiếng Việt mới có (ă đ ơ ư và nguyên âm mang dấu thanh kiểu Việt). Bỏ
# qua é, à, ô, ê, ã, õ, ì, ò, ù... vì tiếng Pháp/Tây Ban Nha/Ý/Bồ Đào Nha cũng dùng.
_VIETNAMESE_ONLY_RE = re.compile(
    "[ăđơưạảấầẩẫậắằẳẵặẻẽẹếềểễệỉĩịỏọốồổỗộớờởỡợủũụứừửữựỳỷỹỵ]", re.IGNORECASE)
_WORD_RE = re.compile(r"[^\W\d_]+")
# Văn bản bị coi là tiếng Việt khi ít nhất 1/4 số từ (viết thường) có chữ chỉ tiếng
# Việt mới có. Câu tiếng Việt thường vượt xa ngưỡng này ("Xin chào các bạn": 1/3),
# câu tiếng Anh/Pháp gần như bằng 0.
_VIETNAMESE_WORD_RATIO = 0.25


def _looks_vietnamese(text: str) -> bool:
    """Đếm theo TỈ LỆ từ, không theo số chữ: câu tiếng Anh nhắc vài địa danh Việt
    ("We flew from Hà Nội to Đà Nẵng.") có tới 3 chữ chỉ tiếng Việt mà vẫn là câu
    tiếng Anh. Tên riêng viết hoa nên chỉ tính các từ viết thường; văn bản không có
    từ viết thường nào (toàn chữ hoa, một từ "Được.") thì tính mọi từ."""
    # Bỏ các thẻ [nghỉ 2s], [cười]... trước khi đếm: chữ trong thẻ không được đọc.
    words = _WORD_RE.findall(re.sub(r"\[[^\]\n]*\]", " ", text or ""))
    lower = [w for w in words if w[0].islower()] or words
    viet = sum(1 for w in lower if _VIETNAMESE_ONLY_RE.search(w))
    return viet > 0 and viet >= _VIETNAMESE_WORD_RATIO * len(lower)


def _require_language(text: str) -> None:
    """Mô hình không đọc tiếng Việt (Kokoro) mà nhận văn bản tiếng Việt -> 400.
    Không chặn thì phần mềm gọi API nhận về audio giọng nước ngoài đọc sai hết
    mà không có lỗi nào báo (app đang để Kokoro, phần mềm vẫn gửi tiếng Việt).
    Văn bản nước ngoài có tên riêng tiếng Việt vẫn đọc được (`_looks_vietnamese`)."""
    if _reads_vietnamese():
        return
    if _looks_vietnamese(text):
        raise HTTPException(
            status_code=400,
            detail="Mô hình đang dùng (Kokoro) không đọc được tiếng Việt. Hãy chuyển sang "
                   "VieNeu-TTS v3 Turbo trong Cài đặt của CIT Voice Studio.",
        )


def _text_segments(text: str, use_dict: bool = True) -> List[tuple]:
    """Tách văn bản tại thẻ ``[nghỉ 2s]`` -> ``[(đoạn, giây_nghỉ_sau), ...]``.

    Từ điển phát âm áp dụng SAU khi tách, trên từng đoạn: nếu áp trước, một mục
    từ điển có thể sửa mất chữ "nghỉ" trong thẻ.
    """
    _require_language(text)
    segments = split_pauses(text)
    if use_dict and _dict_applies():
        segments = [(pronunciation_settings.apply(seg), p) for seg, p in segments]
    if not any(seg for seg, _ in segments):
        raise HTTPException(status_code=400, detail="Văn bản không có chữ để đọc")
    return segments


def _synthesize(text: str, sr: int, infer_one, speed: float = 1.0, use_dict: bool = True) -> np.ndarray:
    """Đọc từng đoạn bằng ``infer_one(đoạn)`` rồi chèn đúng số giây im lặng của thẻ nghỉ.

    Tốc độ áp lên từng đoạn giọng nói, không lên khoảng lặng: "[nghỉ 2s]" vẫn là
    2 giây dù đọc nhanh 1.5x.
    """
    parts = []
    for seg, pause in _text_segments(text, use_dict):
        if seg:
            wav = infer_one(seg)
            if wav is not None and len(wav) > 0:
                parts.append(_apply_speed(np.asarray(wav, dtype=np.float32), speed))
        if pause > 0:
            parts.append(np.zeros(int(round(sr * pause)), dtype=np.float32))
    return np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)


# Văn bản dài được đọc theo khối cỡ này rồi ghi dần ra file: RAM chỉ cần đủ cho
# một khối (~4 phút audio), không phải cả bài. Trước đó cả bài nằm trong RAM -
# bài ~2 giờ làm backend hết bộ nhớ và cửa sổ app trắng (người dùng báo, 2026-09).
# Văn bản ngắn hơn ngưỡng này đọc y như cũ, một lần gọi.
LONG_TEXT_BLOCK_CHARS = 3000
_PARAGRAPH_SPLIT = re.compile(r"\n+")


def _text_blocks(text: str, limit: int = LONG_TEXT_BLOCK_CHARS) -> List[tuple]:
    """Chia văn bản dài thành ``[(khối, giây_im_lặng_sau), ...]`` tại ranh giới câu.

    Khoảng lặng giữa hai khối bằng đúng khoảng engine tự chèn ở ranh giới đó
    (cuối đoạn văn dài hơn cuối câu), nên chỗ cắt khối không nghe ra.
    """
    if len(text) <= limit:
        return [(text, 0.0)]
    units = []  # (chỉ số đoạn văn, câu)
    for pi, para in enumerate(p for p in _PARAGRAPH_SPLIT.split(text) if p.strip()):
        # split_into_sentences chỉ biết dấu câu Latin: văn bản Nhật/Trung/Hindi dài
        # (Kokoro) sẽ thành MỘT khối khổng lồ nằm trọn trong RAM. Cắt trước tại
        # 。！？। - văn bản tiếng Việt không có các dấu này nên chia y như cũ.
        for piece in (x for x in _NON_LATIN_STOP.split(para) if x.strip()):
            for sent in split_into_sentences(piece) or [piece.strip()]:
                units.append((pi, sent))

    blocks, cur, cur_len = [], [], 0
    for pi, sent in units:
        if cur and cur_len + len(sent) + 1 > limit:
            gap = V3_GAP_SILENCE["para"] if pi != cur[-1][0] else V3_GAP_SILENCE["sentence"]
            blocks.append((_join_units(cur), gap))
            cur, cur_len = [], 0
        cur.append((pi, sent))
        cur_len += len(sent) + 1
    if cur:
        blocks.append((_join_units(cur), 0.0))
    return blocks


def _join_units(units: List[tuple]) -> str:
    paras: Dict[int, List[str]] = {}
    for pi, sent in units:
        paras.setdefault(pi, []).append(sent)
    return "\n".join(_join_sentences(sents) for sents in paras.values())


def _join_sentences(sents: List[str]) -> str:
    """Nối câu bằng khoảng trắng, trừ sau dấu kết câu Nhật/Trung (không dùng khoảng trắng)."""
    out = ""
    for sent in sents:
        if out and not out.rstrip(CLOSING_MARKS).endswith(("。", "！", "？")):
            out += " "
        out += sent
    return out


def _silence(sr: int, seconds: float) -> np.ndarray:
    return np.zeros(int(round(sr * seconds)), dtype=np.float32)


def _synthesize_to_file(text: str, sr: int, infer_one, path, speed: float = 1.0,
                        use_dict: bool = True) -> int:
    """Như ``_synthesize`` nhưng ghi dần ra file WAV 16-bit, trả số mẫu đã ghi.

    Văn bản ngắn cho ra đúng từng byte như ``_wav_bytes(_synthesize(...))``.
    """
    written = 0
    with _open_output(str(path), sr) as out:
        for seg, pause in _text_segments(text, use_dict):
            if seg:
                prev_tail, gap_before = None, 0.0
                for block, gap in _text_blocks(seg):
                    wav = infer_one(block)
                    if wav is not None and len(wav) > 0:
                        wav = _apply_speed(np.asarray(wav, dtype=np.float32), speed)
                        pad = _natural_pad(prev_tail, wav, sr, gap_before)
                        if pad:
                            out.write(np.zeros(pad, dtype=np.float32))
                            written += pad
                        out.write(wav)
                        written += len(wav)
                        # Chỉ cần phần đuôi để đo im lặng: không giữ cả khối ~4 phút.
                        prev_tail = wav[-sr * 10:]
                    gap_before = gap
            if pause > 0:
                out.write(_silence(sr, pause))
                written += int(round(sr * pause))
    return written


def _synthesize_with_cues_to_file(text: str, sr: int, infer_one, path, speed: float = 1.0,
                                  use_dict: bool = True):
    """Như ``_synthesize_with_cues`` nhưng ghi dần ra file WAV. Trả ``(số mẫu, cues)``."""
    _require_language(text)
    units = build_units(text)
    if not any(display_text(u.text) for u in units):
        raise HTTPException(status_code=400, detail="Văn bản không có chữ để đọc")
    cues, cursor = [], 0
    with _open_output(str(path), sr) as out:
        for wav, cue_text in _unit_audio(units, sr, infer_one, speed, use_dict):
            if cue_text is not None:
                cues.extend(unit_cues(cue_text, cursor / sr, (cursor + len(wav)) / sr))
            out.write(wav)
            cursor += len(wav)
    return cursor, cues


def _natural_pad(prev_wav, next_wav: np.ndarray, sr: int, gap: float) -> int:
    """Số mẫu im lặng chèn ở một ranh giới câu/đoạn/khối tự nhiên. ``gap`` là TỔNG
    khoảng nghỉ tối thiểu như engine (``V3_GAP_SILENCE``): im lặng sẵn ở đuôi audio
    trước + đầu audio sau được tính vào, chỉ bù phần thiếu."""
    if prev_wav is None or gap <= 0:
        return 0
    return pause_pad_samples(prev_wav, next_wav, sr, gap)


def _unit_audio(units, sr: int, infer_one, speed: float, use_dict: bool):
    """Đọc từng đơn vị phụ đề, sinh lần lượt ``(audio, chữ_phụ_đề | None)``: audio
    giọng nói kèm chữ của nó, hoặc khoảng lặng (chữ ``None``). Ngắt câu/đoạn chỉ bù
    phần nghỉ còn thiếu; thẻ nghỉ chèn đúng số giây."""
    prev, pending = None, 0.0
    for unit in units:
        if unit.text.strip():
            speak = pronunciation_settings.apply(unit.text) if use_dict and _dict_applies() else unit.text
            wav = infer_one(speak)
            if wav is not None and len(wav) > 0:
                wav = _apply_speed(_trim_edges(np.asarray(wav, dtype=np.float32), sr), speed)
                pad = _natural_pad(prev, wav, sr, pending)
                if pad:
                    yield np.zeros(pad, dtype=np.float32), None
                yield wav, unit.text
                prev = wav
        if unit.tag_pause:
            if unit.pause_after > 0:
                yield _silence(sr, unit.pause_after), None
            prev, pending = None, 0.0
        else:
            pending = unit.pause_after


# Chuyển WAV -> MP3 theo từng đoạn: dùng chung với nút tải MP3 của lịch sử.
wav_file_to_mp3 = history_store.wav_file_to_mp3


def _temp_audio_path(suffix: str = ".wav") -> Path:
    fd, name = tempfile.mkstemp(prefix="cit-tts-", suffix=suffix)
    os.close(fd)
    return Path(name)


def _remove_quietly(*paths) -> None:
    for p in paths:
        try:
            Path(p).unlink(missing_ok=True)
        except OSError:
            pass


def _trim_edges(wav: np.ndarray, sr: int, margin_s: float = 0.04) -> np.ndarray:
    """Cắt im lặng đầu/cuối của một đơn vị đọc (giữ lề nhỏ) để khoảng nghỉ và
    mốc phụ đề do chính ta quyết định, không lẫn khoảng lặng thừa của model."""
    if len(wav) == 0:
        return wav
    peak = float(np.max(np.abs(wav)))
    loud = np.flatnonzero(np.abs(wav) > max(1e-3, 0.02 * peak))
    if len(loud) == 0:
        return wav[:0]
    m = int(sr * margin_s)
    return wav[max(0, loud[0] - m): min(len(wav), loud[-1] + 1 + m)]


def _synthesize_with_cues(text: str, sr: int, infer_one, speed: float = 1.0, use_dict: bool = True):
    """Như ``_synthesize`` nhưng đọc theo từng CÂU và trả kèm phụ đề.

    Mốc thời gian đo từ độ dài audio thật của từng câu (xem vieneu_utils.subtitles).
    Trả ``(wav, cues)``.
    """
    _require_language(text)
    units = build_units(text)
    if not any(display_text(u.text) for u in units):
        raise HTTPException(status_code=400, detail="Văn bản không có chữ để đọc")
    parts, cues, cursor = [], [], 0
    for wav, cue_text in _unit_audio(units, sr, infer_one, speed, use_dict):
        if cue_text is not None:
            cues.extend(unit_cues(cue_text, cursor / sr, (cursor + len(wav)) / sr))
        parts.append(wav)
        cursor += len(wav)
    audio = np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)
    return audio, cues


# -------------------------------------------------------------
# Web & Static UI Routes
# -------------------------------------------------------------
@app.get("/", include_in_schema=False)
async def ui():
    if (DIST_DIR / "index.html").exists():
        return FileResponse(DIST_DIR / "index.html", media_type="text/html")
    return Response("CIT Voice Studio UI not found. Build the frontend first.", status_code=404, media_type="text/plain")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # Logo CIT: Vite chép public/favicon.ico vào dist/, mà chỉ /assets được mount nên phải trả tay.
    ico = DIST_DIR / "favicon.ico"
    if ico.exists():
        return FileResponse(ico, media_type="image/x-icon")
    svg ='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y="82" font-size="82">🐆</text></svg>'
    return Response(svg, media_type="image/svg+xml")


def require_model():
    """Chặn sớm khi mô hình chưa nạp xong.

    Không có cái này thì mọi endpoint sẽ ném AttributeError trên `None` và người
    dùng nhận lỗi 500 khó hiểu, thay vì biết là chỉ cần chờ thêm.
    """
    if vieneu is None:
        raise HTTPException(
            status_code=503,
            detail=model_status.get("message", "Mô hình đang được nạp, vui lòng chờ."),
        )


@app.get("/health")
async def health():
    """Trạng thái mô hình, tần số thật và ngôn ngữ hỗ trợ. Chờ `status: ok` trước khi tạo audio.

    `supports_cloning` nói về khả năng tạo giọng trong ứng dụng, không phải API nhận file mẫu.
    """
    return {
        "status": model_status.get("state", "loading" if vieneu is None else "ok"),
        "message": model_status.get("message", ""),
        "sample_rate": current_model_info.get("sample_rate", SAMPLE_RATE),
        "engine": current_model_info.get("name", "VieNeu-TTS v3 Turbo (ONNX int8 CPU)"),
        "backend": current_model_info.get("backend", "onnx"),
        "precision": current_model_info.get("precision", "int8"),
        "device": current_model_info.get("device", "cpu"),
        # Mô hình đọc nhiều ngôn ngữ (Supertonic, Kokoro) liệt kê mã dùng được cho `language`;
        # VieNeu chỉ đọc tiếng Việt (xen tiếng Anh) nên danh sách rỗng.
        "languages": current_model_info.get("languages", []),
        "supports_cloning": vieneu is None or hasattr(vieneu, "add_voice"),
        # Thẻ cảm xúc: VieNeu [cười]…, Supertonic <laugh>…; Kokoro không có (bỏ thẻ).
        "supports_emotions": current_model_info.get("supports_emotions", True),
        # Mỗi lần tạo có ngữ điệu khác nhau, nên seed cố định ("Ổn định") có ý nghĩa.
        "supports_seed": current_model_info.get("supports_seed", True),
    }


@app.get("/voices")
async def voices():
    """Giọng của mô hình đang chạy, gồm giọng nhân bản đã lưu nếu mô hình hỗ trợ.

    Dùng `id` làm `voice_id`. Giọng đầu tiên là mặc định khi bỏ trống `voice_id`.
    Đổi mô hình thì phải lấy lại danh sách; không dùng giọng VieNeu cho Supertonic/Kokoro.
    Giọng Kokoro có thêm `language`: tiếng mà giọng được huấn luyện.
    """
    require_model()
    try:
        vs = list(vieneu.list_preset_voices())
        # Giọng mặc định của model (Hải Đăng ở v3 Turbo) lên đầu: giao diện chọn sẵn
        # giọng đầu danh sách, và API bỏ trống voice_id cũng dùng giọng này. Trước đây
        # thứ tự theo `featured` của file giọng nên giao diện chọn "Adam bựa" trong khi
        # API mặc định "Hải Đăng".
        default_voice = getattr(vieneu, "_default_voice", None)
        vs.sort(key=lambda item: (item[1] if isinstance(item, (tuple, list)) and len(item) == 2
                                  else str(item)) != default_voice)
        presets = getattr(vieneu, "_preset_voices", {})
        khz = current_model_info.get("sample_rate", SAMPLE_RATE) // 1000
        out = []
        for item in vs:
            if isinstance(item, (tuple, list)) and len(item) == 2:
                label, vid = item
                name_str = label
                v_id = vid
            else:
                name_str = str(item)
                v_id = str(item)

            # v3 Turbo và v3 Nano đều kèm sẵn `gender` + mô tả "Giới · Vùng · Phong
            # cách" trong preset; dùng thẳng thay vì đoán từ tên. Đoán theo chuỗi chỉ
            # còn là đường lui cho engine cũ (v1/v2) không có metadata: ở đó
            # "Nam Anh" (miền Bắc) vẫn bị đoán nhầm thành giọng miền Nam.
            preset = presets.get(v_id) if isinstance(presets.get(v_id), dict) else {}
            mo_ta = str(preset.get("description") or "").strip()
            gioi_tinh = str(preset.get("gender") or "").strip().lower()
            phan = [p.strip() for p in mo_ta.split("·")]
            vung = phan[1].lower() if len(phan) > 2 else ""

            if gioi_tinh not in ("male", "female"):
                name_lower = name_str.lower()
                is_female = any(x in name_lower for x in ["huyền", "linh", "mai", "nga", "nữ", "female", "thảo", "hương", "ngọc", "lan"])
                is_male = any(x in name_lower for x in ["đức", "nam", "tuấn", "hùng", "bảo", "quân", "male", "vĩnh", "minh"])
                gioi_tinh = "female" if is_female else ("male" if is_male else "neutral")

            if preset.get("language"):
                region = None  # giọng Kokoro: mỗi giọng một thứ tiếng, không có vùng miền
            elif vung in ("nam", "miền nam"):
                region = "South"
            elif vung in ("bắc", "miền bắc"):
                region = "North"
            elif vung == "đa ngôn ngữ":
                region = None  # giọng Supertonic: không có vùng miền tiếng Việt
            else:
                name_lower = name_str.lower()
                region = "South" if ("nam" in name_lower or "sg" in name_lower or "sài gòn" in name_lower) else "North"

            entry = {
                "id": v_id,
                "isCloned": bool(preset.get("is_custom", False)),
                # Giọng tác giả VieNeu chọn (xếp đầu danh sách), giao diện gắn ⭐.
                "featured": preset.get("featured") is not None,
                "name": v_id,
                "gender": gioi_tinh,
                "region": region,
                "description": f"{mo_ta} · {khz} kHz" if mo_ta else f"Giọng đọc {v_id} ({khz} kHz)",
            }
            if preset.get("language"):
                # Tiếng mà giọng được huấn luyện (Kokoro), mã như `languages` ở /health.
                # Giao diện chọn luôn ngôn ngữ đó khi người dùng chọn giọng.
                entry["language"] = str(preset["language"])
            out.append(entry)
        return out or [{"id": "Minh Đức", "name": "Minh Đức", "gender": "male", "region": "North", "description": "Giọng chuẩn Bắc"}]
    except Exception as e:
        return [{"id": "default", "name": f"⚠️ {e}", "gender": "neutral", "region": "North", "description": str(e)}]


# -------------------------------------------------------------
# Streaming TTS (Chunked Realtime)
# -------------------------------------------------------------
STREAM_RESPONSE = {
    200: {
        "description": "Luồng WAV mono PCM16: header WAV rồi dữ liệu audio; tần số nằm trong header WAV và /health.",
        "headers": {ai_label.HEADER: {
            "description": "Luôn là \"true\": audio do AI tạo ra. Luồng không mang thẻ trong file, "
                           "nên khi lưu hoặc đăng tải, bên gọi API tự ghi nhãn.",
            "schema": {"type": "string"},
        }},
        "content": {"audio/wav": {"schema": {"type": "string", "format": "binary"}}},
    }
}

AUDIO_RESPONSE = {
    200: {
        "description": "File WAV hoặc MP3. Kiểm tra Content-Type thực tế; X-Sample-Rate cho biết tần số mô hình.",
        "headers": {ai_label.HEADER: {
            "description": "Luôn là \"true\": audio do AI tạo ra; file cũng mang thẻ \"AI-generated\".",
            "schema": {"type": "string"},
        }},
        "content": {
            mime: {"schema": {"type": "string", "format": "binary"}}
            for mime in ("audio/wav", "audio/mpeg")
        },
    }
}


@app.get("/stream", response_class=StreamingResponse, responses=STREAM_RESPONSE)
async def stream(text: str, voice_id: Optional[str] = None, language: Optional[str] = None):
    """Đọc văn bản qua luồng WAV, dùng giọng có sẵn hoặc giọng đã lưu.

    `language`: mã từ `/health` (Supertonic; Kokoro đọc theo tiếng của giọng); VieNeu bỏ qua. Không nhận file giọng mẫu.
    Không có tham số tốc độ, temperature hay seed ở endpoint này.
    """
    require_model()
    _require_voice(voice_id)  # báo trước khi gửi header 200 của luồng
    lang_kw = _language_kwargs(language)
    engine = vieneu
    segments = _text_segments(text)
    sample_rate = engine.sample_rate
    def gen():
        h = io.BytesIO()
        with wave.open(h, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.setnframes(1_000_000_000)
        yield h.getvalue()

        t0 = time.perf_counter()
        first_at = None
        n_chunks = 0
        emitted = 0
        for seg, pause in segments:
            chunks = engine.infer_stream(seg, voice=voice_id or None, **lang_kw) if seg else ()
            for chunk in chunks:
                if chunk is None or len(chunk) == 0:
                    continue
                if first_at is None:
                    first_at = time.perf_counter() - t0
                    print(f"⚡ TTFA: {first_at * 1000:.0f} ms")
                n_chunks += 1
                emitted += len(chunk)
                yield _pcm16(chunk)
            if pause > 0:  # thẻ [nghỉ Ns]: phát khoảng lặng ngay trong luồng
                silence = np.zeros(int(round(sample_rate * pause)), dtype=np.float32)
                emitted += len(silence)
                yield _pcm16(silence)
        if first_at is not None:
            gen_time = time.perf_counter() - t0
            audio_s = emitted / sample_rate
            rtf = gen_time / audio_s if audio_s else 0
            print(f"✅ {n_chunks} chunks | audio {audio_s:.2f}s | gen {gen_time:.2f}s | RTF {rtf:.3f}")

    return StreamingResponse(gen(), media_type="audio/wav")


class StreamReq(BaseModel):
    text: str = Field(description="Văn bản cần đọc; nhận thẻ nghỉ [nghỉ 2s].")
    voice_id: Optional[str] = Field(default=None, description="id từ GET /voices; bỏ trống dùng giọng mặc định của mô hình đang chạy.")
    language: Optional[str] = Field(default=None, description="Mã ngôn ngữ từ GET /health cho Supertonic; bỏ trống để đoán theo chữ. Kokoro luôn đọc theo tiếng của giọng, VieNeu bỏ qua.")


@app.post("/stream", response_class=StreamingResponse, responses=STREAM_RESPONSE)
async def stream_post(req: StreamReq):
    """Như GET /stream, nhưng gửi text, voice_id và language bằng JSON."""
    return await stream(req.text, req.voice_id, req.language)


# -------------------------------------------------------------
# High-Quality TTS Synthesis (Batch / Full WAV / MP3)
# -------------------------------------------------------------
class TtsGenerateReq(BaseModel):
    text: str = Field(description="Văn bản cần đọc, không được để trống. Có thể chèn thẻ nghỉ [nghỉ 2s].")
    voice_id: Optional[str] = Field(default=None, description="id từ GET /voices, gồm giọng nhân bản đã lưu. Bỏ trống dùng giọng mặc định; không nhận file mẫu.")
    speed: float = Field(default=1.0, description="Hệ số tốc độ, phải lớn hơn 0; khuyến nghị 0.75–1.5. Không kéo giãn thẻ nghỉ.")
    temperature: float = Field(default=0.8, description="Độ ngẫu nhiên của VieNeu v3 Turbo; giao diện cho chọn 0.1–1.5. Nano, Supertonic và Kokoro bỏ qua.")
    silence_duration: float = Field(default=0.2, description="Tham số tương thích cũ, không có tác dụng ở generate và generate-with-subtitles. Dùng thẻ [nghỉ 2s].")
    format: str = Field(default="wav", description="wav hoặc mp3. generate có thể trả WAV nếu máy không mã hoá được MP3; kiểm tra Content-Type. Với phụ đề, đọc format trong JSON.")
    # False khi text đã được thay sẵn (nút "Nghe thử" của từ điển phát âm) - thay
    # hai lần sẽ đọc sai, vd. mục "ai" không phân biệt hoa/thường nuốt "ây ai".
    use_pronunciation_dict: bool = Field(default=True, description="Áp dụng từ điển phát âm của ứng dụng. Đặt false nếu client đã tự thay từ.")
    # Cố định seed thì cùng văn bản + cùng giọng ra y hệt nhau mỗi lần ("Giữ ổn
    # định"). None: lấy mẫu ngẫu nhiên như cũ, mỗi lần một ngữ điệu.
    seed: Optional[int] = Field(default=None, description="Cố định ngẫu nhiên để tái tạo kết quả với cùng văn bản, giọng, mô hình, thiết lập và môi trường; không tự cải thiện chất lượng.")
    # Mã ngôn ngữ ("en", "ja"…) cho mô hình đọc nhiều ngôn ngữ (Supertonic, Kokoro). Bỏ trống thì
    # mô hình tự nhận theo chữ; VieNeu bỏ qua tham số này.
    language: Optional[str] = Field(default=None, description="Mã ngôn ngữ từ GET /health (Supertonic); bỏ trống để đoán theo chữ. Kokoro luôn đọc theo tiếng của giọng, VieNeu bỏ qua.")


def _language_kwargs(language: Optional[str]) -> dict:
    """``{"lang": ...}`` khi mô hình đang chạy đọc được nhiều ngôn ngữ, ngược lại rỗng:
    phần mềm đã gửi ``language`` vẫn chạy bình thường khi app đổi về VieNeu."""
    codes = {item["code"] for item in current_model_info.get("languages", [])}
    if not codes or not language:
        return {}
    if language not in codes:
        raise HTTPException(
            status_code=400,
            detail=f"Mô hình đang chạy không đọc được ngôn ngữ '{language}'. "
                   f"Mã hợp lệ: {', '.join(sorted(codes))} (xem GET /health).")
    return {"lang": language}


def _require_voice(voice_id: Optional[str]) -> None:
    """Tên giọng không có trong mô hình đang chạy -> 400 kèm lời nhắc. Trước đây engine
    ném ValueError giữa chừng và API trả 500 "Voice '...' not found", khiến phần mềm
    gọi vào tưởng máy chủ hỏng. Bỏ trống = giọng mặc định, luôn hợp lệ."""
    if not voice_id:
        return
    presets = getattr(vieneu, "_preset_voices", None)
    if not isinstance(presets, dict):
        return  # engine cũ (v1/v2) không có danh mục: để engine tự báo
    resolve = getattr(vieneu, "resolve_voice_name", None)
    known = resolve(voice_id) if callable(resolve) else (voice_id if voice_id in presets else None)
    if known is None:
        raise HTTPException(
            status_code=400,
            detail=f"Không có giọng '{voice_id}' trong mô hình đang chạy. Xem danh sách giọng tại GET /voices "
                   "(voice_id là tên giọng, phân biệt dấu), hoặc bỏ trống để dùng giọng mặc định.",
        )


def _tts_infer(seed: Optional[int] = None, **kwargs):
    """``infer_one(đoạn)`` cho các đường đọc văn bản. Có ``seed`` thì đặt lại bộ
    sinh ngẫu nhiên trước MỖI đoạn, nên một đoạn luôn ra cùng audio dù đứng ở vị
    trí nào: Turbo ONNX lấy mẫu bằng ``np.random``, GPU bằng ``torch``, Nano nhận
    tham số ``seed`` riêng. Kiểm tra tên giọng ngay khi dựng (trước khi đọc)."""
    _require_voice(kwargs.get("voice"))
    if seed is None:
        return lambda seg: vieneu.infer(seg, **kwargs)
    import inspect

    seed = int(seed) % (2 ** 32)
    extra = {"seed": seed} if "seed" in inspect.signature(vieneu.infer).parameters else {}

    def run(seg):
        np.random.seed(seed)
        torch = sys.modules.get("torch")
        if torch is not None:
            try:
                torch.manual_seed(seed)
            except Exception:
                pass
        return vieneu.infer(seg, **kwargs, **extra)

    return run


class _ClientGone(Exception):
    """Trình duyệt đã huỷ request (nút Dừng) giữa lúc đang đọc."""


def _cancellable(infer_one, cancelled: Optional[threading.Event]):
    """Dừng ở đoạn kế tiếp khi ``cancelled`` được đặt (người dùng bấm Dừng)."""
    if cancelled is None:
        return infer_one

    def run(seg):
        if cancelled.is_set():
            raise _ClientGone()
        return infer_one(seg)

    return run


async def _run_while_connected(request: Request, work):
    """Chạy ``work(cancelled)`` trong threadpool và theo dõi kết nối: trình duyệt ngắt
    (nút Dừng huỷ fetch) thì đặt ``cancelled`` để ``work`` dừng ở đoạn kế tiếp.

    Trước đây server không biết người dùng đã dừng: đọc hết bài (giữ CPU suốt thời
    gian đó) rồi vẫn lưu vào lịch sử, nên bài "đã dừng" lại hiện ra trong Lịch sử."""
    import asyncio
    from starlette.concurrency import run_in_threadpool

    cancelled = threading.Event()

    async def watch():
        while not await request.is_disconnected():
            await asyncio.sleep(0.5)
        cancelled.set()

    watcher = asyncio.create_task(watch())
    try:
        return await run_in_threadpool(work, cancelled)
    except _ClientGone:
        print("⏹️ Người dùng đã dừng - bỏ bài đang đọc, không lưu lịch sử.")
        raise HTTPException(status_code=499, detail="Đã dừng theo yêu cầu, không lưu vào Bản đã tạo.")
    finally:
        watcher.cancel()


@app.post("/api/tts/generate", response_class=FileResponse, responses=AUDIO_RESPONSE)
async def generate_tts(req: TtsGenerateReq):
    """Tạo file WAV/MP3 từ văn bản bằng giọng có sẵn hoặc giọng nhân bản đã lưu.

    Trả audio nhị phân, không phải JSON. Không tạo giọng mới từ file mẫu.
    Header X-Duration-Seconds, X-Elapsed-Seconds, X-RTF và X-Sample-Rate mô tả kết quả.
    """
    require_model()
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Văn bản không được để trống")

    t0 = time.time()
    sr = current_model_info.get("sample_rate", SAMPLE_RATE)
    wav_path = _temp_audio_path(".wav")
    try:
        samples = _synthesize_to_file(
            req.text.strip(),
            sr,
            _tts_infer(req.seed, voice=req.voice_id or None, temperature=req.temperature,
                   **_language_kwargs(req.language)),
            wav_path,
            speed=req.speed,
            use_dict=req.use_pronunciation_dict,
        )
    except HTTPException:
        _remove_quietly(wav_path)
        raise
    except Exception as e:
        _remove_quietly(wav_path)
        raise HTTPException(status_code=500, detail=f"Lỗi tạo giọng nói: {e}")

    if samples == 0:
        _remove_quietly(wav_path)
        raise HTTPException(status_code=500, detail="Không tạo được dữ liệu âm thanh")

    duration_sec = samples / sr
    elapsed = time.time() - t0
    rtf = elapsed / duration_sec if duration_sec > 0 else 0

    # Trả thẳng từ file (FileResponse đọc dần) thay vì dựng cả bài trong RAM.
    path, media_type = wav_path, "audio/wav"
    if req.format.lower() == "mp3":
        mp3_path = wav_path.with_suffix(".mp3")
        if wav_file_to_mp3(wav_path, mp3_path):
            _remove_quietly(wav_path)
            path, media_type = mp3_path, "audio/mpeg"

    headers = {
        "X-Duration-Seconds": f"{duration_sec:.2f}",
        "X-Elapsed-Seconds": f"{elapsed:.2f}",
        "X-RTF": f"{rtf:.3f}",
        "X-Sample-Rate": str(sr),
    }

    return FileResponse(path, media_type=media_type, headers=headers,
                        background=BackgroundTask(_remove_quietly, path))


class TtsToHistoryReq(TtsGenerateReq):
    subtitles: bool = False
    voice_name: str = ""
    mode: str = "tts"


@app.post("/api/tts/generate-to-history", include_in_schema=False)
async def generate_tts_to_history(req: TtsToHistoryReq, request: Request):
    return await _run_while_connected(request, lambda cancelled: _generate_to_history(req, cancelled))


def _generate_to_history(req: TtsToHistoryReq, cancelled: Optional[threading.Event] = None):
    """Tạo giọng rồi lưu thẳng vào lịch sử trên ổ đĩa; chỉ trả thông tin mục lịch sử.

    Cho giao diện: audio không đi qua trình duyệt rồi lại gửi ngược lên để lưu.
    Bài ~2 giờ (~690 MB WAV) làm cửa sổ app trắng khi trình duyệt vừa giữ, vừa
    phát, vừa tải khối đó lên (người dùng báo, 2026-09). Giao diện phát và tải
    file qua ``/api/history/{id}/...``.
    """
    require_model()
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Văn bản không được để trống")
    t0 = time.time()
    sr = current_model_info.get("sample_rate", SAMPLE_RATE)
    text = req.text.strip()
    infer_one = _cancellable(
        _tts_infer(req.seed, voice=req.voice_id or None, temperature=req.temperature,
                   **_language_kwargs(req.language)), cancelled)
    wav_path = history_store.new_temp_path(".wav")
    try:
        if req.subtitles:
            samples, cues = _synthesize_with_cues_to_file(
                text, sr, infer_one, wav_path, speed=req.speed, use_dict=req.use_pronunciation_dict)
        else:
            samples, cues = _synthesize_to_file(
                text, sr, infer_one, wav_path, speed=req.speed, use_dict=req.use_pronunciation_dict), None
        if samples == 0:
            raise HTTPException(status_code=500, detail="Không tạo được dữ liệu âm thanh")
        duration_sec = samples / sr
        srt = to_srt(cues) if cues else None
        if cancelled is not None and cancelled.is_set():
            raise _ClientGone()  # dừng đúng lúc đọc xong: vẫn không lưu
        entry = history_store.add_file(
            wav_path, text=text, voice_id=req.voice_id or "", voice_name=req.voice_name or req.voice_id or "",
            duration_seconds=duration_sec, fmt="wav", mode=req.mode, subtitles=srt,
        )
    except (HTTPException, _ClientGone):
        _remove_quietly(wav_path)
        raise
    except Exception as e:
        _remove_quietly(wav_path)
        raise HTTPException(status_code=500, detail=f"Lỗi tạo giọng nói: {e}")
    elapsed = time.time() - t0
    return {
        "entry": entry,
        "sample_rate": sr,
        "duration_seconds": round(duration_sec, 3),
        "elapsed_seconds": round(elapsed, 3),
        "rtf": round(elapsed / duration_sec, 3) if duration_sec else 0,
        "srt": srt,
    }


class SrtParseReq(BaseModel):
    srt: str


def _parse_srt_or_400(content: str):
    try:
        return parse_srt(content or "")
    except SrtError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/srt/parse", include_in_schema=False)
async def srt_parse(req: SrtParseReq):
    """Đọc trước file phụ đề để giao diện hiện danh sách câu."""
    cues = _parse_srt_or_400(req.srt)
    return {
        "cues": [{"start": round(c.start, 3), "end": round(c.end, 3), "text": c.text} for c in cues],
        "duration_seconds": round(max(c.end for c in cues), 3),
    }


class DubSrtReq(BaseModel):
    srt: str
    voice_id: Optional[str] = None
    voice_name: str = ""
    speed: float = 1.0
    temperature: float = 0.8
    use_pronunciation_dict: bool = True
    language: Optional[str] = None


@app.post("/api/tts/dub-srt-to-history", include_in_schema=False)
async def dub_srt_to_history(req: DubSrtReq, request: Request):
    return await _run_while_connected(request, lambda cancelled: _dub_srt_to_history(req, cancelled))


def _dub_srt_to_file(cues, sr: int, infer_one, path, speed: float = 1.0,
                     use_dict: bool = True) -> tuple:
    """Lồng tiếng theo mốc phụ đề, ghi dần ra file WAV dài đúng timeline.

    Trả ``(số mẫu, DubStats)``. Từng câu đọc riêng, cắt im lặng hai mép để câu
    vào đúng mốc; khớp khung theo ``vieneu_utils.dubbing``."""
    stats = dubbing.DubStats()
    cursor = 0  # số mẫu đã ghi
    with _open_output(str(path), sr) as out:
        for cue in cues:
            speak = pronunciation_settings.apply(cue.text) if use_dict and _dict_applies() else cue.text
            wav = infer_one(speak)
            if wav is None or len(wav) == 0:
                continue
            wav = _trim_edges(np.asarray(wav, dtype=np.float32), sr)
            if len(wav) == 0:
                continue
            # Tốc độ người chọn và phần tăng thêm cho vừa khung gộp thành MỘT lần đổi
            # tốc độ: đổi hai lần liên tiếp thì méo tiếng cộng dồn.
            rate = dubbing.fit_rate(len(wav) / speed / sr, cue.end - cue.start)
            wav = _apply_speed(wav, speed * rate)
            start = dubbing.place(cue.start, cursor / sr, stats.cues > 0)
            start_sample = int(round(start * sr))
            if start_sample > cursor:
                out.write(np.zeros(start_sample - cursor, dtype=np.float32))
                cursor = start_sample
            stats.record(cue, cursor / sr, len(wav) / sr, rate)
            out.write(wav)
            cursor += len(wav)
        # Audio dài ít nhất tới hết câu phụ đề cuối, cho khớp độ dài video.
        tail = int(round(max(c.end for c in cues) * sr))
        if stats.cues and tail > cursor:
            out.write(np.zeros(tail - cursor, dtype=np.float32))
            cursor = tail
    return cursor, stats


def _dub_srt_to_history(req: DubSrtReq, cancelled: Optional[threading.Event] = None):
    require_model()
    cues = _parse_srt_or_400(req.srt)
    _require_language("\n".join(c.text for c in cues))
    t0 = time.time()
    sr = current_model_info.get("sample_rate", SAMPLE_RATE)
    infer_one = _cancellable(
        _tts_infer(None, voice=req.voice_id or None, temperature=req.temperature,
                   **_language_kwargs(req.language)), cancelled)
    wav_path = history_store.new_temp_path(".wav")
    try:
        samples, stats = _dub_srt_to_file(
            cues, sr, infer_one, wav_path, speed=req.speed, use_dict=req.use_pronunciation_dict)
        if stats.cues == 0:
            raise HTTPException(status_code=500, detail="Không tạo được dữ liệu âm thanh")
        duration_sec = samples / sr
        srt = to_srt(stats.finish())
        if cancelled is not None and cancelled.is_set():
            raise _ClientGone()
        entry = history_store.add_file(
            wav_path, text="\n".join(c.text for c in cues), voice_id=req.voice_id or "",
            voice_name=req.voice_name or req.voice_id or "", duration_seconds=duration_sec,
            fmt="wav", mode="pdf", subtitles=srt,
        )
    except (HTTPException, _ClientGone):
        _remove_quietly(wav_path)
        raise
    except Exception as e:
        _remove_quietly(wav_path)
        raise HTTPException(status_code=500, detail=f"Lỗi lồng tiếng: {e}")
    elapsed = time.time() - t0
    return {
        "entry": entry,
        "sample_rate": sr,
        "duration_seconds": round(duration_sec, 3),
        "elapsed_seconds": round(elapsed, 3),
        "rtf": round(elapsed / duration_sec, 3) if duration_sec else 0,
        "srt": srt,
        "stats": {
            "cues": stats.cues,
            "sped_up": stats.sped_up,
            "pushed": stats.pushed,
            "max_push_seconds": round(stats.max_push_seconds, 2),
        },
    }


@app.post("/api/tts/generate-with-subtitles")
async def generate_tts_with_subtitles(req: TtsGenerateReq):
    """Như ``/api/tts/generate`` nhưng trả JSON gồm audio (base64) + phụ đề SRT.

    Đọc theo từng câu để đo mốc thời gian thật của mỗi câu; phụ đề hiện văn bản
    GỐC (trước từ điển phát âm), bỏ thẻ cảm xúc và thẻ nghỉ.
    """
    require_model()
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Văn bản không được để trống")
    t0 = time.time()
    sr = current_model_info.get("sample_rate", SAMPLE_RATE)
    wav_path = _temp_audio_path(".wav")
    mp3_path = wav_path.with_suffix(".mp3")
    try:
        samples, cues = _synthesize_with_cues_to_file(
            req.text.strip(),
            sr,
            _tts_infer(req.seed, voice=req.voice_id or None, temperature=req.temperature,
                   **_language_kwargs(req.language)),
            wav_path,
            speed=req.speed,
            use_dict=req.use_pronunciation_dict,
        )
        if samples == 0:
            raise HTTPException(status_code=500, detail="Không tạo được dữ liệu âm thanh")
        fmt = "wav"
        if req.format.lower() == "mp3" and wav_file_to_mp3(wav_path, mp3_path):
            fmt = "mp3"
        audio_data = (mp3_path if fmt == "mp3" else wav_path).read_bytes()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo giọng nói: {e}")
    finally:
        _remove_quietly(wav_path, mp3_path)
    duration_sec = samples / sr
    elapsed = time.time() - t0
    return {
        "audio_base64": base64.b64encode(audio_data).decode("ascii"),
        "format": fmt,
        "sample_rate": sr,
        "duration_seconds": round(duration_sec, 3),
        "elapsed_seconds": round(elapsed, 3),
        "rtf": round(elapsed / duration_sec, 3) if duration_sec else 0,
        "srt": to_srt(cues),
        "cues": [{"start": round(c.start, 3), "end": round(c.end, 3), "text": c.text} for c in cues],
    }


# Engine chỉ dùng tối đa 8 giây có tiếng của file mẫu (sau khi cắt im lặng hai đầu);
# 30 giây là đủ dư mà không phải đọc cả bản ghi dài hàng giờ.
REF_AUDIO_MAX_READ_SECONDS = 30.0


def _normalize_ref_audio(file_bytes: bytes, original_filename: str = "sample.wav") -> str:
    """
    Chuyển đổi dữ liệu âm thanh mẫu bất kỳ (WAV, MP3, WebM, OGG, M4A, FLAC, AAC...)
    thành file WAV 16-bit PCM Mono chuẩn hóa để Vieneu và SoundFile luôn nạp được 100%.
    """
    tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp_out_path = tmp_out.name
    tmp_out.close()
    # Chỉ đọc phần đầu: engine dùng tối đa 8 giây có tiếng. File ghi âm 60 phút
    # từng bị đọc trọn rồi cắt im lặng trên cả khối - chậm và dễ hết RAM.
    max_s = REF_AUDIO_MAX_READ_SECONDS

    # 1. Thử đọc bằng soundfile (WAV, FLAC, OGG, MP3...)
    try:
        with sf.SoundFile(io.BytesIO(file_bytes)) as f:
            data = f.read(frames=int(f.samplerate * max_s), dtype="float32", always_2d=True)
            sr = f.samplerate
        sf.write(tmp_out_path, data.mean(axis=1), sr, format="WAV", subtype="PCM_16")
        return tmp_out_path
    except Exception:
        pass

    # 2. Thử đọc bằng librosa (hỗ trợ nhiều định dạng qua audioread/soxr/soundfile)
    try:
        import librosa
        data, sr = librosa.load(io.BytesIO(file_bytes), sr=48000, mono=True, duration=max_s)
        sf.write(tmp_out_path, data, 48000, format="WAV", subtype="PCM_16")
        return tmp_out_path
    except Exception:
        pass

    # 3. Thử đọc bằng pydub nếu có (cần ffmpeg - máy người dùng thường không có)
    try:
        from pydub import AudioSegment
        seg = AudioSegment.from_file(io.BytesIO(file_bytes))[: int(max_s * 1000)]
        seg = seg.set_channels(1).set_frame_rate(48000)
        seg.export(tmp_out_path, format="wav")
        return tmp_out_path
    except Exception:
        pass

    # Trước đây lưu nguyên file gốc rồi để engine báo "Format not recognised" -
    # người dùng nhận lỗi khó hiểu với M4A/MP4/AAC/WMA/WebM (máy không có ffmpeg).
    _remove_quietly(tmp_out_path)
    suffix = Path(original_filename).suffix.lower() or "không rõ"
    raise HTTPException(
        status_code=400,
        detail=(f"Không đọc được file âm thanh mẫu (định dạng {suffix}). "
                "Hãy dùng file MP3, WAV, FLAC hoặc OGG, hoặc chọn file qua giao diện "
                "để app tự chuyển đổi."),
    )


# -------------------------------------------------------------
# Micro và file dùng chung cam kết quyền sử dụng cục bộ, không xác minh danh tính.
# Nhân bản thẳng từ file tải lên (/api/tts/clone) đã bỏ ở 1.0.2.
# -------------------------------------------------------------
# Giao diện cắt đoạn mẫu còn tối đa 15 giây; chừa nửa giây cho sai số giải mã.
MAX_REF_SECONDS = 15.5


def _duration_seconds(wav_path: str) -> float:
    try:
        return sf.info(wav_path).duration
    except Exception:
        return 0.0


@app.post("/api/voices/custom", include_in_schema=False)
async def add_custom_voice(
    name: str = Form(...),
    ref_audio: UploadFile = File(...),
    denoise: bool = Form(True),
    input_source: Literal["recording", "file"] = Form("recording"),
    rights_confirmed: bool = Form(False),
    rights_version: str = Form(""),
):
    """Nhân giọng từ âm thanh mẫu và lưu lại vĩnh viễn dưới `name` để chọn dùng sau này."""
    require_model()
    ten = (name or "").strip()
    if not ten:
        raise HTTPException(status_code=400, detail="Tên giọng không được để trống")
    if not hasattr(vieneu, "add_voice"):
        raise HTTPException(
            status_code=400,
            detail="Mô hình đang dùng không hỗ trợ nhân bản giọng. Hãy chuyển về VieNeu-TTS v3 Turbo.",
        )
    if ten in getattr(vieneu, "_preset_voices", {}):
        raise HTTPException(status_code=409, detail="Tên giọng đã tồn tại. Vui lòng chọn tên khác.")
    if not rights_confirmed:
        raise HTTPException(status_code=400, detail="Hãy xác nhận quyền nhân bản và sử dụng giọng trước khi lưu.")
    if rights_version != terms.TERMS_VERSION:
        raise HTTPException(status_code=409, detail="Cam kết đã được cập nhật. Mở lại tab Nhân bản giọng và xác nhận lại.")

    file_bytes = await ref_audio.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File âm thanh mẫu không có dữ liệu")
    tmp_ref_path = _normalize_ref_audio(file_bytes, ref_audio.filename or "sample.wav")

    try:
        duration = _duration_seconds(tmp_ref_path)
        if not 3 <= duration <= MAX_REF_SECONDS:
            raise HTTPException(status_code=400, detail="Đoạn mẫu cần dài 3–15 giây. Nên đọc tự nhiên khoảng 3–8 giây, không nhạc nền.")
        # Cam kết và dữ liệu giọng được lưu nguyên tử trong cùng một file; xoá
        # giọng sẽ xoá luôn cam kết. Không lưu file gốc, IP hoặc danh tính người dùng.
        authorization = {
            "confirmed": True,
            "statement": terms.VOICE_RIGHTS_STATEMENT,
            "terms_version": terms.TERMS_VERSION,
            "accepted_at": datetime.now(timezone.utc).isoformat(),
            "input_source": input_source,
            "verification": "user_declaration",
        }
        with model_lock:
            if ten in getattr(vieneu, "_preset_voices", {}):
                raise HTTPException(status_code=409, detail="Tên giọng đã tồn tại. Vui lòng chọn tên khác.")
            voice_id = vieneu.add_voice(
                ten, tmp_ref_path, denoise=denoise, save=True, save_path=_custom_voices_path(),
                authorization=authorization,
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lưu giọng tuỳ chỉnh: {e}")
    finally:
        _remove_quietly(tmp_ref_path)

    return {"status": "ok", "voice_id": voice_id, "name": ten}


@app.get("/api/voices/consent", include_in_schema=False)
def consent_info():
    """Cam kết quyền giọng mà tab Nhân bản giọng hiển thị, kèm phiên bản điều khoản."""
    return {"rights_statement": terms.VOICE_RIGHTS_STATEMENT, "terms_version": terms.TERMS_VERSION}


@app.delete("/api/voices/custom/{name}", include_in_schema=False)
async def remove_custom_voice(name: str):
    """Xoá một giọng tuỳ chỉnh đã lưu."""
    require_model()
    if not hasattr(vieneu, "remove_voice"):
        raise HTTPException(
            status_code=400,
            detail="Mô hình đang dùng không hỗ trợ xoá giọng tuỳ chỉnh.",
        )
    preset = getattr(vieneu, "_preset_voices", {}).get(name)
    if preset is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy giọng tuỳ chỉnh.")
    if not preset.get("is_custom", False):
        raise HTTPException(status_code=400, detail="Không thể xoá giọng có sẵn.")
    # Khoá cache tính từ dữ liệu giọng, nên phải lấy đường dẫn trước khi xoá.
    preview = _voice_preview_path(name)
    try:
        vieneu.remove_voice(name, save=True, save_path=_custom_voices_path())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xoá giọng tuỳ chỉnh: {e}")
    preview.unlink(missing_ok=True)
    return {"status": "ok"}


# -------------------------------------------------------------
# Nghe thử giọng trước khi chọn
# -------------------------------------------------------------
VOICE_PREVIEW_TEXT = (
    "Xin chào, đây là giọng đọc mẫu của CIT Voice Studio. "
    "Chúc bạn một ngày làm việc thật hiệu quả."
)


def _preview_text(language: Optional[str] = None, voice_id: Optional[str] = None) -> tuple:
    """``(câu mẫu, tham số ngôn ngữ)``. Supertonic đọc câu mẫu bằng ngôn ngữ đang chọn
    trên giao diện (không có thì tiếng Anh). Kokoro LUÔN dùng câu mẫu bằng tiếng của
    chính giọng: engine bỏ qua `lang` và đọc theo tiếng của giọng, nên câu tiếng Anh
    cho giọng Nhật chỉ ra âm vô nghĩa. Câu mẫu nằm trong khoá cache
    (`_voice_preview_path`), nên đổi câu là đổi file."""
    codes = {item["code"] for item in current_model_info.get("languages", [])}
    if not codes:
        return VOICE_PREVIEW_TEXT, {}
    kokoro = model_catalog.is_kokoro(current_model_info.get("name"))
    if kokoro:
        from apps.kokoro_engine import PREVIEW_TEXTS
    else:
        from apps.supertonic_engine import PREVIEW_TEXTS

    if kokoro or language not in PREVIEW_TEXTS or language not in codes:
        preset = getattr(vieneu, "_preset_voices", {}).get(voice_id)
        language = preset.get("language") if isinstance(preset, dict) else None
        if language not in PREVIEW_TEXTS:
            language = "en"
    return PREVIEW_TEXTS[language], {"lang": language}


def voice_preview_dir() -> Path:
    return Path(os.getenv("LOCALAPPDATA") or Path.home()) / "CitVoiceStudio" / "voice_previews"


def _voice_fingerprint(voice_id: str) -> str:
    """Băm dữ liệu giọng (vector giọng, mã tham chiếu, style). Bộ giọng 3.8.3 giữ
    tên cũ nhưng đổi dữ liệu 8 giọng (Trúc Ly, Mai Anh, …); khoá chỉ theo tên thì
    app cứ phát bản mẫu của giọng cũ."""
    import hashlib

    preset = getattr(vieneu, "_preset_voices", {}).get(voice_id)
    h = hashlib.sha1()
    for field in ("speaker_emb", "codes", "style"):
        value = preset.get(field) if isinstance(preset, dict) else None
        if isinstance(value, np.ndarray):
            h.update(field.encode())
            h.update(np.ascontiguousarray(value).tobytes())
    return h.hexdigest()


def _voice_preview_path(voice_id: str, text: str = VOICE_PREVIEW_TEXT) -> Path:
    """Mỗi (mô hình, giọng, dữ liệu giọng, câu mẫu) một file: Turbo và Nano cùng
    tên giọng nhưng đọc khác nhau, còn đổi dữ liệu giọng hay câu mẫu thì bản cũ
    tự hết hiệu lực."""
    import hashlib

    key = "\n".join([
        current_model_info.get("name", ""),
        str(current_model_info.get("sample_rate", SAMPLE_RATE)),
        voice_id,
        _voice_fingerprint(voice_id),
        # Đổi engine thì cách đọc/ngắt nghỉ đổi theo: bản mẫu cũ tự hết hiệu lực.
        "engine vieneu 3.8.3",
        text,
    ])
    return voice_preview_dir() / f"{hashlib.sha1(key.encode('utf-8')).hexdigest()}.wav"


@app.get("/api/voices/preview", include_in_schema=False)
async def voice_preview(voice_id: str, language: Optional[str] = None):
    """Đọc câu mẫu bằng giọng `voice_id`. Lần đầu tổng hợp (vài giây), các lần sau
    phát lại từ cache trên đĩa. Không áp từ điển phát âm để bản cache ổn định."""
    require_model()
    if voice_id not in getattr(vieneu, "_preset_voices", {}):
        raise HTTPException(status_code=404, detail="Không tìm thấy giọng này ở mô hình đang dùng.")

    text, lang_kw = _preview_text(language, voice_id)
    path = _voice_preview_path(voice_id, text)
    if path.is_file():
        return FileResponse(path, media_type="audio/wav", headers={"Cache-Control": "no-store"})

    sr = current_model_info.get("sample_rate", SAMPLE_RATE)
    try:
        wav = _synthesize(
            text, sr, lambda seg: vieneu.infer(seg, voice=voice_id, **lang_kw), use_dict=False
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi đọc mẫu giọng: {e}")
    if len(wav) == 0:
        raise HTTPException(status_code=500, detail="Không tạo được âm thanh mẫu")

    data = _wav_bytes(wav, sr)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
    except OSError as e:
        # Không ghi được cache thì vẫn phát được, chỉ là lần sau phải đọc lại.
        print(f"[Nghe thử] Không lưu được cache mẫu giọng: {e}")
    return Response(content=data, media_type="audio/wav", headers={"Cache-Control": "no-store"})


# -------------------------------------------------------------
# Multi-Speaker Conversation & Podcast Mode
# -------------------------------------------------------------
class DialogueTurn(BaseModel):
    speaker: str = Field(description="Tên nhân vật của lượt thoại.")
    text: str = Field(description="Nội dung lượt thoại; nhận thẻ nghỉ và cảm xúc theo mô hình.")
    voice_id: Optional[str] = Field(default=None, description="id từ /voices; ưu tiên hơn speaker_mapping. Bỏ trống cả hai dùng giọng mặc định.")


class ConversationReq(BaseModel):
    script: Optional[str] = Field(default=None, description="Kịch bản nhiều dòng dạng [MC]: Xin chào. Khi script có nội dung, được ưu tiên hơn turns.")
    turns: Optional[List[DialogueTurn]] = Field(default=None, description="Danh sách lượt thoại; dùng khi không gửi script có nội dung.")
    speaker_mapping: Optional[Dict[str, str]] = Field(default=None, description="Ánh xạ tên nhân vật sang id giọng từ /voices.")
    silence_duration: float = Field(default=0.4, description="Khoảng nghỉ giữa lượt, đơn vị giây; thực tế tối thiểu 0.05 giây.")
    speed: float = Field(default=1.0, description="Hệ số tốc độ lớn hơn 0; khuyến nghị 0.75–1.5. Giữ nguyên khoảng nghỉ giữa lượt và thẻ nghỉ.")
    temperature: float = Field(default=0.8, description="Độ ngẫu nhiên của VieNeu v3 Turbo; Nano, Supertonic và Kokoro bỏ qua.")
    seed: Optional[int] = Field(default=None, description="Cố định ngẫu nhiên như ở /api/tts/generate.")
    format: str = Field(default="wav", description="wav hoặc mp3.")
    language: Optional[str] = Field(default=None, description="Mã từ /health, áp dụng chung mọi lượt thoại trên Supertonic. Kokoro: mỗi giọng đọc theo tiếng của nó. VieNeu bỏ qua.")


@app.post("/api/tts/conversation", response_class=Response, responses=AUDIO_RESPONSE)
async def generate_conversation(req: ConversationReq):
    """Tạo hội thoại đa người nói / Podcast hoàn chỉnh."""
    require_model()
    turns_list: List[DialogueTurn] = []

    # 1. Parse from raw script if turns list is not provided
    if req.script and req.script.strip():
        # Example syntax: [Người 1]: Xin chào | hoặc Speaker 1: Xin chào
        pattern = re.compile(r"^\s*(?:\[([^\]]+)\]|([^:]+))\s*:\s*(.+)$", re.MULTILINE)
        matches = pattern.findall(req.script)
        if matches:
            for m in matches:
                spk = (m[0] or m[1]).strip()
                content = m[2].strip()
                if spk and content:
                    turns_list.append(DialogueTurn(speaker=spk, text=content))
        else:
            # Fallback: split by lines
            lines = [line.strip() for line in req.script.split("\n") if line.strip()]
            for i, line in enumerate(lines):
                spk = f"Người {(i % 2) + 1}"
                turns_list.append(DialogueTurn(speaker=spk, text=line))
    elif req.turns:
        turns_list = req.turns

    if not turns_list:
        raise HTTPException(status_code=400, detail="Không tìm thấy các lượt thoại trong kịch bản")

    mapping = req.speaker_mapping or {}
    lang_kw = _language_kwargs(req.language)
    sr = current_model_info.get("sample_rate", SAMPLE_RATE)
    silence_arr = np.zeros(int(sr * max(0.05, req.silence_duration)), dtype=np.float32)

    def turn_voice(turn):
        spk = turn.speaker.strip()
        return turn.voice_id or mapping.get(spk) or mapping.get(spk.lower()) or None

    # Kiểm tra giọng của mọi lượt TRƯỚC khi đọc: trước đây lượt có giọng sai bị bỏ
    # qua trong im lặng (vòng dưới nuốt lỗi), bài ra thiếu câu mà không ai biết.
    for turn in turns_list:
        try:
            _require_voice(turn_voice(turn))
            _require_language(turn.text)
        except HTTPException as e:
            raise HTTPException(status_code=400, detail=f"Lượt của '{turn.speaker.strip()}': {e.detail}") from e

    all_wavs = []
    t0 = time.time()

    for i, turn in enumerate(turns_list):
        spk_name = turn.speaker.strip()
        voice_id = turn_voice(turn)

        try:
            # Tốc độ áp theo từng lượt (trong _synthesize) - khoảng lặng giữa lượt
            # và thẻ [nghỉ Ns] giữ đúng số giây đã đặt.
            chunk_wav = _synthesize(
                turn.text.strip(),
                sr,
                _tts_infer(req.seed, voice=voice_id, temperature=req.temperature, **lang_kw),
                speed=req.speed,
            )
            if chunk_wav is None or len(chunk_wav) == 0:
                raise ValueError("Mô hình không trả về âm thanh")
            all_wavs.append(chunk_wav)
            if i < len(turns_list) - 1:
                all_wavs.append(silence_arr)
        except Exception as e:
            print(f"⚠️ Lỗi đoạn hội thoại {i+1} ({spk_name}): {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Không tạo được lượt {i+1} của '{spk_name}'. Vui lòng thử lại; chưa xuất audio vì bài đọc chưa đầy đủ.",
            ) from e

    full_wav = np.concatenate(all_wavs)

    duration_sec = len(full_wav) / sr
    elapsed = time.time() - t0

    if req.format.lower() == "mp3":
        audio_data = _mp3_bytes(full_wav, sr)
        # _mp3_bytes trả WAV nếu máy thiếu bộ mã MP3; MIME phải khớp dữ liệu.
        media_type = "audio/wav" if audio_data.startswith(b"RIFF") else "audio/mpeg"
    else:
        audio_data = _wav_bytes(full_wav, sr)
        media_type = "audio/wav"

    headers = {
        "X-Duration-Seconds": f"{duration_sec:.2f}",
        "X-Elapsed-Seconds": f"{elapsed:.2f}",
        "X-Turns-Count": str(len(turns_list)),
        "X-Sample-Rate": str(sr),
    }

    return Response(content=audio_data, media_type=media_type, headers=headers)


# -------------------------------------------------------------
# Document & PDF Text Extraction
# -------------------------------------------------------------
@app.post("/api/pdf/extract", include_in_schema=False)
async def extract_pdf_text(file: UploadFile = File(...)):
    """Trích xuất nội dung văn bản từ file PDF, Word (.docx) hoặc TXT."""
    filename = file.filename or ""
    content = await file.read()
    ext = Path(filename).suffix.lower()

    if ext == ".doc":
        # Định dạng nhị phân Word 97-2003: đọc được cần Word/LibreOffice trên máy.
        raise HTTPException(
            status_code=415,
            detail="File .doc (Word 97–2003) chưa được hỗ trợ. Hãy mở bằng Word, "
                   "chọn Lưu thành (Save As) → định dạng .docx rồi tải lại.",
        )

    if ext == ".docx":
        from vieneu_utils.docx_extract import DocxError, extract_docx
        try:
            text, page_count = extract_docx(content)
        except DocxError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if not text.strip():
            raise HTTPException(status_code=400, detail="File .docx không có chữ để đọc.")
        return {"text": text, "page_count": page_count, "pages": [text], "filename": filename}

    if ext == ".txt":
        try:
            text = content.decode("utf-8")
        except Exception:
            text = content.decode("latin-1", errors="ignore")
        return {"text": text, "page_count": 1, "pages": [text]}

    # Try PyMuPDF (fitz) or pypdf
    pages_text = []
    try:
        import fitz
        doc = fitz.open(stream=content, filetype="pdf")
        for page in doc:
            pages_text.append(page.get_text())
    except Exception:
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(content))
            for page in reader.pages:
                pages_text.append(page.extract_text() or "")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Không thể giải mã PDF: {e}")

    full_text = "\n\n".join([p.strip() for p in pages_text if p.strip()])
    return {
        "text": full_text,
        "page_count": len(pages_text),
        "pages": pages_text,
        "filename": filename,
    }


# -------------------------------------------------------------
# Convert WAV to MP3 API
# -------------------------------------------------------------
@app.post("/api/audio/mp3", include_in_schema=False)
async def convert_to_mp3_endpoint(file: UploadFile = File(...)):
    """Nhận file WAV và chuyển đổi sang MP3 chất lượng cao."""
    try:
        content = await file.read()
        data, sr = sf.read(io.BytesIO(content), dtype="float32")
        mp3_data = _mp3_bytes(data, sr)
        return Response(content=mp3_data, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi chuyển đổi MP3: {e}")


# -------------------------------------------------------------
# Model Management API
# -------------------------------------------------------------
def _torch_installed() -> bool:
    try:
        import torch  # noqa: F401
        return True
    except Exception:
        return False


def _mo_ta_model(spec, *, has_torch: bool, has_cuda: bool) -> Dict[str, Any]:
    """Một phần tử trong `/api/models`.

    `available` giữ nguyên nghĩa cũ (= máy chạy được) để frontend cũ không đổi
    hành vi; `compatible` và `downloaded` là hai cờ mới, tách bạch.
    """
    from apps import kokoro_installer

    can_autoinstall = model_catalog.frozen_gpu_autoinstall_possible()
    can_kokoro = kokoro_installer.available()
    ok, ly_do = model_catalog.compatible(
        spec, has_torch=has_torch, has_cuda=has_cuda, can_autoinstall_torch=can_autoinstall,
        has_kokoro_deps=can_kokoro,
    )
    da_tai = model_catalog.is_downloaded(spec)
    return {
        "id": spec.id,
        "name": spec.name,
        "description": spec.description,
        "supports_cloning": spec.supports_cloning,
        "supports_streaming": spec.supports_streaming,
        "precision": spec.precision,
        "device": spec.device,
        "sample_rate": spec.sample_rate,
        "available": ok,
        "compatible": ok,
        "downloaded": da_tai,
        "needs_gpu_setup": "torch" in spec.requires and can_autoinstall and not cuda_is_available(),
        "needs_addon_setup": "kokoro_deps" in spec.requires and can_kokoro and not kokoro_installer.deps_ready(),
        # Gói ngôn ngữ tải thêm (Kokoro: tiếng Nhật, tiếng Trung).
        "packs": [
            {"code": p.code, "name": p.name, "approx_bytes": p.approx_bytes,
             "installed": kokoro_installer.pack_ready(p.code) and model_catalog.kokoro_pack_downloaded(p)}
            for p in model_catalog.KOKORO_PACKS
        ] if model_catalog.is_kokoro(spec.id) else [],
        "approx_bytes": spec.approx_bytes,
        "unavailable_reason": ly_do,
        "note": spec.note,
    }


@app.get("/api/models", include_in_schema=False)
async def list_available_models():
    """Liệt kê mô hình kèm hai cờ tách bạch: máy chạy được, và đã tải về chưa.

    Gộp hai thứ đó làm một là lý do người dùng chọn FP32 rồi ngồi nhìn spinner
    vài phút mà không biết đang tải 453MB. `has_cuda` dùng bản dò "hiệu dụng":
    coi có GPU nếu torch báo có, HOẶC máy có GPU vật lý dù torch chưa cài - để
    nút tải mô hình GPU không bị làm mờ oan trên bản .exe chưa cài torch.
    """
    has_cuda = _effective_has_cuda()
    has_torch = _torch_installed()
    return {
        "current": current_model_info,
        "gpu": {"available": cuda_is_available(), "name": gpu_name()},
        "models": [
            _mo_ta_model(s, has_torch=has_torch, has_cuda=has_cuda)
            for s in model_catalog.MODELS
        ],
    }


class LoadModelReq(BaseModel):
    model_name: str
    device: str = "auto"


# Tải/cài/đổi mô hình: chỉ từ giao diện app trên máy này. CORS đang mở "*", nên nếu
# không kiểm Origin/Host thì trang web lạ đang mở trong trình duyệt cũng gọi được -
# vd. bắt máy tải mô hình vài trăm MB hay cài gói Python từ PyPI cho Kokoro.
_THIS_MACHINE = [Depends(remote_access.require_this_machine)]


@app.post("/api/models/load", include_in_schema=False, dependencies=_THIS_MACHINE)
async def switch_model(req: LoadModelReq):
    """Chuyển đổi sang mô hình được chọn."""
    try:
        load_model_instance(req.model_name, req.device)
        return {"status": "ok", "current": current_model_info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể nạp model: {e}")


class DownloadReq(BaseModel):
    model_id: str
    auto_apply: bool = True
    # Gói ngôn ngữ của Kokoro ("ja"/"zh"): chỉ tải giọng + bộ tách âm của gói.
    pack: Optional[str] = None


def _reload_kokoro_if_current(_model_id: str) -> None:
    """Cài xong gói ngôn ngữ: nạp lại Kokoro nếu đang dùng, để giọng và ngôn ngữ mới
    hiện ra. Đang dùng mô hình khác thì để yên - không tự đổi mô hình của người dùng."""
    if model_catalog.is_kokoro(current_model_info.get("name")):
        load_model_instance(current_model_info["name"])


@app.post("/api/models/download", status_code=202, include_in_schema=False,
          dependencies=_THIS_MACHINE)
async def start_model_download(req: DownloadReq):
    """Nhận việc tải mô hình ở thread nền. Trả về ngay, không đợi tải xong."""
    ok, ly_do = model_downloader.start(
        req.model_id, auto_apply=req.auto_apply,
        apply_fn=_reload_kokoro_if_current if req.pack else load_model_instance,
        pack=req.pack,
    )
    if not ok:
        raise HTTPException(status_code=409, detail=ly_do)
    return {"status": "accepted", "model_id": req.model_id}


@app.get("/api/models/download", include_in_schema=False)
async def model_download_status():
    return model_downloader.get_state()


@app.post("/api/models/download/cancel", status_code=202, include_in_schema=False,
          dependencies=_THIS_MACHINE)
async def cancel_model_download():
    if not model_downloader.cancel():
        raise HTTPException(status_code=409, detail="Không có việc tải nào đang chạy.")
    return {"status": "cancelling"}
def _openapi_with_api_key():
    """Them nut "Authorize" (khoa X-API-Key) vao /docs de thu API tu may khac.
    Moi API cong khai deu ghi "khong khoa HOAC co khoa": cung may thi khong can."""
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi

    schema = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
    schema.setdefault("components", {})["securitySchemes"] = {
        "ApiKey": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "Chỉ cần khi gọi từ máy khác. Lấy khoá trong Cài đặt → Cho máy khác truy cập API.",
        }
    }
    for path, operations in schema.get("paths", {}).items():
        if path in remote_access.PUBLIC_PATHS:
            for operation in operations.values():
                operation["security"] = [{}, {"ApiKey": []}]
    app.openapi_schema = schema
    return schema


app.openapi = _openapi_with_api_key


def main():
    host = remote_access.listen_host()
    remote_access.mark_listening(host)
    uvicorn.run(app, host=host, port=setup_port(), ws="none")  # app không dùng WebSocket


if __name__ == "__main__":
    main()

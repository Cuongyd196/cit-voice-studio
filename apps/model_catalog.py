"""Danh mục mô hình: mô hình nào gồm file nào, cần gì để chạy được.

Nguồn sự thật duy nhất cho cả `fetch_models.py` (tải trước lúc đóng gói) lẫn
`apps/model_downloader.py` (tải lúc chạy). Trước đây danh sách file bị chép ở
nhiều nơi và lệch nhau là chuyện sớm muộn.

KHÔNG import torch / onnxruntime / transformers ở top level: module này bị
`/api/models` gọi ở mọi request, và bản cài mặc định là torch-free.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Optional, Tuple

V3_REPO = "pnnbao-ump/VieNeu-TTS-v3-Turbo"
NANO_REPO = "pnnbao-ump/VieNeu-TTS-v3-Nano"
NANO_FILES: Tuple[str, ...] = (
    "text_encoder.onnx", "duration_predictor.onnx", "vector_estimator.onnx",
    "codec_decoder.onnx", "config.json", "constants.npz",
    "speaker_encoder.onnx", "codec_encoder.onnx", "reference_encoder.onnx", "denoiser.onnx",
)
CODEC_REPO = "OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX"
CODEC_REPO_TORCH = "OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano"
# Supertonic 3 (Supertone, OpenRAIL-M): giọng nước ngoài, apps/supertonic_engine.py. Repo
# đã ngừng phát triển (2026-07), ghim revision để file không đổi dưới chân bộ giải mã.
SUPERTONIC_REPO = "supertone-oss-archive/supertonic-3"
SUPERTONIC_REVISION = "aafc6e32416a594460b32413efc49d7fe4ce6d46"
SUPERTONIC_ID = "Supertonic 3 (31 ngôn ngữ)"
SUPERTONIC_FILES: Tuple[str, ...] = (
    "onnx/duration_predictor.onnx", "onnx/text_encoder.onnx", "onnx/vector_estimator.onnx",
    "onnx/vocoder.onnx", "onnx/tts.json", "onnx/unicode_indexer.json",
    *(f"voice_styles/{v}{i}.json" for v in "FM" for i in range(1, 6)),
    # Giấy phép OpenRAIL-M và model card (ghi giấy phép, tác giả) luôn đi cùng trọng số.
    # Chỉ bỏ audio_samples/ và img/ của repo (~13 MB file demo, app không dùng).
    "LICENSE", "README.md", "config.json",
)

# Kokoro-82M (hexgrad, Apache-2.0) bản ONNX: một mô hình đọc giọng bản xứ 8 ngôn
# ngữ (không có tiếng Việt). Chỉ lấy bản fp32 - bản 8-bit (model_quantized/q8) đo
# trên i7-8650U chậm gấp ~10 lần (RTF 5.7 so với 0.5) vì ONNX Runtime chạy phép nhân
# lượng tử hoá động rất tệ trên CPU. Chữ cái đầu mã giọng là ngôn ngữ (xem
# apps/kokoro_engine.LANGS). Phần tách âm (espeak-ng GPL, misaki + từ điển Nhật/Trung)
# KHÔNG đi kèm bộ cài - xem apps/kokoro_installer.py.
KOKORO_REPO = "onnx-community/Kokoro-82M-v1.0-ONNX"
# Ghim revision: người dùng mới luôn tải đúng bản đã test, repo đổi cũng không ảnh hưởng.
# Lên bản mới = đổi sha ở đây, test lại rồi phát hành.
KOKORO_REVISION = "1939ad2a8e416c0acfeecc08a694d14ef25f2231"
KOKORO_ID = "Kokoro-82M (Multilingual)"
# Bản GPU: trọng số PyTorch gốc của tác giả (hexgrad), chạy apps/_kokoro_torch trên
# CUDA trong venv GPU. Giọng dùng chung file .bin của KOKORO_REPO - trùng từng byte
# với voices/*.pt của hexgrad (đã so) - nên gói ngôn ngữ phục vụ cả hai bản.
KOKORO_TORCH_REPO = "hexgrad/Kokoro-82M"
KOKORO_TORCH_REVISION = "f3ff3571791e39611d31c381e3a41a3af07b4987"
KOKORO_GPU_ID = "Kokoro-82M (Multilingual, GPU)"
KOKORO_IDS = (KOKORO_ID, KOKORO_GPU_ID)
# Gói cơ bản: tiếng Anh + các thứ tiếng espeak đọc được (Tây Ban Nha, Pháp, Hindi,
# Ý, Bồ Đào Nha) - 13 giọng ngoài tiếng Anh chỉ ~7 MB và dùng chung bộ tách âm.
KOKORO_VOICE_PREFIXES = ("af", "am", "bf", "bm", "ef", "em", "ff", "hf", "hm",
                         "if", "im", "pf", "pm")


@dataclass(frozen=True)
class KokoroPack:
    """Gói ngôn ngữ thêm cho Kokoro, chỉ tải khi người dùng bấm: giọng + bộ tách âm
    riêng (từ điển Nhật ~250 MB trên đĩa). Không phải ModelSpec - không nạp riêng
    được, chỉ mở thêm giọng cho mô hình Kokoro đã tải."""
    code: str                        # mã ngôn ngữ, khớp kokoro_engine.LANGS
    name: str
    voice_prefixes: Tuple[str, ...]
    marker: str                      # một file giọng làm dấu "đã tải"
    approx_bytes: int

    @property
    def patterns(self) -> Tuple[str, ...]:
        return tuple(f"voices/{p}_*.bin" for p in self.voice_prefixes)


KOKORO_PACKS: Tuple[KokoroPack, ...] = (
    KokoroPack("ja", "Tiếng Nhật", ("jf", "jm"), "voices/jf_alpha.bin", 52 * 1024 * 1024),
    KokoroPack("zh", "Tiếng Trung", ("zf", "zm"), "voices/zf_xiaoxiao.bin", 25 * 1024 * 1024),
)


def is_kokoro(model_id: Optional[str]) -> bool:
    return model_id in KOKORO_IDS


def kokoro_pack(code: str) -> Optional[KokoroPack]:
    return next((p for p in KOKORO_PACKS if p.code == code), None)

# Phải khớp `_GRAPH_FILES` / `_CODEC_FILES` trong
# src/vieneu/_v3_turbo_engine/onnx_runtime_lite.py (bản chép vendored, không sửa
# được). tests/test_model_catalog.py canh chừng chỗ lệch này.
GRAPH_FILES: Tuple[str, ...] = (
    "vieneu_prefill.onnx", "vieneu_decode_step.onnx",
    "vieneu_acoustic_cached.onnx", "vieneu_backbone_shared.data",
    "vieneu_v3_heads.npz", "config.json", "tokenizer.json",
)
CODEC_FILES: Tuple[str, ...] = (
    "moss_audio_tokenizer_decode_full.onnx", "moss_audio_tokenizer_decode_shared.data",
    "moss_audio_tokenizer_decode_step.onnx", "codec_browser_onnx_meta.json",
    "moss_audio_tokenizer_encode.onnx", "moss_audio_tokenizer_encode.data",
)
# Ở gốc repo, dùng cho Voice Cloning. Tải luôn, nếu không thì nhân bản giọng vẫn
# phải ra mạng ở lần dùng đầu - đúng thứ ta đang muốn tránh.
ROOT_FILES: Tuple[str, ...] = ("config.json", "denoiser.onnx", "speaker_encoder.onnx")


@dataclass(frozen=True)
class RepoFiles:
    """Một nguồn file trên HF: hoặc danh sách file cố định, hoặc mẫu glob.

    ONNX dùng `files` vì danh sách biết chính xác. Đường PyTorch (GPU v3)
    dùng `patterns` vì nạp qua `AutoModel.from_pretrained(trust_remote_code=True)`,
    không có manifest cố định - khi đó `markers` phải nêu vài file chốt để dò
    xem đã tải hay chưa.
    """
    repo: str
    subfolder: Optional[str] = None
    files: Optional[Tuple[str, ...]] = None
    patterns: Optional[Tuple[str, ...]] = None
    markers: Tuple[str, ...] = ()
    # Ghim một revision cố định (sha). None = lấy sha mới nhất lúc tải.
    revision: Optional[str] = None

    def __post_init__(self) -> None:
        if bool(self.files) == bool(self.patterns):
            raise ValueError("RepoFiles cần đúng MỘT trong `files` hoặc `patterns`")
        if self.patterns and not self.markers:
            raise ValueError("Nguồn kiểu `patterns` phải nêu `markers`")

    @property
    def allow_patterns(self) -> Tuple[str, ...]:
        """Chuỗi truyền thẳng cho `snapshot_download(allow_patterns=...)`."""
        if self.patterns:
            return self.patterns
        prefix = f"{self.subfolder}/" if self.subfolder else ""
        return tuple(prefix + f for f in (self.files or ()))

    @property
    def marker_paths(self) -> Tuple[str, ...]:
        """File bắt buộc phải có trong cache thì mới coi là đã tải xong."""
        return self.markers or self.allow_patterns


@dataclass(frozen=True)
class ModelSpec:
    id: str
    name: str
    description: str
    sources: Tuple[RepoFiles, ...]
    requires: Tuple[str, ...] = ()
    approx_bytes: int = 0
    precision: str = "int8"
    device: str = "cpu"
    sample_rate: int = 48_000
    supports_cloning: bool = True
    supports_streaming: bool = True
    note: Optional[str] = None


# Mô hình kèm sẵn trong bản phát hành (copy_release_models.py chép đúng các file
# của nó); các mô hình khác người dùng tải trong Cài đặt.
BUNDLED_MODEL_ID = "VieNeu-TTS-v3-Turbo (int8)"

_ONNX_ROOT = RepoFiles(repo=V3_REPO, files=ROOT_FILES)
_ONNX_CODEC = RepoFiles(repo=CODEC_REPO, files=CODEC_FILES)

MODELS: Tuple[ModelSpec, ...] = (
    ModelSpec(
        id="VieNeu-TTS-v3-Turbo (int8)",
        name="VieNeu-TTS v3 Turbo (INT8 CPU - Khuyến nghị)",
        description="Siêu nhanh, nén int8 tối ưu tuyệt đối cho CPU, chuẩn âm thanh 48kHz.",
        sources=(
            RepoFiles(repo=V3_REPO, subfolder="onnx_int8", files=GRAPH_FILES),
            _ONNX_ROOT,
            _ONNX_CODEC,
        ),
        requires=(),
        approx_bytes=312 * 1024 * 1024,
        precision="int8",
        device="cpu",
    ),
    ModelSpec(
        id="VieNeu-TTS-v3-Turbo (GPU)",
        name="VieNeu-TTS v3 Turbo (GPU NVIDIA - Nhanh nhất)",
        description=(
            "Chạy PyTorch/CUDA, 48kHz. Gộp lô cả kịch bản nên nhanh vượt trội ở "
            "chế độ Hội thoại/Podcast."
        ),
        sources=(
            RepoFiles(
                repo=V3_REPO,
                patterns=("update/*", "*.onnx", "config.json"),
                markers=("update/config.json", "speaker_encoder.onnx"),
            ),
            RepoFiles(
                repo=CODEC_REPO_TORCH,
                patterns=("*.json", "*.py", "*.safetensors"),
                markers=("config.json",),
            ),
        ),
        requires=("torch", "cuda"),
        approx_bytes=1500 * 1024 * 1024,
        precision="fp32",
        device="cuda",
    ),
    ModelSpec(
        id="VieNeu-TTS-v3-Turbo (fp32)",
        name="VieNeu-TTS v3 Turbo (FP32 Studio Quality)",
        description="Chất lượng âm thanh phòng thu 48kHz tối đa, hỗ trợ clone giọng và tag cảm xúc.",
        sources=(
            RepoFiles(repo=V3_REPO, subfolder="onnx_update", files=GRAPH_FILES),
            _ONNX_ROOT,
            _ONNX_CODEC,
        ),
        requires=(),
        approx_bytes=453 * 1024 * 1024,
        precision="fp32",
        device="cpu",
        note="Cần tải thêm ở lần đầu.",
    ),
    ModelSpec(
        id=SUPERTONIC_ID,
        name="Supertonic 3 (31 ngôn ngữ · CPU · 44 kHz)",
        description=(
            "Giọng đọc tiếng Anh, Nhật, Hàn, Pháp, Đức, Tây Ban Nha… (31 ngôn ngữ), 10 giọng "
            "nam nữ. Dùng cho văn bản tiếng nước ngoài."
        ),
        sources=(RepoFiles(repo=SUPERTONIC_REPO, files=SUPERTONIC_FILES, revision=SUPERTONIC_REVISION),),
        approx_bytes=401_301_114,
        precision="fp32",
        device="cpu",
        sample_rate=44_100,
        supports_cloning=False,
        note="Không nhân bản giọng. Tiếng Việt nên dùng VieNeu.",
    ),
    ModelSpec(
        id=KOKORO_ID,
        name="Kokoro (Đa ngôn ngữ · CPU · 24 kHz)",
        description=(
            "Giọng bản xứ: tiếng Anh (Mỹ, Anh), Tây Ban Nha, Pháp, Ý, Bồ Đào Nha, Hindi; "
            "thêm tiếng Nhật, tiếng Trung khi cần. Không đọc tiếng Việt."
        ),
        sources=(
            RepoFiles(
                repo=KOKORO_REPO,
                revision=KOKORO_REVISION,
                patterns=("onnx/model.onnx",
                          *(f"voices/{p}_*.bin" for p in KOKORO_VOICE_PREFIXES)),
                # Một giọng tiếng Pháp làm dấu: cache chỉ có giọng tiếng Anh (bản
                # trước) thì coi như chưa tải, bấm Tải về sẽ lấy bù phần thiếu.
                markers=("onnx/model.onnx", "voices/af_heart.bin", "voices/ff_siwis.bin"),
            ),
        ),
        requires=("kokoro_deps",),
        approx_bytes=350 * 1024 * 1024,
        precision="fp32",
        device="cpu",
        sample_rate=24_000,
        supports_cloning=False,
        note=(
            "Lần đầu tải khoảng 350 MB mô hình và cài thêm bộ tách âm (khoảng 22 MB) "
            "vào máy bạn. Không nhân bản giọng, không hỗ trợ thẻ cảm xúc."
        ),
    ),
    ModelSpec(
        id=KOKORO_GPU_ID,
        name="Kokoro (Đa ngôn ngữ · GPU NVIDIA · 24 kHz)",
        description=(
            "Như Kokoro đa ngôn ngữ nhưng chạy trên GPU NVIDIA, nhanh hơn nhiều khi đọc "
            "văn bản dài. Không đọc tiếng Việt."
        ),
        sources=(
            RepoFiles(repo=KOKORO_TORCH_REPO, files=("config.json", "kokoro-v1_0.pth"),
                      revision=KOKORO_TORCH_REVISION),
            RepoFiles(
                repo=KOKORO_REPO,
                revision=KOKORO_REVISION,
                patterns=tuple(f"voices/{p}_*.bin" for p in KOKORO_VOICE_PREFIXES),
                markers=("voices/af_heart.bin", "voices/ff_siwis.bin"),
            ),
        ),
        requires=("torch", "cuda", "kokoro_deps"),
        approx_bytes=340 * 1024 * 1024,
        precision="fp32",
        device="cuda",
        sample_rate=24_000,
        supports_cloning=False,
        note=(
            "Lần đầu tải khoảng 340 MB mô hình, bộ tách âm (khoảng 22 MB) và bộ hỗ trợ GPU "
            "nếu máy chưa có. Không nhân bản giọng, không hỗ trợ thẻ cảm xúc."
        ),
    ),
    ModelSpec(
        id="VieNeu-TTS-v3-Nano (preview)",
        name="VieNeu-TTS v3 Nano (Thử nghiệm · CPU · 24 kHz)",
        description="Mô hình nhẹ cho CPU, hỗ trợ đọc tiếng Việt và nhân bản giọng, âm thanh 24 kHz.",
        sources=(RepoFiles(repo=NANO_REPO, files=NANO_FILES),),
        approx_bytes=419918885,
        precision="fp32",
        device="cpu",
        sample_rate=24_000,
        supports_cloning=True,
        supports_streaming=False,
        note="Chất lượng và tiếng Anh kém hơn Turbo.",
    ),
)

def check_has_physical_nvidia_gpu() -> bool:
    """Máy có GPU NVIDIA vật lý kèm driver hợp lệ không - không cần torch để biết.

    Dùng để quyết định hiển thị nút tải cho mô hình GPU khi torch chưa cài (bản
    .exe không kèm torch). Trên Windows: thử nạp `nvcuda.dll` (driver NVIDIA cài
    sẵn nó, kể cả khi torch/CUDA toolkit chưa có). Trên Linux: dò file driver.
    """
    if sys.platform != "win32":
        from pathlib import Path
        return Path("/proc/driver/nvidia/version").exists()

    import ctypes
    try:
        return bool(ctypes.windll.kernel32.LoadLibraryW("nvcuda.dll"))
    except Exception:
        return False


def frozen_gpu_autoinstall_possible() -> bool:
    """Có thể cài GPU theo yêu cầu không (giữ tên cũ để tương thích).

    Backend chạy bằng Python riêng cũng hỗ trợ cài từ Settings, không chỉ
    PyInstaller. Chỉ kiểm tra công cụ cài thực tế, không dựa vào sys.frozen.
    """
    from apps.gpu_installer import find_uv
    return find_uv() is not None


def get(model_id: str) -> Optional[ModelSpec]:
    for spec in MODELS:
        if spec.id == model_id:
            return spec
    return None


def compatible(
    spec: ModelSpec, *, has_torch: bool, has_cuda: bool, can_autoinstall_torch: bool = False,
    has_kokoro_deps: bool = False,
) -> tuple[bool, Optional[str]]:
    """Máy này chạy được mô hình đó không, kèm lý do tiếng Việt khi không.

    Nhận cờ từ bên ngoài thay vì tự dò, để test khỏi phải vá torch/hardware và để
    module này giữ được cam kết torch-free. `can_autoinstall_torch=True` (bản .exe
    có `uv`) coi thiếu torch là tạm thời - mô hình vẫn hiện compatible, việc cài
    thật sự diễn ra lúc tải/áp dụng (`apps/model_downloader.py`).
    `has_kokoro_deps` tương tự cho bộ tách âm của Kokoro: đã cài, hoặc cài được.
    """
    co = {"torch": has_torch or can_autoinstall_torch, "cuda": has_cuda,
          "kokoro_deps": has_kokoro_deps}

    reason_torch = (
        "Chưa có bộ hỗ trợ GPU và không tìm thấy công cụ cài tự động. "
        "Hãy cập nhật hoặc cài lại đầy đủ bộ CIT Voice Studio mới nhất."
    )
    _LY_DO = {
        "torch": reason_torch,
        "cuda": "Không thấy GPU NVIDIA dùng được trên máy này.",
        "kokoro_deps": (
            # macOS: kokoro_installer.available() luôn False - chưa hỗ trợ, cập nhật
            # app cũng không giúp gì nên không khuyên thế.
            "Kokoro chưa hỗ trợ macOS. Trên máy Mac hãy dùng VieNeu-TTS cho tiếng Việt "
            "hoặc Supertonic 3 cho tiếng nước ngoài."
            if sys.platform == "darwin" else
            "Không tìm thấy công cụ cài bộ tách âm cho Kokoro. "
            "Hãy cập nhật hoặc cài lại đầy đủ bộ CIT Voice Studio mới nhất."
        ),
    }

    for yeu_cau in spec.requires:
        if not co.get(yeu_cau, False):
            return False, _LY_DO.get(yeu_cau, f"Thiếu {yeu_cau}.")
    return True, None


def kokoro_pack_downloaded(pack: KokoroPack) -> bool:
    """Giọng của gói đã nằm trong cache HF chưa. Không chạm mạng."""
    import huggingface_hub

    try:
        huggingface_hub.hf_hub_download(KOKORO_REPO, pack.marker, repo_type="model",
                                        revision=KOKORO_REVISION, local_files_only=True)
        return True
    except Exception:
        return False


def is_downloaded(spec: ModelSpec) -> bool:
    """File đã nằm đủ trong cache HF cục bộ chưa. Không chạm mạng."""
    import huggingface_hub

    for src in spec.sources:
        for path in src.marker_paths:
            try:
                huggingface_hub.hf_hub_download(
                    src.repo, path, repo_type="model", revision=src.revision,
                    local_files_only=True,
                )
            except Exception:
                return False
    return True

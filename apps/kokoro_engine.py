"""Engine đọc đa ngôn ngữ bằng Kokoro-82M (ONNX, CPU) cho web_stream.

Không kế thừa `BaseVieneuTTS`: lớp đó gắn với codec + định dạng giọng của VieNeu.
Engine này chỉ cung cấp đúng phần `web_stream.py` dùng - `infer`, `infer_stream`,
`list_preset_voices`, `_preset_voices`, `sample_rate` - và cố ý KHÔNG có
`add_voice` / `load_extra_voices`: Kokoro không nhân bản giọng, web_stream dựa vào
việc thiếu thuộc tính đó để từ chối rõ ràng.

Một mô hình, 8 ngôn ngữ (không có tiếng Việt). Với web_stream, Kokoro là một mô
hình nhiều ngôn ngữ như Supertonic: `languages` liệt kê mã đọc được (/health).
Khác Supertonic, mỗi giọng Kokoro được huấn luyện cho MỘT thứ tiếng (chữ cái đầu
của mã giọng, như Kokoro quy ước) và luôn đọc theo tiếng đó - `infer(lang=...)` được
nhận nhưng bỏ qua (xem `_lang_for`).
Tiếng Anh/Tây Ban Nha/Pháp/Ý/Bồ Đào Nha/Hindi tách âm bằng espeak-ng (qua
`kokoro_onnx`); tiếng Nhật và tiếng Trung espeak đọc kém nên dùng `misaki` - đúng
bộ tách âm mà Kokoro được huấn luyện cùng.

`kokoro_onnx` và `misaki` chỉ có sau khi `apps/kokoro_installer.py` cài (không
đóng gói), nên chỉ import bên trong hàm.
"""
from __future__ import annotations

import re
import sys
import threading
import types
from pathlib import Path
from typing import Iterator, NamedTuple, Optional, Union

import numpy as np

from vieneu_utils.subtitles import NON_LATIN_STOP_PATTERN

SAMPLE_RATE = 24_000


class Lang(NamedTuple):
    code: str              # mã gửi cho giao diện ("en", "ja"...)
    espeak: Optional[str]  # None = tách âm bằng misaki
    name: str              # tên tiếng Việt
    region: str            # vùng hiển thị ("" nếu không phân vùng)
    suffix: str            # hậu tố tên giọng, tránh trùng tên giữa các thứ tiếng


# Chữ cái đầu mã giọng -> ngôn ngữ (VOICES.md, hexgrad/Kokoro-82M).
LANGS = {
    "a": Lang("en", "en-us", "Tiếng Anh", "Mỹ", ""),
    "b": Lang("en", "en-gb", "Tiếng Anh", "Anh", ""),
    "e": Lang("es", "es", "Tiếng Tây Ban Nha", "", "ES"),
    "f": Lang("fr", "fr-fr", "Tiếng Pháp", "", "FR"),
    "h": Lang("hi", "hi", "Tiếng Hindi", "", "HI"),
    "i": Lang("it", "it", "Tiếng Ý", "", "IT"),
    "p": Lang("pt", "pt-br", "Tiếng Bồ Đào Nha", "Brazil", "PT"),
    "j": Lang("ja", None, "Tiếng Nhật", "", "JA"),
    "z": Lang("zh", None, "Tiếng Trung", "", "ZH"),
}
_GENDER = {"f": ("female", "Nữ"), "m": ("male", "Nam")}
# Mã ngôn ngữ -> cách tách âm khi văn bản viết bằng chữ của thứ tiếng khác tiếng
# của giọng (`_lang_for`). "en" lấy giọng Mỹ (bản ghi đầu).
_BY_CODE: dict = {}
for _lang in LANGS.values():
    _BY_CODE.setdefault(_lang.code, _lang)
# Thứ tự hiện ở ô "Ngôn ngữ văn bản", kèm tên tiếng Việt.
LANGUAGES = {code: _BY_CODE[code].name for code in ("en", "es", "fr", "it", "pt", "hi", "ja", "zh")}
# Câu nghe thử (nút ▶ ở danh sách giọng): dùng chung câu của Supertonic, thêm tiếng
# Trung (Supertonic không đọc tiếng Trung).
PREVIEW_TEXTS = {
    "en": "Hello, this is a sample voice from CIT Voice Studio. Have a wonderful day.",
    "es": "Hola, esta es una voz de muestra de CIT Voice Studio. Que tengas un día maravilloso.",
    "fr": "Bonjour, ceci est une voix d'exemple de CIT Voice Studio. Passez une excellente journée.",
    "it": "Ciao, questa è una voce di esempio di CIT Voice Studio. Buona giornata.",
    "pt": "Olá, esta é uma voz de exemplo do CIT Voice Studio. Tenha um ótimo dia.",
    "hi": "नमस्ते, यह CIT Voice Studio की एक नमूना आवाज़ है। आपका दिन शुभ हो।",
    "ja": "こんにちは。CIT Voice Studioのサンプル音声です。素敵な一日をお過ごしください。",
    "zh": "你好，这是CIT Voice Studio的示例声音。祝你今天过得愉快。",
}

# Giọng tốt nhất theo bảng chấm điểm của tác giả đứng đầu; còn lại theo thứ tự
# ngôn ngữ trong LANGS rồi theo tên.
_ORDER = (
    "af_heart", "af_bella", "af_nicole", "bf_emma", "af_aoede", "af_kore",
    "af_sarah", "am_fenrir", "am_michael", "am_puck", "bm_george", "bm_fable",
)
_LANG_ORDER = "abefhipjz"

# Thẻ cảm xúc ([cười], [thở dài]... của VieNeu; <laugh> <breath> <sigh> của
# Supertonic, có trong đoạn mẫu tiếng nước ngoài): Kokoro không hiểu, espeak sẽ đọc
# to chữ bên trong. Thẻ nghỉ đã được web_stream cắt ra trước khi tới đây.
_TAG_RE = re.compile(r"\[[^\]\n]*\]|<(?:laugh|breath|sigh)>", re.IGNORECASE)
# Chữ viết riêng của tiếng Nhật/Trung/Hindi (`_lang_for`).
_KANA_RE = re.compile(r"[぀-ヿ]")
_HAN_RE = re.compile(r"[㐀-鿿豈-﫿]")
_DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")
# Tiếng Nhật/Trung không có khoảng trắng sau dấu câu; Hindi kết câu bằng "।". Dấu
# đóng ngoặc sau dấu kết câu (「…。」) đi cùng câu đó - dùng chung mẫu với phụ đề.
_SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+|" + NON_LATIN_STOP_PATTERN)
# espeak chèn cờ đổi ngôn ngữ quanh từ mượn, vd. "(en)vˈɔɪs(fr)"; mô hình sẽ đọc
# chúng thành âm lạ.
_LANG_FLAG_RE = re.compile(r"\([a-z]{2,3}(?:-[a-z]+)?\)")
# Đoạn chữ Latin trong câu Nhật/Trung ("CIT", "AI"): đọc bằng espeak tiếng Anh.
_LATIN_RE = re.compile(r"[A-Za-z][A-Za-z0-9'\-]*(?:\s+[A-Za-z][A-Za-z0-9'\-]*)*")


def _create_session(model_path: Path):
    import onnxruntime as ort

    return ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])


def _torch_kokoro(config_path: Path, weights_path: Path, voices_npz: Path, device: str):
    """`kokoro_onnx.Kokoro` với bước suy luận chạy bằng PyTorch (GPU).

    Onnxruntime đóng gói trong app chỉ có CPU, và bản GPU trùng tên module nên không
    nạp song song được. Thay đúng `_infer` - tách âm, chia lô ≤510 âm, cắt khoảng
    lặng, chèn nghỉ theo dấu câu vẫn là của kokoro_onnx (ghim 0.6.1), nên hai
    đường cho cùng cách đọc. Không gọi `Kokoro.__init__`/`_setup`: chúng cần phiên ONNX.
    """
    import torch
    from kokoro_onnx import Kokoro
    from kokoro_onnx.tokenizer import Tokenizer

    from apps._kokoro_torch.model import KModel

    class _TorchKokoro(Kokoro):
        def __init__(self):
            self.model = KModel(str(config_path), str(weights_path)).to(device).eval()
            self.voices = np.load(voices_npz)
            self.tokenizer = Tokenizer(vocab=self.model.vocab)
            vocab = self.tokenizer.vocab
            self._stops = frozenset(vocab[m] for m in ".!?" if m in vocab)
            self._spaces = frozenset(vocab[m] for m in " " if m in vocab)
            self.has_timings = True

        def _infer(self, tokens, style, speed):
            ids = torch.tensor([[0, *tokens, 0]], dtype=torch.long, device=device)
            ref = torch.from_numpy(np.asarray(style, dtype=np.float32).reshape(1, -1)).to(device)
            audio, dur = self.model.forward_with_tokens(ids, ref, float(speed))
            return audio.float().cpu().numpy().ravel(), dur.cpu().numpy().ravel()

    return _TorchKokoro()


def _is_voice_key(key: str) -> bool:
    return len(key) > 3 and key[0] in LANGS and key[1] in _GENDER and key[2] == "_"


def _display_name(key: str) -> str:
    name = key.split("_", 1)[1].capitalize()
    suffix = LANGS[key[0]].suffix
    return f"{name} ({suffix})" if suffix else name


def _sort_key(key: str):
    if key in _ORDER:
        return (0, _ORDER.index(key), key)
    return (1, _LANG_ORDER.index(key[0]), key)


def _ensure_pyopenjtalk_importable() -> None:
    """`misaki.ja` import `pyopenjtalk` ở đầu file dù nhánh mặc định (cutlet) không
    dùng tới. Bản gốc không có wheel Windows (phải build bằng cmake), nên khi thiếu
    thì đặt một module rỗng - gọi nhầm nhánh pyopenjtalk sẽ báo AttributeError rõ."""
    try:
        import pyopenjtalk  # noqa: F401
    except ImportError:
        sys.modules.setdefault("pyopenjtalk", types.ModuleType("pyopenjtalk"))


def _voices_npz(voices_dir: Path, cache_dir: Path, keys: list) -> Path:
    """File .npz gộp các giọng `keys`, tên theo chính danh sách đó.

    Không dùng một tên cố định: kokoro_onnx giữ file .npz MỞ suốt đời engine, nên
    trên Windows nạp lại Kokoro với bộ giọng mới (vừa cài gói tiếng Nhật) mà ghi
    đè file cũ thì `replace` chết với `[WinError 5] Access is denied`. Tên khác
    nhau thì không đụng file đang mở; file của bộ giọng cũ dọn khi không còn ai giữ.
    """
    import hashlib

    tag = hashlib.sha1(",".join(keys).encode()).hexdigest()[:12]
    npz = cache_dir / f"kokoro-voices-{tag}.npz"
    if not npz.is_file():
        cache_dir.mkdir(parents=True, exist_ok=True)
        arrays = {k: np.fromfile(voices_dir / f"{k}.bin", dtype=np.float32).reshape(-1, 1, 256)
                  for k in keys}
        tmp = npz.with_name(npz.stem + ".tmp.npz")
        np.savez(tmp, **arrays)
        tmp.replace(npz)
    for old in cache_dir.glob("kokoro-voices*.npz"):
        if old != npz:
            try:
                old.unlink()
            except OSError:
                pass  # engine đang chạy còn giữ: lần nạp sau sẽ dọn
    return npz


class KokoroTTS:
    """Kokoro-82M fp32 qua `kokoro_onnx`. `voices_dir` chứa `<mã>.bin` (float32 510x1x256)."""

    sample_rate = SAMPLE_RATE

    def __init__(self, model_path: Union[str, Path], voices_dir: Union[str, Path],
                 cache_dir: Union[str, Path], languages: Optional[set] = None,
                 torch_config: Union[str, Path, None] = None, device: str = "cuda"):
        """`languages`: chỉ hiện giọng của các ngôn ngữ này - những thứ tiếng đã cài
        bộ tách âm (tiếng Nhật/Trung là gói tải thêm). None = mọi giọng có file.

        `torch_config` (config.json của hexgrad/Kokoro-82M): chạy bằng PyTorch trên
        `device`, khi đó `model_path` là `kokoro-v1_0.pth`. Không có: ONNX trên CPU."""
        from kokoro_onnx import Kokoro

        keys = sorted((p.stem for p in Path(voices_dir).glob("*.bin")
                       if _is_voice_key(p.stem)
                       and (languages is None or LANGS[p.stem[0]].code in languages)),
                      key=_sort_key)
        if not keys:
            raise RuntimeError("Không tìm thấy giọng nào của Kokoro. Hãy tải lại mô hình.")
        self._keys = {_display_name(k): k for k in keys}
        self._preset_voices = {}
        for name, key in self._keys.items():
            lang = LANGS[key[0]]
            gioi, gioi_vi = _GENDER[key[1]]
            tieng = f"{lang.name} ({lang.region})" if lang.region else lang.name
            # "Giới · Kokoro · Tiếng": cùng khuôn "Giới · Vùng · Phong cách" mà
            # /voices và giao diện tách theo dấu "·" (phần 3 hiện thành nhãn).
            self._preset_voices[name] = {
                "gender": gioi,
                "language": lang.code,
                "description": f"{gioi_vi} · Kokoro · {tieng}",
            }
        self._default_voice = next(iter(self._keys))
        # Ngôn ngữ đọc được = tiếng của các giọng đang hiện (đã lọc theo bộ tách âm
        # đã cài), theo thứ tự LANGUAGES. web_stream báo danh sách này ở /health.
        have = {LANGS[k[0]].code for k in keys}
        self.languages = {c: n for c, n in LANGUAGES.items() if c in have}
        self._g2p = {}
        self._g2p_lock = threading.Lock()
        # Một khoá cho mỗi bộ tách âm misaki, giữ suốt lần gọi: tagger MeCab của
        # fugashi (và jieba) không an toàn khi hai yêu cầu dùng chung một lúc.
        self._g2p_call_locks = {code: threading.Lock() for code in ("ja", "zh")}

        # kokoro_onnx đọc giọng từ MỘT file .npz; Hugging Face để mỗi giọng một file.
        # Gộp một lần ra thư mục ghi được (cache HF có thể chỉ đọc).
        npz = _voices_npz(Path(voices_dir), Path(cache_dir), keys)
        if torch_config is not None:
            self.backend, self.device = "pytorch", device
            self.kokoro = _torch_kokoro(Path(torch_config), Path(model_path), npz, device)
        else:
            self.backend, self.device = "onnx", "cpu"
            self.kokoro = Kokoro.from_session(_create_session(Path(model_path)), str(npz))

    # -- giọng -----------------------------------------------------------------
    def list_preset_voices(self):
        return [(f"{n} - {v['description']}", n) for n, v in self._preset_voices.items()]

    def resolve_voice_name(self, voice) -> Optional[str]:
        """Tên hiển thị của giọng (nhận cả mã gốc "af_heart"), None nếu không có.
        web_stream dùng để trả 400 cho giọng lạ trước khi đọc."""
        if voice in self._keys:
            return voice
        return next((name for name, key in self._keys.items() if key == voice), None)

    def voice_language(self, voice=None) -> str:
        return LANGS[self._resolve(voice)[0]].code

    def _lang_for(self, key: str, text: str) -> Lang:
        """Cách tách âm cho một lần đọc: LUÔN theo tiếng của giọng.

        `language` của yêu cầu không được dùng: tab Hội thoại/Hàng loạt/SRT gửi một
        mã chung cho mọi lượt, nên giọng Nhật trong hội thoại "tiếng Anh" từng bị
        đọc qua espeak en-us - toàn âm vô nghĩa. Ngoại lệ duy nhất là chữ viết mà
        tiếng của giọng không đọc được: văn bản có kana -> tiếng Nhật, chữ Hán ->
        tiếng Trung, Devanagari -> Hindi (nếu máy đã cài thứ tiếng đó). Giọng Nhật
        đọc chữ Hán như tiếng Nhật (kanji), không chuyển sang tiếng Trung."""
        own = LANGS[key[0]]
        if _KANA_RE.search(text):
            script = "ja"
        elif _HAN_RE.search(text):
            script = "zh"
        elif _DEVANAGARI_RE.search(text):
            script = "hi"
        else:
            return own
        if script == own.code or (own.code == "ja" and script == "zh"):
            return own
        if script not in self.languages:
            return own  # chưa cài gói tiếng đó: đọc theo giọng còn hơn báo lỗi
        return _BY_CODE[script]

    def _resolve(self, voice) -> str:
        if voice is None or voice == "":
            return self._keys[self._default_voice]
        if isinstance(voice, str):
            if voice in self._keys:
                return self._keys[voice]
            if voice in self._keys.values():   # nhận cả mã gốc "af_heart" cho người gọi API
                return voice
        raise ValueError(f"Giọng '{voice}' không có trong mô hình Kokoro. "
                         f"Có: {', '.join(self._keys)}")

    # -- tách âm -----------------------------------------------------------------
    def _misaki(self, code: str):
        """Bộ tách âm misaki cho "ja"/"zh", tạo một lần (nạp từ điển mất ~1 giây)."""
        with self._g2p_lock:
            if code not in self._g2p:
                if code == "ja":
                    _ensure_pyopenjtalk_importable()
                    from misaki import ja

                    self._g2p[code] = ja.JAG2P()
                else:
                    import logging

                    import jieba
                    from misaki import zh

                    jieba.setLogLevel(logging.WARNING)
                    # version=None: cách phiên âm Kokoro v1.0 được huấn luyện
                    # (bản "1.1" dành cho mô hình Kokoro-82M-v1.1-zh).
                    self._g2p[code] = zh.ZHG2P(version=None)
            return self._g2p[code]

    def _espeak(self, text: str, lang: str) -> str:
        return _LANG_FLAG_RE.sub("", self.kokoro.tokenizer.phonemize(text, lang))

    def _phonemes(self, text: str, lang: Lang) -> str:
        if lang.espeak:
            return self._espeak(text, lang.espeak)
        misaki = self._misaki(lang.code)
        call_lock = self._g2p_call_locks[lang.code]

        def g2p(part: str) -> str:
            with call_lock:
                return misaki(part)[0]

        out, pos = [], 0
        for m in _LATIN_RE.finditer(text):
            if m.start() > pos:
                out.append(g2p(text[pos:m.start()]))
            out.append(self._espeak(m.group(), "en-us"))
            pos = m.end()
        if pos < len(text):
            out.append(g2p(text[pos:]))
        return " ".join(p.strip() for p in out if p and p.strip())

    # -- tổng hợp ----------------------------------------------------------------
    def infer(self, text: str, voice=None, lang: Optional[str] = None, speed: float = 1.0,
              **_ignored) -> np.ndarray:
        """Đọc `text` bằng giọng `voice`, theo tiếng của chính giọng đó (`_lang_for`).

        `lang` (web_stream `_language_kwargs` chuyển xuống, cùng kiểu Supertonic) được
        nhận để phần mềm gọi API không lỗi, nhưng bỏ qua: muốn đọc tiếng nào thì chọn
        giọng của tiếng đó. `temperature` và tham số riêng của VieNeu cũng bị bỏ qua."""
        key = self._resolve(voice)
        clean = re.sub(r"\s+", " ", _TAG_RE.sub(" ", text or "")).strip()
        if not clean:
            return np.zeros(0, dtype=np.float32)
        phonemes = self._phonemes(clean, self._lang_for(key, clean))
        if not phonemes.strip():
            return np.zeros(0, dtype=np.float32)
        audio, _sr = self.kokoro.create(phonemes, voice=key, speed=float(speed), is_phonemes=True)
        return np.asarray(audio, dtype=np.float32)

    def infer_stream(self, text: str, voice=None, **kwargs) -> Iterator[np.ndarray]:
        """Kokoro không stream từng khung; trả từng câu một để nghe được sớm."""
        for sentence in _SENTENCE_RE.split(text or ""):
            wav = self.infer(sentence, voice=voice, **kwargs)
            if wav.size:
                yield wav

    def close(self) -> None:
        self.kokoro = None

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self.close()

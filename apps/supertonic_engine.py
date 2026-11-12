"""
Supertonic 3 (Supertone, mô hình OpenRAIL-M): giọng đọc 31 ngôn ngữ, chạy ONNX trên CPU.

Dùng cho giọng nước ngoài; tiếng Việt vẫn nên dùng VieNeu (Supertonic đọc tiếng Việt chậm
và không chuẩn hoá số/viết tắt). Mô hình đọc thẳng từng ký tự Unicode nên không cần bộ
tách âm nào - không espeak, không GPL - và chỉ cần `onnxruntime` + `numpy` app đã có.

Cách chạy (theo code mẫu MIT của Supertone, `py/helper.py`): chuẩn hoá chữ -> mã ký tự
qua `unicode_indexer.json` -> `duration_predictor` đoán độ dài -> `text_encoder` -> khử
nhiễu `vector_estimator` qua `steps` bước từ nhiễu ngẫu nhiên -> `vocoder` ra sóng âm.
Nhiễu lấy từ `np.random`, nên `_tts_infer(seed=...)` của web_stream cố định được kết quả.

Có cùng giao diện engine VieNeu mà web_stream dùng (`infer`, `infer_stream`, danh sách
giọng, `sample_rate`) và cố ý KHÔNG có `add_voice`: Supertonic không nhân bản giọng, nên
`POST /api/voices/custom` tự trả 400.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple
from unicodedata import normalize

import numpy as np

# Ngôn ngữ mô hình hỗ trợ (README của mô hình). Thứ tự = thứ tự hiện trên giao diện.
LANGUAGES: Dict[str, str] = {
    "en": "Tiếng Anh", "vi": "Tiếng Việt", "ja": "Tiếng Nhật", "ko": "Tiếng Hàn",
    "fr": "Tiếng Pháp", "de": "Tiếng Đức", "es": "Tiếng Tây Ban Nha", "pt": "Tiếng Bồ Đào Nha",
    "it": "Tiếng Ý", "ru": "Tiếng Nga", "id": "Tiếng Indonesia", "hi": "Tiếng Hindi",
    "ar": "Tiếng Ả Rập", "tr": "Tiếng Thổ Nhĩ Kỳ", "nl": "Tiếng Hà Lan", "pl": "Tiếng Ba Lan",
    "uk": "Tiếng Ukraina", "sv": "Tiếng Thuỵ Điển", "da": "Tiếng Đan Mạch", "fi": "Tiếng Phần Lan",
    "el": "Tiếng Hy Lạp", "cs": "Tiếng Séc", "sk": "Tiếng Slovakia", "hu": "Tiếng Hungary",
    "ro": "Tiếng Romania", "bg": "Tiếng Bulgaria", "hr": "Tiếng Croatia", "sl": "Tiếng Slovenia",
    "et": "Tiếng Estonia", "lv": "Tiếng Latvia", "lt": "Tiếng Litva",
}
# Câu nghe thử giọng theo từng ngôn ngữ (nút ▶ ở danh sách giọng).
PREVIEW_TEXTS: Dict[str, str] = {
    "en": "Hello, this is a sample voice from CIT Voice Studio. Have a wonderful day.",
    "vi": "Xin chào, đây là giọng đọc mẫu của CIT Voice Studio. Chúc bạn một ngày tốt lành.",
    "ja": "こんにちは。CIT Voice Studioのサンプル音声です。素敵な一日をお過ごしください。",
    "ko": "안녕하세요. CIT Voice Studio의 샘플 음성입니다. 좋은 하루 보내세요.",
    "fr": "Bonjour, ceci est une voix d'exemple de CIT Voice Studio. Passez une excellente journée.",
    "de": "Hallo, dies ist eine Beispielstimme von CIT Voice Studio. Einen schönen Tag noch.",
    "es": "Hola, esta es una voz de muestra de CIT Voice Studio. Que tengas un día maravilloso.",
    "pt": "Olá, esta é uma voz de exemplo do CIT Voice Studio. Tenha um ótimo dia.",
    "it": "Ciao, questa è una voce di esempio di CIT Voice Studio. Buona giornata.",
    "ru": "Здравствуйте, это пример голоса CIT Voice Studio. Хорошего вам дня.",
    "id": "Halo, ini adalah contoh suara dari CIT Voice Studio. Semoga harimu menyenangkan.",
    "hi": "नमस्ते, यह CIT Voice Studio की एक नमूना आवाज़ है। आपका दिन शुभ हो।",
    "ar": "مرحبًا، هذا صوت تجريبي من CIT Voice Studio. أتمنى لك يومًا رائعًا.",
    "tr": "Merhaba, bu CIT Voice Studio'dan örnek bir ses. İyi günler dilerim.",
    "nl": "Hallo, dit is een voorbeeldstem van CIT Voice Studio. Nog een fijne dag.",
    "pl": "Dzień dobry, to jest przykładowy głos z CIT Voice Studio. Miłego dnia.",
    "uk": "Привіт, це зразок голосу CIT Voice Studio. Гарного вам дня.",
    "sv": "Hej, det här är en exempelröst från CIT Voice Studio. Ha en underbar dag.",
    "da": "Hej, dette er en eksempelstemme fra CIT Voice Studio. Hav en dejlig dag.",
    "fi": "Hei, tämä on CIT Voice Studion esimerkkiääni. Mukavaa päivää.",
    "el": "Γεια σας, αυτή είναι μια δοκιμαστική φωνή του CIT Voice Studio. Καλή σας μέρα.",
    "cs": "Dobrý den, toto je ukázkový hlas z CIT Voice Studio. Přeji hezký den.",
    "sk": "Dobrý deň, toto je ukážkový hlas z CIT Voice Studio. Prajem pekný deň.",
    "hu": "Helló, ez a CIT Voice Studio mintahangja. Szép napot kívánok.",
    "ro": "Bună ziua, aceasta este o voce demonstrativă de la CIT Voice Studio. O zi minunată.",
    "bg": "Здравейте, това е примерен глас от CIT Voice Studio. Приятен ден.",
    "hr": "Bok, ovo je ogledni glas iz CIT Voice Studija. Ugodan dan.",
    "sl": "Pozdravljeni, to je vzorčni glas iz CIT Voice Studio. Lep dan želim.",
    "et": "Tere, see on CIT Voice Studio näidishääl. Ilusat päeva.",
    "lv": "Sveiki, šī ir CIT Voice Studio parauga balss. Jauku dienu.",
    "lt": "Sveiki, tai CIT Voice Studio balso pavyzdys. Geros dienos.",
}
VOICES: Tuple[str, ...] =("F1", "F2", "F3", "F4", "F5", "M1", "M2", "M3", "M4", "M5")
DEFAULT_VOICE = "F1"
DEFAULT_STEPS = 8          # số bước khử nhiễu, mặc định của Supertone
DEFAULT_SPEED = 1.05       # tốc độ gốc trong code mẫu của Supertone
CHUNK_SILENCE_S = 0.3      # nghỉ giữa hai đoạn của một văn bản dài
MODEL_FILES: Tuple[str, ...] = (
    "onnx/duration_predictor.onnx", "onnx/text_encoder.onnx", "onnx/vector_estimator.onnx",
    "onnx/vocoder.onnx", "onnx/tts.json", "onnx/unicode_indexer.json",
    *(f"voice_styles/{v}.json" for v in VOICES),
    "LICENSE", "README.md", "config.json",
)

# Thẻ của Supertonic là <laugh>, <breath>, <sigh> (giao diện chèn thẳng, giữ nguyên). Thẻ
# ngoặc vuông cũ của app vẫn nhận: [cười] -> <laugh>, [thở dài] -> <sigh>, [lấy hơi] ->
# <breath>; thẻ khác bị bỏ, vì chuẩn hoá của Supertonic đổi "[" "]" thành dấu cách và đọc
# "[hắng giọng]" thành chữ.
_EMOTION_TAGS = {"cười": "<laugh>", "thở dài": "<sigh>", "lấy hơi": "<breath>"}
_BRACKET_TAG = re.compile(r"\[([^\]]*)\]")
_VI_LETTERS = re.compile(
    r"[ăâđêôơưàảãáạằẳẵắặầẩẫấậèẻẽéẹềểễếệìỉĩíịòỏõóọồổỗốộờởỡớợùủũúụừửữứựỳỷỹýỵ]", re.IGNORECASE)
_KANA = re.compile(r"[぀-ヿ]")
_HANGUL = re.compile(r"[가-힯ᄀ-ᇿ]")

_EMOJI = re.compile(
    "[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f680-\U0001f6ff\U0001f700-\U0001f77f"
    "\U0001f780-\U0001f7ff\U0001f800-\U0001f8ff\U0001f900-\U0001f9ff\U0001fa00-\U0001fa6f"
    "\U0001fa70-\U0001faff☀-⛿✀-➿\U0001f1e6-\U0001f1ff]+")
_REPLACE = {
    "–": "-", "‑": "-", "—": "-", "_": " ", "“": '"', "”": '"', "‘": "'",
    "’": "'", "´": "'", "`": "'", "[": " ", "]": " ", "|": " ", "/": " ", "#": " ",
    "→": " ", "←": " ",
}
_SENTENCE_END = re.compile(r"[.!?;:,'\"')\]}…。」』】〉》›»]$")
_PARAGRAPHS = re.compile(r"\n\s*\n+")
_SENTENCES = re.compile(
    r"(?<!Mr\.)(?<!Mrs\.)(?<!Ms\.)(?<!Dr\.)(?<!Prof\.)(?<!Sr\.)(?<!Jr\.)(?<!etc\.)(?<!e\.g\.)"
    r"(?<!i\.e\.)(?<!vs\.)(?<!Inc\.)(?<!Ltd\.)(?<!Co\.)(?<!St\.)(?<!\b[A-Z]\.)(?<=[.!?])\s+"
    r"|(?<=[。！？])")  # dấu câu CJK không có dấu cách theo sau


def detect_language(text: str) -> str:
    """Đoán ngôn ngữ khi người gọi không nêu: đủ cho trường hợp hay gặp của app."""
    if _VI_LETTERS.search(text):
        return "vi"
    if _KANA.search(text):
        return "ja"
    if _HANGUL.search(text):
        return "ko"
    return "en"


def convert_tags(text: str) -> str:
    """Đổi thẻ cảm xúc của app sang thẻ Supertonic; bỏ các thẻ ngoặc vuông khác."""
    def repl(m: re.Match) -> str:
        tag = _EMOTION_TAGS.get(m.group(1).strip().lower())
        return f" {tag} " if tag else " "
    return _BRACKET_TAG.sub(repl, text)


def preprocess(text: str, lang: str) -> str:
    """Chuẩn hoá chữ như code mẫu của Supertone, rồi bọc thẻ ngôn ngữ ``<lang>…</lang>``."""
    text = _EMOJI.sub("", normalize("NFKD", text))
    for k, v in _REPLACE.items():
        text = text.replace(k, v)
    text = re.sub(r"[♥☆♡©\\]", "", text)
    for k, v in {"@": " at ", "e.g.,": "for example, ", "i.e.,": "that is, "}.items():
        text = text.replace(k, v)
    text = re.sub(r" ([,.!?;:'])", r"\1", text)
    for q in ('"', "'"):
        while q * 2 in text:
            text = text.replace(q * 2, q)
    text = re.sub(r"\s+", " ", text).strip()
    if not _SENTENCE_END.search(text):
        text += "."
    return f"<{lang}>{text}</{lang}>"


def chunk_text(text: str, max_len: int = 300) -> List[str]:
    """Chia theo đoạn văn rồi theo câu, mỗi đoạn ≤ ``max_len`` ký tự khi có thể."""
    chunks: List[str] = []
    for para in (p.strip() for p in _PARAGRAPHS.split(text.strip())):
        if not para:
            continue
        cur = ""
        for sent in (s for s in _SENTENCES.split(para) if s.strip()):
            if cur and len(cur) + len(sent) + 1 > max_len:
                chunks.append(cur.strip())
                cur = sent
            else:
                cur = f"{cur} {sent}" if cur else sent
        if cur.strip():
            chunks.append(cur.strip())
    return chunks


def _mask(lengths: np.ndarray, max_len: Optional[int] = None) -> np.ndarray:
    max_len = int(max_len or lengths.max())
    ids = np.arange(max_len)
    return (ids < lengths[:, None]).astype(np.float32).reshape(-1, 1, max_len)


class SupertonicTTS:
    """Supertonic 3 qua onnxruntime. ``model_dir`` là thư mục snapshot của repo HF."""

    def __init__(self, model_dir, steps: int = DEFAULT_STEPS, sessions=None):
        model_dir = Path(model_dir)
        cfg = json.loads((model_dir / "onnx" / "tts.json").read_text(encoding="utf-8"))
        self.sample_rate = int(cfg["ae"]["sample_rate"])
        self._base_chunk = int(cfg["ae"]["base_chunk_size"])
        self._compress = int(cfg["ttl"]["chunk_compress_factor"])
        self._latent_dim = int(cfg["ttl"]["latent_dim"])
        self.steps = int(steps)
        self._indexer = np.asarray(
            json.loads((model_dir / "onnx" / "unicode_indexer.json").read_text(encoding="utf-8")),
            dtype=np.int64)
        self._styles = {v: self._load_style(model_dir / "voice_styles" / f"{v}.json") for v in VOICES}
        self._dp, self._enc, self._est, self._voc = sessions or self._load_sessions(model_dir / "onnx")
        self._default_voice = DEFAULT_VOICE
        self._preset_voices = {
            v: {"gender": "female" if v[0] == "F" else "male",
                "description": f"{'Nữ' if v[0] == 'F' else 'Nam'} · Đa ngôn ngữ · Supertonic 3"}
            for v in VOICES
        }

    @staticmethod
    def _load_sessions(onnx_dir: Path):
        import onnxruntime as ort

        opts = ort.SessionOptions()
        return tuple(
            ort.InferenceSession(str(onnx_dir / f"{name}.onnx"), sess_options=opts,
                                 providers=["CPUExecutionProvider"])
            for name in ("duration_predictor", "text_encoder", "vector_estimator", "vocoder"))

    @staticmethod
    def _load_style(path: Path) -> Tuple[np.ndarray, np.ndarray]:
        data = json.loads(path.read_text(encoding="utf-8"))
        def arr(key):
            dims = data[key]["dims"]
            return np.asarray(data[key]["data"], dtype=np.float32).reshape(1, dims[1], dims[2])
        return arr("style_ttl"), arr("style_dp")

    # --- danh sách giọng (cùng kiểu engine VieNeu) ---------------------------------
    def list_preset_voices(self) -> List[tuple]:
        return [(f"{'Nữ' if v[0] == 'F' else 'Nam'} {v[1]} ({v})", v) for v in VOICES]

    def resolve_voice_name(self, name: Optional[str]) -> Optional[str]:
        if name is None:
            return None
        key = str(name).strip().upper()
        return key if key in self._styles else None

    # --- đọc --------------------------------------------------------------------
    def _encode(self, text: str, lang: str) -> np.ndarray:
        codes = np.fromiter((ord(c) for c in preprocess(text, lang)), dtype=np.int64)
        codes = codes[codes < len(self._indexer)]
        ids = self._indexer[codes]
        return ids[ids >= 0]  # ký tự mô hình không biết: bỏ, không làm hỏng cả câu

    def _infer_chunk(self, text: str, lang: str, style, speed: float) -> np.ndarray:
        ids = self._encode(text, lang)
        if len(ids) == 0:
            return np.zeros(0, dtype=np.float32)
        text_ids = ids.reshape(1, -1)
        text_mask = _mask(np.array([len(ids)]))
        ttl, dp = style
        dur, *_ = self._dp.run(None, {"text_ids": text_ids, "style_dp": dp, "text_mask": text_mask})
        dur = np.asarray(dur, dtype=np.float32).reshape(-1) / speed
        emb, *_ = self._enc.run(None, {"text_ids": text_ids, "style_ttl": ttl, "text_mask": text_mask})

        wav_len = (dur * self.sample_rate).astype(np.int64)
        chunk = self._base_chunk * self._compress
        latent_len = (wav_len + chunk - 1) // chunk
        latent_mask = _mask(latent_len)
        xt = np.random.randn(1, self._latent_dim * self._compress, int(latent_len.max())).astype(np.float32)
        xt *= latent_mask
        total = np.array([self.steps], dtype=np.float32)
        for step in range(self.steps):
            xt, *_ = self._est.run(None, {
                "noisy_latent": xt, "text_emb": emb, "style_ttl": ttl, "text_mask": text_mask,
                "latent_mask": latent_mask, "current_step": np.array([step], dtype=np.float32),
                "total_step": total,
            })
        wav, *_ = self._voc.run(None, {"latent": xt})
        return np.asarray(wav, dtype=np.float32).reshape(-1)[: int(wav_len[0])]

    def _chunks(self, text: str, voice: Optional[str], lang: Optional[str], speed: float) -> Iterator[np.ndarray]:
        name = self.resolve_voice_name(voice or self._default_voice)
        if name is None:
            raise ValueError(f"Voice '{voice}' not found")
        text = convert_tags(text)
        lang = lang if lang in LANGUAGES else detect_language(text)
        max_len = 120 if lang in ("ja", "ko") else 300
        for part in chunk_text(text, max_len=max_len):
            wav = self._infer_chunk(part, lang, self._styles[name], speed)
            if len(wav):
                yield wav

    def infer_stream(self, text: str, voice: Optional[str] = None, lang: Optional[str] = None,
                     speed: float = DEFAULT_SPEED, **_) -> Iterator[np.ndarray]:
        """Đọc từng đoạn và trả ngay (không có streaming từng khung như VieNeu Turbo)."""
        silence = np.zeros(int(self.sample_rate * CHUNK_SILENCE_S), dtype=np.float32)
        for i, wav in enumerate(self._chunks(text, voice, lang, speed)):
            yield np.concatenate([silence, wav]) if i else wav

    def infer(self, text: str, voice: Optional[str] = None, lang: Optional[str] = None,
              speed: float = DEFAULT_SPEED, **_) -> np.ndarray:
        """Đọc cả văn bản. ``temperature`` và tham số riêng của VieNeu bị bỏ qua."""
        parts = list(self.infer_stream(text, voice=voice, lang=lang, speed=speed))
        return np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)

    def close(self) -> None:
        self._dp = self._enc = self._est = self._voc = None

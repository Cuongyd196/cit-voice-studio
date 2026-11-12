"""
Torch-FREE reference denoiser (resemble-enhance denoise core, ONNX).
=====================================================================
Enrollment-time preprocessing: clean a (possibly noisy) reference clip so its
x-vector lands in the training distribution (train data is denoised + LUFS-20).
Noisy refs otherwise push the speaker embedding out-of-distribution and cause
EOS run-away at inference.

Runtime deps: numpy + onnxruntime (+ resampy only when the ref sr != 44100).
No torch. STFT/iSTFT are numpy; the learned UNet + mask/phase math is `denoiser_core.onnx`.

The ONNX graph boundary is (mag, cos, sin) -> (sep_mag, sep_cos, sep_sin); it is
byte-equivalent to the torch resemble-enhance DENOISE path (verified: waveform
corr=1.0, x-vector cos=1.0). Handles a single chunk (<=~30s), which is enough for
enrollment clips. Denoise runs ONCE per voice, not in the per-utterance loop.

Usage:
    from vieneu_v3.onnx_denoiser import OnnxDenoiser
    den = OnnxDenoiser("denoiser_core.onnx")
    clean = den.denoise(wav, sr)      # -> float32 mono @ 44100 Hz
"""
from __future__ import annotations

import numpy as np
import onnxruntime as ort

# STFT config — must match resemble-enhance Denoiser (hop_size=420, n_fft=hop*4).
N_FFT = 1680
HOP = 420
WAV_RATE = 44100
# Hann window, PERIODIC (torch default: 0.5 - 0.5*cos(2*pi*n/N)).
_WIN = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(N_FFT) / N_FFT)


def _stft(x: np.ndarray) -> np.ndarray:
    """torch.stft(center=True, reflect pad, hann-periodic), last frame dropped -> (f, t)."""
    pad = N_FFT // 2
    xp = np.pad(x, (pad, pad), mode="reflect")
    n = 1 + (len(xp) - N_FFT) // HOP
    idx = np.arange(N_FFT)[None, :] + HOP * np.arange(n)[:, None]
    frames = xp[idx] * _WIN[None, :]                     # (n, N_FFT)
    spec = np.fft.rfft(frames, n=N_FFT, axis=1).T        # (f, n)
    return spec[:, :-1]                                   # drop last frame (matches source)


def _istft(spec: np.ndarray, out_len: int) -> np.ndarray:
    """Inverse of _stft: replicate-pad last frame, WOLA with window^2 normalization."""
    spec = np.concatenate([spec, spec[:, -1:]], axis=1)  # replicate-pad last frame
    frames = np.fft.irfft(spec, n=N_FFT, axis=0) * _WIN[:, None]  # (N_FFT, T)
    T = spec.shape[1]
    siglen = N_FFT + HOP * (T - 1)
    out = np.zeros(siglen)
    wsum = np.zeros(siglen)
    w2 = _WIN ** 2
    for i in range(T):
        s = i * HOP
        out[s:s + N_FFT] += frames[:, i]
        wsum[s:s + N_FFT] += w2
    out = out / np.maximum(wsum, 1e-11)
    pad = N_FFT // 2
    out = out[pad:siglen - pad]                           # remove center padding
    if len(out) < out_len:
        out = np.pad(out, (0, out_len - len(out)))
    return out[:out_len]


def _normalize(x: np.ndarray) -> np.ndarray:
    return x / (np.abs(x).max() + 1e-7)


def _resample(wav: np.ndarray, sr: int, target: int = WAV_RATE) -> np.ndarray:
    """Resample to `target` Hz. Prefers `soxr` (a base dependency); falls back to
    torchaudio when present so no single package is strictly required."""
    if sr == target:
        return wav.astype(np.float32)
    try:
        import soxr
        return soxr.resample(wav, sr, target).astype(np.float32)
    except Exception:
        pass
    try:
        import torch
        import torchaudio
        out = torchaudio.functional.resample(torch.as_tensor(wav, dtype=torch.float32), sr, target)
        return out.numpy().astype(np.float32)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            f"Cần `soxr` (hoặc torchaudio) để resample audio {sr}→{target} Hz."
        ) from e


class OnnxDenoiser:
    """Torch-free resemble-enhance denoiser (denoise-only) via ONNX + numpy."""

    def __init__(self, onnx_path: str, providers=None, sess_options=None):
        # sess_options: share the engine's tuned options (thread count, no
        # spinning). The ORT default is a pool of ALL cores that busy-waits.
        self.sess = ort.InferenceSession(
            onnx_path, sess_options, providers=providers or ["CPUExecutionProvider"]
        )

    def _core(self, mag, cos, sin):
        o = self.sess.run(
            None,
            {
                "mag": mag[None].astype(np.float32),
                "cos": cos[None].astype(np.float32),
                "sin": sin[None].astype(np.float32),
            },
        )
        return o[0][0], o[1][0], o[2][0]                  # sep_mag, sep_cos, sep_sin

    def _forward(self, x: np.ndarray) -> np.ndarray:
        x = _normalize(x)
        s = _stft(x)
        mag = np.abs(s)
        phi = np.angle(s)
        cos = np.cos(phi)
        sin = np.sin(phi)
        sep_mag, sep_cos, sep_sin = self._core(mag, cos, sin)
        spec = sep_mag * (sep_cos + 1j * sep_sin)
        return _istft(spec, out_len=len(x))

    def denoise(self, wav, sr: int) -> np.ndarray:
        """wav: 1D float array (any sr) -> denoised float32 mono @ 44100 Hz.

        Single-chunk (<= ~30s); for enrollment clips.
        """
        wav = np.asarray(wav, dtype=np.float32).reshape(-1)
        wav = _resample(wav, sr, WAV_RATE)
        length = len(wav)
        abs_max = max(float(np.abs(wav).max()), 1e-7)
        w = wav / abs_max
        w = np.pad(w, (0, 441))                           # npad=441 (resemble inference_chunk)
        o = self._forward(w)
        return (o[:length] * abs_max).astype(np.float32)

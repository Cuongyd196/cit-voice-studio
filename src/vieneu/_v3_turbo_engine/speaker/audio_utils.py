"""Audio helpers for the speaker encoder (fbank front-end).

Torch-free: resampling runs on soxr and the 80-dim Kaldi fbank on
kaldi-native-fbank (same Kaldi algorithm as torchaudio.compliance.kaldi.fbank;
verified x-vector cosine = 1.0 on identical input). torchaudio is only a
fallback for environments installed before kaldi-native-fbank became a core
dependency.
"""
from __future__ import annotations

import numpy as np

_FBANK_FRAME_SHIFT_MS = 10.0
_FBANK_FRAME_LENGTH_MS = 25.0


def _to_numpy(x) -> np.ndarray:
    """np.ndarray | torch.Tensor -> float32 numpy (no torch import needed)."""
    if hasattr(x, "detach"):
        x = x.detach().cpu().numpy()
    return np.asarray(x, dtype=np.float32)


def high_quality_resample(x, orig_sr: int, target_sr: int) -> np.ndarray:
    """Resample along the last axis (1D ``(T,)`` or 2D ``(ch, T)``) via soxr."""
    import soxr

    wav = _to_numpy(x)
    if wav.ndim == 1:
        return soxr.resample(wav, orig_sr, target_sr).astype(np.float32)
    if wav.ndim == 2:
        out = soxr.resample(wav.T, orig_sr, target_sr)          # soxr wants (T, ch)
        return np.ascontiguousarray(out.T, dtype=np.float32)
    raise ValueError(f"Expected 1D or 2D waveform, got shape {tuple(wav.shape)}")


def _kaldi_fbank(wav: np.ndarray, sample_rate: int, n_mels: int, dither: float) -> np.ndarray:
    """1D float wav -> (T, n_mels) Kaldi log-mel fbank (povey window, snip_edges)."""
    try:
        import kaldi_native_fbank as knf
    except ImportError:
        # Old env without kaldi-native-fbank: keep working through torchaudio.
        import torch
        import torchaudio.compliance.kaldi as Kaldi
        feats = Kaldi.fbank(
            torch.from_numpy(wav).unsqueeze(0),
            num_mel_bins=n_mels,
            sample_frequency=sample_rate,
            dither=dither,
        )
        return feats.numpy().astype(np.float32)

    opts = knf.FbankOptions()
    opts.frame_opts.samp_freq = sample_rate
    opts.frame_opts.frame_shift_ms = _FBANK_FRAME_SHIFT_MS
    opts.frame_opts.frame_length_ms = _FBANK_FRAME_LENGTH_MS
    opts.frame_opts.dither = dither
    opts.frame_opts.snip_edges = True
    opts.frame_opts.window_type = "povey"
    opts.frame_opts.remove_dc_offset = True
    opts.frame_opts.preemph_coeff = 0.97
    opts.mel_opts.num_bins = n_mels
    fb = knf.OnlineFbank(opts)
    fb.accept_waveform(sample_rate, wav)
    fb.input_finished()
    n = fb.num_frames_ready
    if n == 0:
        raise ValueError(
            f"Audio too short for fbank ({len(wav)} samples @ {sample_rate} Hz "
            f"< one {_FBANK_FRAME_LENGTH_MS:.0f} ms frame)."
        )
    return np.stack([fb.get_frame(i) for i in range(n)]).astype(np.float32)


def extract_fbank(
    waveform,
    *,
    sample_rate: int,
    n_mels: int,
    dither: float = 0.0,
    mean_norm: bool = False,
) -> np.ndarray:
    wav = _to_numpy(waveform)
    if wav.ndim == 2:
        wav = wav[0]                                            # first channel
    elif wav.ndim != 1:
        raise ValueError(
            f"FBank expects a 1D or 2D waveform, got shape {tuple(wav.shape)}."
        )
    features = _kaldi_fbank(wav, sample_rate, n_mels, dither)
    if mean_norm:
        features = features - features.mean(axis=0, keepdims=True)
    return features

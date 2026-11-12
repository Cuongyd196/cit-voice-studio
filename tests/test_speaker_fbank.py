"""Speaker-encoder fbank front-end: torch-free (kaldi-native-fbank + soxr).

Regression for the cloning crash on the minimal install: `pip install vieneu`
ships no torch/torchaudio, so the front-end must never import them.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

SRC = str(Path(__file__).resolve().parents[1] / "src")


def _sine(sr: int, seconds: float = 1.0, freq: float = 220.0) -> np.ndarray:
    t = np.arange(int(sr * seconds), dtype=np.float32) / sr
    return (0.3 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


class TestSpeakerFbank:
    def test_fbank_shape_and_mean_norm(self):
        from vieneu._v3_turbo_engine.speaker import extract_speaker_fbank

        feats = extract_speaker_fbank(_sine(24000), sample_rate=24000)
        # 1s @ 16 kHz, 25ms/10ms snip_edges → (16000-400)//160 + 1 = 98 frames
        assert feats.shape == (98, 80)
        assert feats.dtype == np.float32
        # mean-normalized over time
        assert np.abs(feats.mean(axis=0)).max() < 1e-4

    def test_fbank_accepts_2d_and_16k_passthrough(self):
        from vieneu._v3_turbo_engine.speaker import extract_speaker_fbank

        wav = _sine(16000)
        f1 = extract_speaker_fbank(wav, sample_rate=16000)
        f2 = extract_speaker_fbank(wav[None, :], sample_rate=16000)  # (1, T)
        np.testing.assert_allclose(f1, f2)

    def test_cloning_front_end_is_torch_free(self):
        """Import + fbank must succeed in a process where torch cannot be imported."""
        code = """
import json, sys
import numpy as np

class _Block:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in ("torch", "torchaudio"):
            raise ModuleNotFoundError(f"No module named '{name}'")
        return None

sys.meta_path.insert(0, _Block())
sys.path.insert(0, sys.argv[1])

from vieneu._v3_turbo_engine.speaker import OnnxSpeakerEncoder, extract_speaker_fbank  # noqa: F401

sr = 24000
t = np.arange(sr, dtype=np.float32) / sr
feats = extract_speaker_fbank(0.3 * np.sin(2 * np.pi * 220.0 * t), sample_rate=sr)
print(json.dumps({"shape": list(feats.shape), "torch_loaded": "torch" in sys.modules}))
"""
        proc = subprocess.run(
            [sys.executable, "-c", code, SRC], capture_output=True, text=True, timeout=120
        )
        assert proc.returncode == 0, proc.stderr
        out = json.loads(proc.stdout.strip().splitlines()[-1])
        assert out["shape"] == [98, 80]
        assert out["torch_loaded"] is False

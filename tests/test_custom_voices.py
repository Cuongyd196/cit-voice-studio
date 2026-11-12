"""Saved cloned voices must resolve immediately and after reloading the model.

Use real API, voice registry and persistence with only neural inference mocked.
Run with: python -m unittest discover -s tests -p test_custom_voices.py
"""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from apps import web_stream as ws
from apps import terms
from vieneu.v3turbo import V3TurboVieNeuTTS


def make_tts():
    tts = V3TurboVieNeuTTS.__new__(V3TurboVieNeuTTS)
    tts.default_style = "tu_nhien"
    tts._preset_voices = {}
    tts._default_voice = None
    tts._voice_aliases = {}
    from collections import OrderedDict
    tts._ref_cache = OrderedDict()
    tts._load_v3_voices()
    tts.sample_rate = 48000
    tts.max_batch_size = 1
    tts.watermarker = None
    tts.engine = Mock()
    tts.engine.prepare_reference.return_value = (
        np.linspace(-1, 1, 192, dtype=np.float32),
        np.arange(32, dtype=np.int64).reshape(2, 16),
    )
    tts._preclean_reference_audio = lambda path: path
    tts._infer_chunks = Mock(return_value=[np.zeros(4800, dtype=np.float32)])
    return tts


class CustomVoiceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "voices.json"
        self.tts = make_tts()
        for patcher in (
            patch.object(ws, "vieneu", self.tts),
            patch.object(ws, "current_model_info", {"sample_rate": 48000}),
            patch.object(ws, "_custom_voices_path", return_value=self.path),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = TestClient(ws.app)
        self.addCleanup(self.client.close)
        audio = io.BytesIO()
        sf.write(audio, np.zeros(16000 * 6, dtype=np.float32), 16000, format="WAV")
        self.audio = audio.getvalue()

    def save_voice(self, name="Giọng của tôi", source="recording"):
        return self.client.post(
            "/api/voices/custom",
            data={"name": name, "denoise": "false", "input_source": source,
                  "rights_confirmed": "true", "rights_version": terms.TERMS_VERSION},
            files={"ref_audio": ("reference.wav", self.audio, "audio/wav")},
        )

    def assert_can_generate(self, tts, voice_id):
        response = self.client.post("/api/tts/generate", json={
            "text": "Xin chào.", "voice_id": voice_id,
        })
        self.assertEqual(response.status_code, 200, response.text[:200])
        self.assertTrue(response.content.startswith(b"RIFF"))
        args = tts._infer_chunks.call_args.args
        embedding, codes = self.tts.engine.prepare_reference.return_value
        np.testing.assert_allclose(args[1], embedding, atol=1e-6)
        np.testing.assert_array_equal(args[2], codes)

    def test_save_list_generate_and_reload_fp32(self):
        response = self.save_voice("  Giọng của tôi  ")
        self.assertEqual(response.status_code, 200, response.text)
        voice_id = response.json()["voice_id"]
        self.assertEqual(voice_id, "Giọng của tôi")
        voices = self.client.get("/voices").json()
        self.assertTrue(next(v for v in voices if v["id"] == voice_id)["isCloned"])
        saved = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(list(saved["presets"]), [voice_id])
        self.assert_can_generate(self.tts, voice_id)
        self.assertFalse(self.tts.engine.prepare_reference.call_args.kwargs["denoise"])
        temporary_audio = self.tts.engine.prepare_reference.call_args.args[0]
        self.assertFalse(Path(temporary_audio).exists())

        reloaded = make_tts()
        original_default = reloaded._default_voice
        with patch.object(ws, "Vieneu", return_value=reloaded):
            ws.load_model_instance("VieNeu-TTS-v3-Turbo (fp32)")
        self.assertEqual(reloaded._default_voice, original_default)
        self.assert_can_generate(reloaded, voice_id)
        reloaded.engine.prepare_reference.assert_not_called()

    def test_multiple_saved_voices_survive_reload_and_delete(self):
        for name in ("Giọng A", "Giọng B"):
            self.assertEqual(self.save_voice(name).status_code, 200)
        self.assertEqual(self.client.delete("/api/voices/custom/Giọng A").status_code, 200)
        restored = make_tts()
        self.assertEqual(restored.load_extra_voices(self.path), 1)
        self.assertNotIn("Giọng A", restored._preset_voices)
        self.assertIn("Giọng B", restored._preset_voices)

    def test_duplicate_names_do_not_overwrite_voices(self):
        self.assertEqual(self.save_voice(self.tts._default_voice).status_code, 409)
        self.assertEqual(self.save_voice().status_code, 200)
        previous = self.path.read_bytes()
        self.assertEqual(self.save_voice().status_code, 409)
        self.assertEqual(self.path.read_bytes(), previous)

    def test_deleted_voice_leaves_voice_list_and_unknown_is_404(self):
        # Giao diện nạp lại /voices ngay sau khi xoá: giọng phải biến mất khỏi đó
        # (không cần khởi động lại), và xoá lần hai phải báo 404 chứ không 500.
        self.assertEqual(self.save_voice().status_code, 200)
        listed = [v["id"] for v in self.client.get("/voices").json()]
        self.assertIn("Giọng của tôi", listed)
        self.assertEqual(self.client.delete("/api/voices/custom/Giọng của tôi").status_code, 200)
        listed = [v["id"] for v in self.client.get("/voices").json()]
        self.assertNotIn("Giọng của tôi", listed)
        self.assertEqual(self.client.delete("/api/voices/custom/Giọng của tôi").status_code, 404)

    def test_cannot_delete_built_in_voice(self):
        name = self.tts._default_voice
        self.assertEqual(self.client.delete(f"/api/voices/custom/{name}").status_code, 400)
        self.assertIn(name, self.tts._preset_voices)

    def test_failed_write_preserves_previous_file_and_registry(self):
        self.assertEqual(self.save_voice("Giọng A").status_code, 200)
        previous = self.path.read_bytes()
        with patch("os.replace", side_effect=OSError("disk full")):
            self.assertEqual(self.save_voice("Giọng B").status_code, 500)
        self.assertNotIn("Giọng B", self.tts._preset_voices)
        self.assertEqual(self.path.read_bytes(), previous)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_failed_delete_keeps_saved_voice(self):
        self.assertEqual(self.save_voice("Giọng A").status_code, 200)
        previous = self.path.read_bytes()
        with patch("os.replace", side_effect=OSError("disk full")):
            self.assertEqual(self.client.delete("/api/voices/custom/Giọng A").status_code, 500)
        self.assertIn("Giọng A", self.tts._preset_voices)
        self.assertEqual(self.path.read_bytes(), previous)

    def test_empty_name_or_audio_is_rejected(self):
        self.assertEqual(self.save_voice("   ").status_code, 400)
        self.audio = b""
        self.assertEqual(self.save_voice().status_code, 400)
        self.tts.engine.prepare_reference.assert_not_called()

    def test_old_full_voice_file_does_not_override_built_ins(self):
        self.assertEqual(self.save_voice().status_code, 200)
        self.tts.save_voices(self.path)
        restored = make_tts()
        default = restored.get_preset_voice()
        self.assertEqual(restored.load_extra_voices(self.path), 1)
        self.assertIs(restored.get_preset_voice(), default)
        self.assertFalse(default["is_custom"])

    def test_cam_ket_luu_cung_giong_reload_va_xoa_cung_giong(self):
        response = self.save_voice("Giọng MP3", source="file")
        self.assertEqual(response.status_code, 200, response.text)
        saved = json.loads(self.path.read_text(encoding="utf-8"))
        record = saved["presets"]["Giọng MP3"]["authorization"]
        self.assertEqual(record["terms_version"], terms.TERMS_VERSION)
        self.assertEqual(record["input_source"], "file")
        restored = make_tts()
        restored.load_extra_voices(self.path)
        self.assertEqual(restored._preset_voices["Giọng MP3"]["authorization"], record)
        # Lưu thêm giọng không làm mất cam kết của giọng đã nạp lại.
        restored.save_voices(self.path, custom_only=True)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["presets"]["Giọng MP3"]["authorization"], record)
        self.assertEqual(self.client.delete("/api/voices/custom/Giọng MP3").status_code, 200)
        self.assertNotIn("Giọng MP3", json.loads(self.path.read_text(encoding="utf-8"))["presets"])


if __name__ == "__main__":
    unittest.main()

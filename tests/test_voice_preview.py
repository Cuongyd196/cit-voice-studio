"""Nghe thử giọng: đọc câu mẫu một lần, các lần sau phát lại từ cache trên đĩa."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from apps import web_stream as ws


class VoicePreviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        self.tts = Mock()
        self.tts._preset_voices = {"Minh Đức": {}, "Giọng riêng": {"is_custom": True}}
        self.tts.infer.return_value = np.full(4800, 0.1, dtype=np.float32)
        self.info = {"name": "VieNeu-TTS-v3-Turbo (int8)", "sample_rate": 48000}
        for patcher in (
            patch.object(ws, "vieneu", self.tts),
            patch.object(ws, "current_model_info", self.info),
            patch.object(ws, "voice_preview_dir", return_value=self.dir),
            patch.object(ws, "_custom_voices_path", return_value=self.dir / "voices.json"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = TestClient(ws.app)
        self.addCleanup(self.client.close)

    def preview(self, voice_id):
        return self.client.get("/api/voices/preview", params={"voice_id": voice_id})

    def test_doc_mau_bang_dung_giong_va_tra_wav(self):
        res = self.preview("Minh Đức")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["content-type"], "audio/wav")
        audio, sr = sf.read(io.BytesIO(res.content))
        self.assertEqual(sr, 48000)
        self.assertGreater(len(audio), 0)
        self.assertEqual(self.tts.infer.call_args.kwargs["voice"], "Minh Đức")

    def test_lan_sau_phat_tu_cache_khong_tong_hop_lai(self):
        first = self.preview("Minh Đức").content
        second = self.preview("Minh Đức").content
        self.assertEqual(first, second)
        self.assertEqual(self.tts.infer.call_count, 1)

    def test_doi_mo_hinh_thi_doc_lai(self):
        self.preview("Minh Đức")
        self.info["name"] = "VieNeu-TTS-v3-Nano (preview)"
        self.info["sample_rate"] = 24000
        self.preview("Minh Đức")
        self.assertEqual(self.tts.infer.call_count, 2)

    def test_doi_du_lieu_giong_cung_ten_thi_doc_lai(self):
        # 3.8.3 giữ tên "Trúc Ly" nhưng đổi vector giọng: không được phát bản mẫu cũ.
        self.tts._preset_voices["Minh Đức"] = {"speaker_emb": np.zeros(4, dtype=np.float32)}
        self.preview("Minh Đức")
        self.preview("Minh Đức")
        self.assertEqual(self.tts.infer.call_count, 1)
        self.tts._preset_voices["Minh Đức"] = {"speaker_emb": np.ones(4, dtype=np.float32)}
        self.preview("Minh Đức")
        self.assertEqual(self.tts.infer.call_count, 2)

    def test_khong_ap_tu_dien_phat_am(self):
        with patch.object(ws.pronunciation_settings, "apply", side_effect=AssertionError):
            self.assertEqual(self.preview("Minh Đức").status_code, 200)

    def test_giong_khong_ton_tai_bao_404(self):
        self.assertEqual(self.preview("Không có").status_code, 404)
        self.tts.infer.assert_not_called()

    def test_xoa_giong_rieng_thi_xoa_luon_ban_mau(self):
        self.preview("Giọng riêng")
        self.assertEqual(len(list(self.dir.glob("*.wav"))), 1)
        res = self.client.delete("/api/voices/custom/Giọng riêng")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(list(self.dir.glob("*.wav")), [])

    def test_endpoint_khong_nam_trong_tai_lieu_cong_khai(self):
        self.assertNotIn("/api/voices/preview", ws.app.openapi()["paths"])


if __name__ == "__main__":
    unittest.main()

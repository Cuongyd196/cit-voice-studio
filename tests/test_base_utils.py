import unittest
import numpy as np
import sys
from unittest.mock import MagicMock, patch

from vieneu.utils import normalize_device
from vieneu.base import BaseVieneuTTS

class DummyTTS(BaseVieneuTTS):
    def infer(self, text, **kwargs):
        return np.zeros(100)
    def infer_batch(self, texts, **kwargs):
        return [np.zeros(100) for _ in texts]

class TestBaseUtils(unittest.TestCase):
    def test_normalize_device(self):
        self.assertEqual(normalize_device("cuda:0"), "cuda")
        self.assertEqual(normalize_device("GPU"), "cuda")
        self.assertEqual(normalize_device("cpu"), "cpu")
        self.assertEqual(normalize_device("xpu"), "xpu")

        # torch giả, chỉ trong phạm vi test này (core không cần torch).
        fake_torch = MagicMock()
        with patch.dict(sys.modules, {"torch": fake_torch}):
            fake_torch.backends.mps.is_available.return_value = True
            self.assertEqual(normalize_device("mps"), "mps")
            fake_torch.backends.mps.is_available.return_value = False
            self.assertEqual(normalize_device("mps"), "cpu")

    def test_to_list(self):
        tts = DummyTTS()
        # Test list
        self.assertEqual(tts.to_list([1, 2, 3]), [1, 2, 3])
        # Test numpy
        self.assertEqual(tts.to_list(np.array([4, 5])), [4, 5])
        # Test multi-dim numpy
        self.assertEqual(tts.to_list(np.array([[6], [7]])), [6, 7])

        # Đối tượng kiểu mảng (có flatten().tolist()), với một torch giả không nhận ra nó.
        fake_torch = MagicMock()
        fake_torch.Tensor = type("Tensor", (), {})
        with patch.dict(sys.modules, {"torch": fake_torch}):
            mock_obj = MagicMock()
            mock_obj.flatten.return_value.tolist.return_value = [10, 11]
            self.assertEqual(tts.to_list(mock_obj), [10, 11])

    def test_base_streaming_config(self):
        tts = DummyTTS()
        self.assertTrue(hasattr(tts, "streaming_overlap_frames"))
        self.assertEqual(tts.streaming_lookforward, 5)

if __name__ == "__main__":
    unittest.main()

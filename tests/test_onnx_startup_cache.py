"""Warm launches must use local model files without online metadata requests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

from huggingface_hub.errors import LocalEntryNotFoundError
from vieneu._v3_turbo_engine.onnx_runtime_lite import (
    OnnxV3LiteEngine, _GRAPH_FILES, _CODEC_FILES,
)


class StartupCacheTests(unittest.TestCase):
    def test_cached_graphs_and_codec_never_need_network(self):
        def cached(repo, filename, **kwargs):
            self.assertTrue(kwargs.get("local_files_only"))
            return str(Path("cache") / repo / (kwargs.get("subfolder") or "") / filename)

        with patch("huggingface_hub.hf_hub_download", side_effect=cached) as download:
            graphs = OnnxV3LiteEngine._fetch("tts", _GRAPH_FILES, "onnx_int8")
            codec = OnnxV3LiteEngine._fetch("codec", _CODEC_FILES, None)
        self.assertEqual(graphs, Path("cache/tts/onnx_int8"))
        self.assertEqual(codec, Path("cache/codec"))
        self.assertEqual(download.call_count, len(_GRAPH_FILES) + len(_CODEC_FILES))

    def test_missing_file_is_downloaded_after_local_lookup(self):
        with patch("huggingface_hub.hf_hub_download", side_effect=[
            LocalEntryNotFoundError("not downloaded"), "cache/model.onnx",
        ]) as download:
            result = OnnxV3LiteEngine._cached_download("tts", "model.onnx", subfolder="onnx_int8")
        self.assertEqual(result, "cache/model.onnx")
        self.assertEqual(download.call_args_list, [
            call("tts", "model.onnx", local_files_only=True, subfolder="onnx_int8"),
            call("tts", "model.onnx", subfolder="onnx_int8"),
        ])

    def test_partial_cache_downloads_only_missing_file(self):
        online = []

        def fetch(repo, filename, **kwargs):
            if kwargs.get("local_files_only"):
                if filename == "missing.onnx":
                    raise LocalEntryNotFoundError("not downloaded")
            else:
                online.append(filename)
            return str(Path("cache") / filename)

        with patch("huggingface_hub.hf_hub_download", side_effect=fetch):
            OnnxV3LiteEngine._fetch("tts", ["existing.onnx", "missing.onnx"], None)
        self.assertEqual(online, ["missing.onnx"])

    def test_root_denoiser_reuses_cache(self):
        engine = OnnxV3LiteEngine.__new__(OnnxV3LiteEngine)
        engine.checkpoint_path = "test-repo/tts"
        with patch("huggingface_hub.hf_hub_download", return_value="cache/denoiser.onnx") as download:
            self.assertEqual(engine._resolve_root_file("denoiser.onnx"), "cache/denoiser.onnx")
        download.assert_called_once_with("test-repo/tts", "denoiser.onnx", local_files_only=True)

    def test_local_root_file_does_not_access_hub(self):
        engine = OnnxV3LiteEngine.__new__(OnnxV3LiteEngine)
        with tempfile.TemporaryDirectory() as directory:
            engine.checkpoint_path = directory
            source = Path(directory) / "denoiser.onnx"
            source.write_bytes(b"test")
            with patch("huggingface_hub.hf_hub_download") as download:
                self.assertEqual(engine._resolve_root_file("denoiser.onnx"), str(source))
            download.assert_not_called()

    def test_other_cache_errors_do_not_trigger_redownload(self):
        with patch("huggingface_hub.hf_hub_download", side_effect=PermissionError("read denied")) as download:
            with self.assertRaises(PermissionError):
                OnnxV3LiteEngine._cached_download("tts", "model.onnx")
        self.assertEqual(download.call_count, 1)


if __name__ == "__main__":
    unittest.main()

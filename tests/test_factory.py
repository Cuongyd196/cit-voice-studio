from unittest.mock import patch

import pytest

from vieneu.factory import Vieneu


@patch("vieneu.v3turbo.V3TurboVieNeuTTS")
def test_factory_mac_dinh_la_v3turbo(mock_turbo):
    Vieneu(backend="onnx")
    mock_turbo.assert_called_once_with(backend="onnx")


@patch("vieneu.v3nano.V3NanoVieNeuTTS")
def test_factory_v3nano(mock_nano):
    Vieneu(mode="v3nano")
    mock_nano.assert_called_once_with()


@pytest.mark.parametrize("mode", ["standard", "fast", "turbo", "remote", "xpu", "unknown"])
def test_factory_che_do_cu_bao_loi(mode):
    with pytest.raises(ValueError, match="Chế độ không hỗ trợ"):
        Vieneu(mode=mode)

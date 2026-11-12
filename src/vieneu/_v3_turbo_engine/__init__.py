"""Vendored VieNeu-TTS v3 Turbo engine.

Exports are LAZY: importing this package (e.g. to reach the torch-free
``OnnxV3LiteEngine``) does NOT pull torch/transformers. The PyTorch engine
modules load only when their symbols are actually requested (GPU path).
"""

__all__ = [
    "VieNeuV3TurboConfig",
    "VieNeuV3TurboForTTS",
    "VieNeuTTSv3Turbo",
    "OnnxV3LiteEngine",
]


def __getattr__(name):  # PEP 562 lazy attribute import
    if name == "VieNeuV3TurboConfig":
        from .configuration_v3_turbo import VieNeuV3TurboConfig
        return VieNeuV3TurboConfig
    if name == "VieNeuV3TurboForTTS":
        from .modeling_v3_turbo import VieNeuV3TurboForTTS
        return VieNeuV3TurboForTTS
    if name == "VieNeuTTSv3Turbo":
        from .inference_v3_turbo import VieNeuTTSv3Turbo
        return VieNeuTTSv3Turbo
    if name == "OnnxV3LiteEngine":
        from .onnx_runtime_lite import OnnxV3LiteEngine
        return OnnxV3LiteEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

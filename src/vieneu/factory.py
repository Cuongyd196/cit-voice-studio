

def Vieneu(mode="v3turbo", **kwargs):
    """
    Factory function for VieNeu-TTS.

    Args:
        mode: 'v3turbo' (DEFAULT) — VieNeu-TTS v3 Turbo, 48 kHz. CPU runs torch-free
              via ONNX Runtime; GPU uses PyTorch. Works with the minimal install.
              'v3nano' — VieNeu-TTS v3 Nano, 24 kHz. Also torch-free ONNX on CPU;
              a smaller flow-matching model for machines where Turbo is too slow.
              Các chế độ v1/v2 cũ (standard, fast, turbo, remote, xpu) đã bỏ khỏi
              bản desktop; dùng gói ``vieneu`` gốc trên PyPI nếu cần.
        **kwargs: Arguments for chosen class

    Returns:
        BaseVieneuTTS: An instance of a VieNeu-TTS implementation.
    """
    match mode:
        case "v3nano":
            from .v3nano import V3NanoVieNeuTTS
            return V3NanoVieNeuTTS(**kwargs)
        case "v3turbo":
            from .v3turbo import V3TurboVieNeuTTS
            return V3TurboVieNeuTTS(**kwargs)

        case _:
            raise ValueError(f"Chế độ không hỗ trợ: {mode!r}. Dùng 'v3turbo' hoặc 'v3nano'.")

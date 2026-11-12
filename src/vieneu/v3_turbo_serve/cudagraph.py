"""
CUDA-graph capture for the per-frame acoustic step (no C compiler required).

The acoustic frame generation runs the SAME sequence of ops every frame (prefill
2 tokens, then 15 single-token steps at fixed cache lengths) — only the data
changes. That makes it capturable as a single ``torch.cuda.CUDAGraph``: replaying
it advances B sequences by one frame with ONE kernel launch instead of ~16×17
tiny launches, killing the dispatch overhead that dominates this AR loop.

Unlike ``torch.compile``, ``torch.cuda.CUDAGraph`` needs no compiler toolchain,
so it works on Windows + CUDA.
"""
from __future__ import annotations

import torch

from .batched_acoustic import generate_frame_batched


class CudaGraphedFrame:
    """Captures ``generate_frame_batched`` (+ EOS check) for a fixed batch B."""

    def __init__(self, model, batch_size: int, *, temperature: float, top_k: int,
                 top_p: float, warmup: int = 3):
        self.model = model
        self.eos_id = int(model.config.speech_generation_end_token_id)
        dev = next(model.parameters()).device
        H = model.config.hidden_size
        dt = next(model.acoustic_decoder.parameters()).dtype
        self._sampling = dict(temperature=temperature, top_k=top_k, top_p=top_p)

        # Static input buffer (copy each frame's backbone hidden into this).
        self.static_hidden = torch.zeros(batch_size, H, device=dev, dtype=dt)

        # Warm up on a side stream before capture (required by CUDA graphs).
        s = torch.cuda.Stream()
        s.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(s), torch.no_grad():
            for _ in range(warmup):
                self._run_once()
        torch.cuda.current_stream().wait_stream(s)

        # Capture.
        self.graph = torch.cuda.CUDAGraph()
        with torch.cuda.graph(self.graph), torch.no_grad():
            codes, is_eos = self._run_once()
            self.static_codes = codes
            self.static_eos = is_eos

    def _run_once(self):
        codes, prefill_out = generate_frame_batched(self.model, self.static_hidden, **self._sampling)
        is_eos = self.model.text_lm_head(prefill_out[:, 0]).float().argmax(-1) == self.eos_id
        return codes, is_eos

    @torch.no_grad()
    def run(self, backbone_hidden: torch.Tensor):
        """Advance one frame. Returns ``(codes (B,n_vq), is_eos (B,))`` (clones)."""
        self.static_hidden.copy_(backbone_hidden)
        self.graph.replay()
        return self.static_codes.clone(), self.static_eos.clone()

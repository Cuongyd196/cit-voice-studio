"""
Batched Qwen3 backbone steps for v3 Turbo serving.

Wraps the model's ``semantic_backbone`` (HF Qwen3) and runs PREFILL / DECODE for
a whole batch of B sequences at once, sharing one forward per step. Sequences may
have different prompt lengths: prompts are LEFT-padded so every sequence's last
token is right-aligned, and an ``attention_mask`` + explicit ``position_ids``
keep the padded positions inert (and RoPE correct).

Uses HF's native attention + DynamicCache (dense, not paged) — simple and exact.
Paged KV would only matter at very high concurrency / very long sequences.
"""
from __future__ import annotations

from typing import List, Tuple

import torch


class BatchedBackbone:
    def __init__(self, model):
        # model: VieNeuV3TurboForTTS
        self.backbone = model.semantic_backbone
        self.hidden_size = model.config.hidden_size

    @torch.no_grad()
    def prefill(self, embeds_list: List[torch.Tensor]):
        """Prefill a batch of prompts (each ``(Ti, H)``).

        Returns ``(last_hidden (B,H), cache, attn_mask (B,T), cur_pos (B,))``.
        """
        B = len(embeds_list)
        dev = embeds_list[0].device
        dt = embeds_list[0].dtype
        lens = torch.tensor([e.shape[0] for e in embeds_list], device=dev)
        T = int(lens.max())
        x = torch.zeros(B, T, self.hidden_size, device=dev, dtype=dt)
        mask = torch.zeros(B, T, device=dev, dtype=torch.long)
        for i, e in enumerate(embeds_list):
            x[i, T - e.shape[0]:] = e          # left-pad: real tokens right-aligned
            mask[i, T - e.shape[0]:] = 1
        # position_ids: 0..len-1 over the real (right-aligned) tokens.
        pos = (mask.cumsum(-1) - 1).clamp(min=0)
        out = self.backbone(
            inputs_embeds=x, attention_mask=mask, position_ids=pos,
            use_cache=True, return_dict=True,
        )
        last_hidden = out.last_hidden_state[:, -1]   # (B, H) — last real token (right-aligned)
        return last_hidden, out.past_key_values, mask, pos[:, -1]

    @torch.no_grad()
    def decode_step(self, embeds: torch.Tensor, cache, attn_mask: torch.Tensor, cur_pos: torch.Tensor):
        """One decode step for the batch. ``embeds`` is ``(B, 1, H)``.

        Returns ``(hidden (B,H), cache, attn_mask, cur_pos)`` updated.
        """
        new_mask = torch.cat([attn_mask, torch.ones_like(attn_mask[:, :1])], dim=-1)
        new_pos = cur_pos + 1
        out = self.backbone(
            inputs_embeds=embeds, attention_mask=new_mask,
            position_ids=new_pos.unsqueeze(1), past_key_values=cache,
            use_cache=True, return_dict=True,
        )
        return out.last_hidden_state[:, 0], out.past_key_values, new_mask, new_pos

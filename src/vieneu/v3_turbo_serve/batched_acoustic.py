"""
Batched acoustic-frame generation for v3 Turbo serving.

``generate_frame_batched`` runs the acoustic decoder's 16-codebook autoregression
for a WHOLE BATCH of B sequences at once (one audio frame each), reusing the
model's ``AcousticDecoder.cached_step``. This is the per-step kernel of the
batched serving runtime: B requests are advanced together instead of one at a
time, which is where the throughput win comes from.

Equivalent (per row) to ``VieNeuV3TurboForTTS.decode_one_frame`` but vectorised
over the batch dimension.
"""
from __future__ import annotations

import math
from typing import List

import torch
import torch.nn.functional as F


@torch.no_grad()
def _sample_batched(
    logits: torch.Tensor, temperature: float, top_k: int, top_p: float,
    repetition_penalty: float = 1.0, prev=None,
) -> torch.Tensor:
    """Top-k + top-p sampling over a batch. logits: (B, V) -> codes: (B,).

    ``prev`` (optional) is a length-B list of per-row seen-token iterables for this
    codebook; when ``repetition_penalty != 1.0`` those codes are down-weighted on
    each row's logits BEFORE temperature — same CTRL/MOSS rule as the single-path
    ``_sample_token`` (logit<0 → *penalty, else /penalty).
    """
    if not math.isclose(repetition_penalty, 1.0) and prev is not None:
        for b, seen in enumerate(prev):
            if seen:
                idx = torch.as_tensor(sorted(seen), device=logits.device, dtype=torch.long)
                sel = logits[b, idx]
                logits[b, idx] = torch.where(sel < 0, sel * repetition_penalty, sel / repetition_penalty)
    if temperature <= 0:
        return logits.argmax(dim=-1)
    logits = logits / max(temperature, 1e-6)
    if top_k and 0 < top_k < logits.shape[-1]:
        kth = torch.topk(logits, top_k, dim=-1).values[..., -1:]
        logits = torch.where(logits < kth, torch.full_like(logits, float("-inf")), logits)
    if 0.0 < top_p < 1.0:
        s_logits, s_idx = torch.sort(logits, descending=True, dim=-1)
        probs = F.softmax(s_logits, dim=-1)
        drop = probs.cumsum(dim=-1) > top_p
        drop[..., 1:] = drop[..., :-1].clone()
        drop[..., 0] = False
        s_logits = s_logits.masked_fill(drop, float("-inf"))
        logits = torch.full_like(logits, float("-inf")).scatter_(-1, s_idx, s_logits)
    probs = F.softmax(logits, dim=-1)
    return torch.multinomial(probs, num_samples=1).squeeze(-1)


@torch.no_grad()
def generate_frame_batched(
    model,
    backbone_hidden: torch.Tensor,            # (B, H) — backbone hidden for each sequence
    *,
    temperature=0.8,
    top_k: int = 25,
    top_p: float = 0.95,
    repetition_penalty: float = 1.0,
    history=None,   # optional list (len B) of per-row RepetitionHistory (indexable by codebook), updated in place
):
    """Sample one audio frame for each of B sequences.

    ``temperature`` is a scalar applied to every codebook. When
    ``repetition_penalty != 1.0`` and ``history`` is supplied, each row's codes are
    penalised against that row's per-codebook history (then the new codes are added
    to it) — matching the single-path ``decode_one_frame`` behaviour.

    Returns ``(codes, prefill_out)`` where ``codes`` is ``(B, n_vq)`` Long and
    ``prefill_out`` is ``(B, 2, H)`` (slot-0 column feeds the EOS / text head).
    """
    cfg = model.config
    n_vq, H = cfg.n_vq, cfg.hidden_size
    temps = [temperature] * n_vq
    dec = model.acoustic_decoder
    L = len(dec.layers)
    dt = next(dec.parameters()).dtype
    dev = backbone_hidden.device
    B = backbone_hidden.shape[0]
    sgs = cfg.speech_generation_start_token_id
    use_rep = not math.isclose(repetition_penalty, 1.0) and history is not None

    def _sample_ch(ch: int, vec: torch.Tensor) -> torch.Tensor:
        logits = model.audio_lm_heads[ch](vec).float()                            # (B, V)
        prev = [history[b][ch] for b in range(B)] if use_rep else None
        code = _sample_batched(logits, temps[ch], top_k, top_p, repetition_penalty, prev)
        if use_rep:
            for b in range(B):
                history[b][ch].add(int(code[b].item()))
        return code

    cond = backbone_hidden.to(dt)                                                  # (B, H)
    sgs_ids = torch.full((B,), sgs, device=dev, dtype=torch.long)
    txt = model.text_embeddings(sgs_ids).to(dt)                                    # (B, H)
    tok = torch.stack([cond, txt], dim=1)                                          # (B, 2, H)
    # Use arange (a GPU kernel) for positions so this stays CUDA-graph capturable
    # (``torch.tensor([...])`` would do a host->device copy, which capture forbids).
    pos = torch.arange(2, device=dev, dtype=torch.long)
    hidden, pk, pv = dec.cached_step(tok, pos, [None] * L, [None] * L)
    prefill_out = hidden                                                           # (B, 2, H)

    codes: List[torch.Tensor] = [_sample_ch(0, hidden[:, 1])]
    for ch in range(1, n_vq):
        emb = model.audio_embeddings[ch - 1](codes[-1]).to(dt)                     # (B, H)
        pos = torch.arange(ch + 1, ch + 2, device=dev, dtype=torch.long)
        hidden, pk, pv = dec.cached_step(emb.view(B, 1, H), pos, pk, pv)
        codes.append(_sample_ch(ch, hidden[:, 0]))
    return torch.stack(codes, dim=1), prefill_out                                  # (B, n_vq), (B, 2, H)

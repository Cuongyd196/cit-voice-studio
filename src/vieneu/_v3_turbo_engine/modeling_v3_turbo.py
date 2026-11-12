"""
VieNeu-TTS v3 Turbo — model definition (inference).
===================================================
Defines the network that turns text + a reference voice into audio tokens:
a Qwen3 semantic backbone followed by a small acoustic decoder that emits the
16 residual-VQ codes per frame. For synthesis you do not call this module
directly — use ``VieNeuTTSv3Turbo`` in ``inference_v3_turbo`` (or the
``Vieneu(mode="v3turbo")`` wrapper), which drives the backbone's KV cache and
``decode_one_frame`` for you.

This distribution ships the model for inference only. The training objective,
target/label construction, and data pipeline are not part of this package.

Credits
-------
- Architecture: VieNeu-TTS v3 Turbo is designed and trained from scratch on
  ~10,000 hours of English–Vietnamese speech by Phạm Nguyễn Ngọc Bảo
  — https://github.com/pnnbao97
- Phonemizer: sea-g2p — https://github.com/pnnbao97/sea-g2p
- Audio codec: MOSS-Audio-Tokenizer-Nano (OpenMOSS-Team).
"""
from __future__ import annotations
import math
from typing import Optional
import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import PreTrainedModel
from .configuration_v3_turbo import VieNeuV3TurboConfig

class AcousticAttention(nn.Module):

    def __init__(self, hidden_size: int, num_heads: int, rms_eps: float=1e-06):
        super().__init__()
        assert hidden_size % num_heads == 0
        self.num_heads = num_heads
        self.head_dim = hidden_size // num_heads
        self.qkv = nn.Linear(hidden_size, 3 * hidden_size, bias=False)
        self.o_proj = nn.Linear(hidden_size, hidden_size, bias=False)
        self.q_norm = nn.RMSNorm(self.head_dim, eps=rms_eps)
        self.k_norm = nn.RMSNorm(self.head_dim, eps=rms_eps)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, S, H = x.shape
        qkv = self.qkv(x).reshape(B, S, 3, self.num_heads, self.head_dim)
        q, k, v = qkv.unbind(dim=2)
        q, k, v = [t.transpose(1, 2) for t in (q, k, v)]
        q = self.q_norm(q)
        k = self.k_norm(k)
        attn = torch.nn.functional.scaled_dot_product_attention(q, k, v, is_causal=True)
        attn = attn.transpose(1, 2).reshape(B, S, H)
        return self.o_proj(attn)

class AcousticDecoderLayer(nn.Module):

    def __init__(self, hidden_size: int, num_heads: int, intermediate_size: int, rms_eps: float=1e-06):
        super().__init__()
        self.norm1 = nn.RMSNorm(hidden_size, eps=rms_eps)
        self.attn = AcousticAttention(hidden_size, num_heads, rms_eps=rms_eps)
        self.norm2 = nn.RMSNorm(hidden_size, eps=rms_eps)
        self.ff_up = nn.Linear(hidden_size, intermediate_size, bias=False)
        self.ff_gate = nn.Linear(hidden_size, intermediate_size, bias=False)
        self.ff_down = nn.Linear(intermediate_size, hidden_size, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.attn(self.norm1(x))
        residual = x
        normed = self.norm2(x)
        h = F.silu(self.ff_gate(normed)) * self.ff_up(normed)
        return residual + self.ff_down(h)

class AcousticDecoder(nn.Module):

    def __init__(self, config: VieNeuV3TurboConfig):
        super().__init__()
        hs = config.hidden_size
        max_seq_len = config.n_vq + 1
        self.layers = nn.ModuleList([AcousticDecoderLayer(hs, config.local_num_attention_heads, config.local_intermediate_size, config.rms_norm_eps) for _ in range(config.local_num_hidden_layers)])
        self.slot_pos_emb = nn.Embedding(max_seq_len, hs)
        self.norm = nn.RMSNorm(hs, eps=config.rms_norm_eps)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        S = x.shape[1]
        positions = torch.arange(S, device=x.device)
        x = x + self.slot_pos_emb(positions).to(dtype=x.dtype)
        for layer in self.layers:
            x = layer(x)
        return self.norm(x)

    def cached_step(self, x, position_ids, past_k, past_v):
        """One incremental step with a KV cache (lossless vs ``forward``).

        ``x`` is ``(1, Snew, H)`` and ``position_ids`` are the absolute slot
        indices of those tokens. New tokens sit at the END of the sequence, so an
        explicit additive mask is used (they attend to all cached keys and are
        causal among themselves) — ``is_causal=True`` would be wrong here because
        SDPA aligns it to the upper-left when q_len < kv_len.
        """
        B, S, H = x.shape
        x = x + self.slot_pos_emb(position_ids).to(dtype=x.dtype).unsqueeze(0)
        P = past_k[0].shape[2] if past_k[0] is not None else 0
        P1 = P + S
        idx_k = torch.arange(P1, device=x.device)
        idx_q = torch.arange(S, device=x.device) + P
        attend = idx_k.unsqueeze(0) <= idx_q.unsqueeze(1)
        bias = torch.zeros(S, P1, dtype=x.dtype, device=x.device).masked_fill(~attend, torch.finfo(x.dtype).min)
        new_k, new_v = [], []
        for i, layer in enumerate(self.layers):
            a = layer.attn
            h = layer.norm1(x)
            qkv = a.qkv(h).reshape(B, S, 3, a.num_heads, a.head_dim)
            q, k, v = qkv.unbind(dim=2)
            q = q.transpose(1, 2); k = k.transpose(1, 2); v = v.transpose(1, 2)
            q = a.q_norm(q); k = a.k_norm(k)
            if past_k[i] is not None:
                k = torch.cat([past_k[i], k], dim=2)
                v = torch.cat([past_v[i], v], dim=2)
            new_k.append(k); new_v.append(v)
            attn = F.scaled_dot_product_attention(q, k, v, attn_mask=bias)
            attn = attn.transpose(1, 2).reshape(B, S, H)
            x = x + a.o_proj(attn)
            n2 = layer.norm2(x)
            x = x + layer.ff_down(F.silu(layer.ff_gate(n2)) * layer.ff_up(n2))
        return self.norm(x), new_k, new_v

class VieNeuV3TurboForTTS(PreTrainedModel):
    """VieNeu-TTS v3 Turbo network (Qwen3 backbone + acoustic decoder).

    At synthesis time the inference engine runs the backbone step by step with a
    KV cache and calls :meth:`decode_one_frame` to sample the 16 RVQ codes of
    each audio frame. Load it with the checkpoint helpers in
    ``hub_load_v3_turbo`` and prefer the high-level ``VieNeuTTSv3Turbo`` API.
    """

    config_class = VieNeuV3TurboConfig
    _no_split_modules = ['Qwen3DecoderLayer', 'AcousticDecoderLayer']

    def __init__(self, config: VieNeuV3TurboConfig):
        super().__init__(config)
        self.config = config
        self.text_embeddings = nn.Embedding(config.text_vocab_size, config.hidden_size)
        self.audio_embeddings = nn.ModuleList([nn.Embedding(config.audio_vocab_size, config.hidden_size) for _ in range(config.n_vq)])
        from transformers import Qwen3Config, Qwen3Model
        qwen_cfg = Qwen3Config(vocab_size=config.text_vocab_size, hidden_size=config.hidden_size, num_hidden_layers=config.num_hidden_layers, num_attention_heads=config.num_attention_heads, num_key_value_heads=config.num_key_value_heads, head_dim=config.head_dim, intermediate_size=config.intermediate_size, max_position_embeddings=config.max_position_embeddings, rope_parameters={'rope_type': 'default', 'rope_theta': config.rope_theta}, rms_norm_eps=config.rms_norm_eps, attention_dropout=config.attention_dropout, tie_word_embeddings=False)
        self.semantic_backbone = Qwen3Model(qwen_cfg)
        self.semantic_backbone.embed_tokens = self.text_embeddings
        self.acoustic_decoder = AcousticDecoder(config)
        self.text_lm_head = nn.Linear(config.hidden_size, config.text_vocab_size, bias=False)
        self.audio_lm_heads = nn.ModuleList([nn.Linear(config.hidden_size, config.audio_vocab_size, bias=False) for _ in range(config.n_vq)])
        # Optional speaker-embedding projection used by voice cloning: a 192-d
        # speaker vector is projected to hidden_size and added to every row.
        if getattr(config, 'use_speaker_embedding', False):
            self.xvec_proj = nn.Sequential(nn.Linear(config.speaker_embedding_dim, config.hidden_size), nn.LayerNorm(config.hidden_size))
        else:
            self.xvec_proj = None
        self.post_init()

    @property
    def _tied_weights_keys(self) -> dict[str, str]:
        d = {'semantic_backbone.embed_tokens.weight': 'text_embeddings.weight', 'text_lm_head.weight': 'text_embeddings.weight'}
        for ch in range(self.config.n_vq):
            d[f'audio_lm_heads.{ch}.weight'] = f'audio_embeddings.{ch}.weight'
        return d

    def tie_weights(self, *args, **kwargs) -> None:
        self.text_lm_head.weight = self.text_embeddings.weight
        for emb, head in zip(self.audio_embeddings, self.audio_lm_heads):
            head.weight = emb.weight

    def _build_inputs_embeds(self, input_ids: torch.LongTensor, speaker_emb: Optional[torch.Tensor]=None) -> torch.Tensor:
        embeds = self.text_embeddings(input_ids[:, :, 0])
        for ch in range(self.config.n_vq):
            channel_ids = input_ids[:, :, ch + 1]
            valid_mask = channel_ids.ne(self.config.audio_pad_token_id)
            safe_ids = channel_ids.masked_fill(~valid_mask, 0)
            audio_emb = self.audio_embeddings[ch](safe_ids)
            audio_emb = audio_emb * valid_mask.unsqueeze(-1)
            embeds = embeds + audio_emb
        # Add the speaker anchor (same vector on every row) when cloning a voice.
        if self.xvec_proj is not None and speaker_emb is not None:
            embeds = embeds + self.xvec_proj(speaker_emb.to(embeds.dtype)).unsqueeze(1)
        return embeds

    @torch.no_grad()
    def decode_one_frame(self, global_hidden_step: torch.Tensor, text_token_id: Optional[torch.LongTensor]=None, temperature: float=0.8, top_k: int=25, audio_top_p: float=0.95, repetition_penalty: float=1.0, history_by_channel=None) -> tuple[torch.LongTensor, torch.Tensor]:
        """Sample one audio frame (the 16 RVQ codes) from one backbone hidden step.

        This is the core inference step: given the backbone's hidden state for the
        current position, the acoustic decoder autoregressively samples codebook 0
        then conditions each finer codebook on the previous ones.

        Args:
            global_hidden_step: backbone hidden state, shape ``(1, hidden_size)``.
            temperature, top_k, audio_top_p, repetition_penalty: sampling controls.
            history_by_channel: optional per-codebook sliding-window history
                (``RepetitionHistory``) for the repetition penalty; only codes
                from the recent window are penalised.

        Returns:
            ``(frame_codes, last_local_out)`` — the ``n_vq`` sampled codes and the
            acoustic decoder output (reused by the caller for the EOS check).
        """
        n_vq = self.config.n_vq
        H = self.config.hidden_size
        device = global_hidden_step.device
        local_dtype = next(self.acoustic_decoder.parameters()).dtype
        L = len(self.acoustic_decoder.layers)

        cond = global_hidden_step[0].to(dtype=local_dtype)
        if text_token_id is not None:
            safe_id = text_token_id.clamp(0, self.config.text_vocab_size - 1)
            txt = self.text_embeddings(safe_id)[0].to(dtype=local_dtype)
        else:
            txt = torch.zeros(H, dtype=local_dtype, device=device)

        def _sample(ch, vec):
            prev = history_by_channel[ch] if history_by_channel is not None else None
            code = _sample_token(self.audio_lm_heads[ch](vec).float(), temperature=temperature, top_k=top_k, top_p=audio_top_p, repetition_penalty=repetition_penalty, prev_tokens=prev)
            if history_by_channel is not None:
                history_by_channel[ch].add(int(code.item()))
            return code

        # Prefill the two condition tokens (slot 0 = backbone hidden, slot 1 = text),
        # then sample each codebook with a single cached step (lossless vs the full
        # 17-token forward, but O(1) per step instead of O(seq) per step).
        tok = torch.stack([cond, txt]).view(1, 2, H)
        pos = torch.tensor([0, 1], device=device)
        hidden, pk, pv = self.acoustic_decoder.cached_step(tok, pos, [None] * L, [None] * L)
        prefill_out = hidden  # slot-0 output is causal-invariant -> used for the EOS check

        sampled_codes = [_sample(0, hidden[0, 1])]
        for ch in range(1, n_vq):
            emb = self.audio_embeddings[ch - 1](sampled_codes[-1].unsqueeze(0))[0].to(dtype=local_dtype)
            pos = torch.tensor([ch + 1], device=device)
            hidden, pk, pv = self.acoustic_decoder.cached_step(emb.view(1, 1, H), pos, pk, pv)
            sampled_codes.append(_sample(ch, hidden[0, 0]))
        return (torch.stack(sampled_codes), prefill_out)

def _sample_token(logits: torch.Tensor, temperature: float=1.0, top_k: int=0, top_p: float=1.0, repetition_penalty: float=1.0, prev_tokens=None) -> torch.LongTensor:
    if not math.isclose(repetition_penalty, 1.0) and prev_tokens:
        idx = torch.as_tensor(sorted(prev_tokens), device=logits.device, dtype=torch.long)
        sel = logits[idx]
        logits = logits.clone()
        logits[idx] = torch.where(sel < 0, sel * repetition_penalty, sel / repetition_penalty)
    if temperature > 0:
        logits = logits / temperature
    # top_k FIRST, then top_p + softmax + multinomial over just the k candidates instead
    # of the full vocab. Mathematically identical (same support & probabilities to ~1e-7)
    # but avoids a full-vocab sort/scatter each call — ~1.5x faster sampling, which is
    # ~1/3 of per-frame CPU time.
    if top_k > 0:
        k = min(top_k, logits.size(-1))
        cand_logits, cand_idx = torch.topk(logits, k)          # (k,)
    else:
        cand_logits, cand_idx = torch.sort(logits, descending=True)
    probs = cand_logits.softmax(-1)
    if top_p < 1.0:
        keep = (probs.cumsum(-1) - probs) < top_p              # nucleus within candidates
        probs = probs * keep
    choice = torch.multinomial(probs, num_samples=1)
    return cand_idx.gather(-1, choice).squeeze(-1)

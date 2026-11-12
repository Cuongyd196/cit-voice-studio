from __future__ import annotations
from typing import Optional
import torch

def build_prompt_2d(phonemes: str, ref_codes: Optional[torch.LongTensor], tokenizer, config, style_token_id: int=16, ref_phonemes: str='') -> torch.LongTensor:
    """Build the (T, n_vq+1) prompt: a style token, the phonemes, then optional ref rows.

    The leading token selects the speaking style. Inline ``<|emotion_N|>`` tags inside
    ``phonemes`` are picked up by the tokenizer. ``ref_phonemes`` is unused.
    """
    tps = config.text_prompt_start_token_id
    tpe = config.text_prompt_end_token_id
    ref_slot = config.audio_ref_slot_token_id
    audio_pad = config.audio_pad_token_id
    n_vq = config.n_vq
    phone_ids = tokenizer.encode(phonemes, add_special_tokens=False)
    text_token_ids = [style_token_id, tps] + phone_ids + [tpe]
    T_text = len(text_token_ids)
    text_rows = torch.full((T_text, n_vq + 1), audio_pad, dtype=torch.long)
    text_rows[:, 0] = torch.tensor(text_token_ids, dtype=torch.long)
    if ref_codes is None:
        return text_rows
    T_ref = int(ref_codes.shape[0])
    ref_rows = torch.full((T_ref, n_vq + 1), audio_pad, dtype=torch.long)
    ref_rows[:, 0] = ref_slot
    ref_rows[:, 1:] = ref_codes
    return torch.cat([text_rows, ref_rows], dim=0)

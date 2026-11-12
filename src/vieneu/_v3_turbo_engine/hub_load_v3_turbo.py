from __future__ import annotations
from pathlib import Path
from typing import Optional, Union
import torch
from huggingface_hub import hf_hub_download
from safetensors.torch import load_model
from .configuration_v3_turbo import VieNeuV3TurboConfig
from .modeling_v3_turbo import VieNeuV3TurboForTTS

def _apply_dtype(model: VieNeuV3TurboForTTS, device: torch.device, dtype: torch.dtype) -> VieNeuV3TurboForTTS:
    model = model.to(device=device)
    if dtype == torch.float32:
        return model.float()
    if dtype == torch.bfloat16 and device.type == 'cuda':
        return model.to(dtype=torch.bfloat16)
    return model

def load_v3_turbo_checkpoint(path_or_repo: str, *, token: Optional[Union[str, bool]]=None, device: Optional[torch.device]=None, dtype: Optional[torch.dtype]=None, subfolder: Optional[str]=None) -> VieNeuV3TurboForTTS:
    if device is None:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if dtype is None:
        dtype = torch.bfloat16 if device.type == 'cuda' else torch.float32
    local = Path(path_or_repo)
    if subfolder:
        local = local / subfolder
    if local.is_dir() and (local / 'model.safetensors').is_file():
        cfg = VieNeuV3TurboConfig.from_pretrained(str(local))
        model = VieNeuV3TurboForTTS(cfg)
        load_model(model, str(local / 'model.safetensors'), strict=False, device=str(device))
        model.tie_weights()
        model = _apply_dtype(model, device, dtype)
        if next(model.parameters()).is_meta:
            raise RuntimeError(f'Checkpoint weights still on meta after load (dir={local!r}).')
        return model
    return load_v3_turbo_from_hub(path_or_repo, token=token, device=device, dtype=dtype, subfolder=subfolder)

def load_v3_turbo_from_hub(repo_id: str, *, token: Optional[Union[str, bool]]=None, device: Optional[torch.device]=None, dtype: Optional[torch.dtype]=None, subfolder: Optional[str]=None) -> VieNeuV3TurboForTTS:
    if device is None:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if dtype is None:
        dtype = torch.bfloat16 if device.type == 'cuda' else torch.float32
    cfg = VieNeuV3TurboConfig.from_pretrained(repo_id, token=token, subfolder=subfolder or "")
    model = VieNeuV3TurboForTTS(cfg)
    weights_path = hf_hub_download(repo_id, 'model.safetensors', token=token, subfolder=subfolder or None)
    load_model(model, weights_path, strict=False, device=str(device))
    model.tie_weights()
    model = _apply_dtype(model, device, dtype)
    if next(model.parameters()).is_meta:
        raise RuntimeError(f'Checkpoint weights still on meta after load (repo={repo_id!r}).')
    return model

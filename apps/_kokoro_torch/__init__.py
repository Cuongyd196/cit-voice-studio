"""Kokoro-82M bản PyTorch (chép từ hexgrad/kokoro 0.9.4, Apache-2.0) cho đường GPU.

Chỉ phần mô hình (`KModel`): tách âm vẫn là của `apps/kokoro_engine.py`. Không
cài nguyên gói `kokoro` vì nó bắt `misaki[en]` (spacy + mô hình tiếng Anh) dù
đường này không dùng tới. Import torch/transformers - chỉ được nạp sau khi venv
GPU đã gắn vào sys.path (xem `apps/gpu_installer.activate_gpu_venv`).
"""

# syntax=docker/dockerfile:1.7
# CIT Voice Studio chạy làm máy chủ (không cửa sổ). Build từ GỐC repo:
#   docker compose -f packaging/docker/compose.yaml up -d --build          # CPU
#   docker compose -f packaging/docker/compose.yaml -f packaging/docker/compose.gpu.yaml up -d --build   # NVIDIA
# File được đưa vào build: packaging/docker/Dockerfile.dockerignore (danh sách cho phép).

# ---- 1. Giao diện React -> dist/ --------------------------------------------
FROM node:20-bookworm-slim AS ui
WORKDIR /ui
# "prepare": "husky" cần .git, ảnh không có.
ENV HUSKY=0
COPY app-desktop/cit-voice-app/package.json app-desktop/cit-voice-app/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY app-desktop/cit-voice-app/ ./
RUN npm run build

# ---- 2. Backend Python ------------------------------------------------------
# torch cu128 tự mang thư viện CUDA (gói nvidia-* trên PyPI), nên không cần ảnh
# nvidia/cuda: máy chủ chỉ cần driver + NVIDIA Container Toolkit.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS app

# GPU=1: thêm torch cu128 + transformers (~3,5 GB). GPU=0: chỉ ONNX trên CPU.
ARG GPU=0

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    # Lịch sử, cài đặt, khoá API, từ điển phát âm: $LOCALAPPDATA/CitVoiceStudio.
    LOCALAPPDATA=/data

WORKDIR /app

# Thư viện trước, mã nguồn sau: sửa code không phải tải lại thư viện.
COPY pyproject.toml uv.lock README.md LICENSE NOTICE ./
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ "$GPU" = "1" ]; then G="--group gpu-app"; else G=""; fi; \
    uv sync --frozen --no-install-project $G

COPY src ./src
COPY apps ./apps
COPY docs/cit-voice-studio.md DIEU-KHOAN.md PRIVACY.md THIRD-PARTY-NOTICES.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ "$GPU" = "1" ]; then G="--group gpu-app"; else G=""; fi; \
    uv sync --frozen $G

COPY --from=ui /ui/dist ./app-desktop/cit-voice-app/dist

# Mô hình (models/hf_cache), giọng nhân bản (models/custom_voices_*.json) và phần
# tải thêm (addons/, gpu_venv/) nằm cạnh app: trỏ cả vào volume để không mất khi
# tạo lại container.
RUN ln -s /data/models /app/models && ln -s /data/addons /app/addons

VOLUME /data
EXPOSE 8001

# Lần đầu phải tải mô hình nên cho khởi động lâu.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10m --retries=3 \
    CMD python -c "import json, os, urllib.request; s = json.load(urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8001') + '/health', timeout=4)); raise SystemExit(s['status'] != 'ok')"

ENTRYPOINT ["sh", "-c", "mkdir -p /data/models /data/addons && exec \"$@\"", "--"]
CMD ["python", "-m", "apps.web_stream"]

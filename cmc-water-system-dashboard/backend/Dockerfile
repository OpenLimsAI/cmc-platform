# ============================================================
# CMC Pharmaceutical Water System Dashboard — Backend
# Multi-stage hardened Dockerfile (non-root & read_only friendly)
# ============================================================

# ---------- Stage 1: Dependency Builder ----------
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project


# ---------- Stage 2: Hardened Non-Root Production Runtime ----------
FROM python:3.12-slim AS production

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai \
    PATH="/app/.venv/bin:$PATH" \
    MPLCONFIGDIR="/tmp/matplotlib" \
    PNG_FONT_PATH="/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"

# 安装 curl（存活探针）与 Noto CJK 字体（app/export.py 趋势图中文渲染硬依赖），
# 并确保 /usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc 路径稳定存在
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    fonts-noto-cjk \
    && mkdir -p /usr/share/fonts/truetype/noto \
    && if [ ! -f /usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc ] && [ -f /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc ]; then \
         ln -s /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc /usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc; \
       fi \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app app ./app

USER app

EXPOSE 8015

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8015/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8015", "--no-access-log"]

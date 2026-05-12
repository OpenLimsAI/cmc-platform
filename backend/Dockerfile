# ============================================================
# CMAB MDM Portal Backend
# Multi-stage Dockerfile: development / production
# ============================================================

# ---------- 基础镜像 ----------
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=UTC

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv（快速 Python 包管理）
RUN pip install --no-cache-dir uv

WORKDIR /app


# ---------- 开发镜像 ----------
FROM base AS development

# 复制项目元数据
COPY pyproject.toml ./

# 安装依赖（含 dev）
RUN uv pip install --system -e ".[dev]"

# 拷贝代码（开发模式下会被 volume 挂载覆盖）
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]


# ---------- 生产构建 ----------
FROM base AS builder

COPY pyproject.toml ./
RUN uv pip install --system .

COPY . .


# ---------- 生产镜像 ----------
FROM python:3.12-slim AS production

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r app && useradd -r -g app app

WORKDIR /app

# 从 builder 复制已安装包
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制应用代码
COPY --chown=app:app app ./app
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini ./

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

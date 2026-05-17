# 后端 Dockerfile（生产镜像，开发环境用 docker-compose.dev.yml 挂载源码）
FROM python:3.13-slim

WORKDIR /app

# 安装 uv
RUN pip install uv --no-cache-dir

COPY pyproject.toml .
RUN uv sync --no-dev

COPY app/ app/

ENV PYTHONPATH=/app
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

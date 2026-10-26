# Isolated verification only; never used as a production deployment image.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT=/opt/venv
RUN apt-get update && apt-get -o Acquire::Retries=3 install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --extra dev --no-install-project
ENV PATH="/opt/venv/bin:$PATH" PYTHONPATH=/app
COPY . .
CMD ["python", "scripts/run_phase1_tests.py"]

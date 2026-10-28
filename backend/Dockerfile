# EventProof API: FastAPI + ffmpeg. Build context is the repo root (the frozen holdout lives in benchmark/).
# Base images are pinned by digest and Python deps come from uv.lock (--frozen), so a rebuild gets the same bits.
FROM ghcr.io/astral-sh/uv:0.12.10@sha256:2bb3ebca0a796a155094a27773d290c4b074572e6107f171d88d086682fd2500 AS uv

FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337

RUN apt-get update -q \
    && apt-get install -y -q --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY --from=uv /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/eventproof ./eventproof
RUN uv sync --frozen --no-dev
COPY benchmark/holdout /app/benchmark/holdout
COPY benchmark/final/report_final_v1.json /app/benchmark/final/report_final_v1.json

# runs and model caches live in /app/artifacts (a volume); the code paths resolve to it from the package location
RUN useradd --uid 10001 --create-home eventproof && mkdir -p /app/artifacts && chown eventproof /app/artifacts
USER eventproof
ENV PATH=/app/backend/.venv/bin:$PATH
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]
CMD ["uvicorn", "eventproof.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

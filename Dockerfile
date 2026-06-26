FROM python:3.12-slim

WORKDIR /app

# Download uv binary directly (no pip install)
ADD https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz /tmp/uv.tar.gz
RUN tar -xzf /tmp/uv.tar.gz -C /usr/local/bin --strip-components=1 && rm /tmp/uv.tar.gz

# Install deps
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source and re-sync to install local package
COPY src/ ./src/
RUN uv sync --frozen --no-dev
ENV PYTHONPATH=/app/src
ENV UV_CACHE_DIR=/tmp/uv-cache

RUN useradd -r -s /bin/false appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "calendate.main:app", "--host", "0.0.0.0", "--port", "8000"]

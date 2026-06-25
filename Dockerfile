FROM python:3.12-slim

WORKDIR /app

# Install uv + deps in one layer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source
COPY src/ ./src/

# Runtime
ENV PYTHONPATH=/app/src
RUN useradd -r -s /bin/false appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "calendate.main:app", "--host", "0.0.0.0", "--port", "8000"]

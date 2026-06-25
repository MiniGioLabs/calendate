FROM python:3.12-slim

WORKDIR /app

# Install uv via pip (no GHCR pull needed)
RUN pip install uv

# Install deps
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source
COPY src/ ./src/
ENV PYTHONPATH=/app/src

RUN useradd -r -s /bin/false appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "calendate.main:app", "--host", "0.0.0.0", "--port", "8000"]

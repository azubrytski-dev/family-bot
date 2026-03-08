FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml .

# Install dependencies using uv
RUN uv sync --no-install-project --no-dev

# Copy source code
COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "python", "-m", "app.main"]
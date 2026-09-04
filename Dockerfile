FROM python:3.11-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY pyproject.toml .env.example ./
COPY src ./src
COPY prompts ./prompts
COPY golden ./golden
COPY tests ./tests
RUN uv sync --frozen --no-dev
ENV RESULTS_DB=/app/results.db
CMD ["uv", "run", "python", "-m", "model_regression_detection.eval", "--prompt", "v1"]

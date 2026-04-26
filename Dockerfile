FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev

COPY src/ src/
COPY launcher.py ./
COPY .streamlit/ .streamlit/
COPY .env.example .env.example
# EM-DAT CSV is needed at runtime by the disasters MCP server.
COPY data/ data/

EXPOSE 8501

CMD ["uv", "run", "python", "launcher.py"]

FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /bin/

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH=/app/.venv/bin:$PATH
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY prototype prototype
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-install-project

# contract.py loads the spec from two levels above the package, so keep both in /app.
COPY src src
COPY DT-PROTOTYPE-OPENAPI.yaml ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked

EXPOSE 8000
CMD ["uvicorn", "spheere_dt_api.app:app", "--host", "0.0.0.0", "--port", "8000"]

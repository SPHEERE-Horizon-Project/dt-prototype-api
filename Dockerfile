FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /bin/

# Enable to add OpenDSM and its dependencies in a separate environment.
ARG WITH_OPENDSM=false

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH=/app/.venv/bin:$PATH \
    DT_OPENDSM_PYTHON=/opt/opendsm/bin/python

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY prototype prototype
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-install-project

# Build fdasrsf for OpenDSM: requires BLAS/LAPACK.
RUN --mount=type=cache,target=/root/.cache/uv if [ "$WITH_OPENDSM" = "true" ]; then \
    apt-get update && \
    apt-get install -y --no-install-recommends build-essential libblas-dev liblapack-dev libblas3 liblapack3 && \
    python3.12 -m venv --copies --without-pip /opt/opendsm && \
    uv pip install --python /opt/opendsm/bin/python -r prototype/requirements-opendsm-verified.txt && \
    apt-get purge -y build-essential libblas-dev liblapack-dev && apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*; \
    fi

COPY src src
COPY DT-PROTOTYPE-OPENAPI.yaml ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked

EXPOSE 8000
CMD ["uvicorn", "spheere_dt_api.app:app", "--host", "0.0.0.0", "--port", "8000"]

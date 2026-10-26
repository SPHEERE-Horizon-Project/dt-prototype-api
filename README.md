# SPHEERE Digital Twin API

> [!NOTE]
> This codebase includes portions derived from and adapted from [EUReCA](https://github.com/BETALAB-team/EUReCA).

An HTTP API over the Digital Twing building-energy tools: heat demand, energy bought, CO2 and cost, life-cycle cost and impact, and models learned from meter readings. The [OpenAPI document](DT-PROTOTYPE-OPENAPI.yaml) lists every endpoint and explains its terms.

## Start

Install [Task](https://taskfile.dev/) and [uv](https://docs.astral.sh/uv/), then run:

```sh
task setup
task serve              # http://127.0.0.1:8000, docs at /docs
task example:monthly    # in another terminal; also dynamic, simplified, vbdd, energy
task test
```

## Docker

```sh
task compose:up
task compose:down
```

OpenDSM models in `/inverse` need a separate Python (pandas 2) from the API (pandas 3). To support OpenDSM, run `WITH_OPENDSM=true task compose:up`. Otherwise, OpenDSM requests return `503`. Locally, use `task setup:opendsm` to create `.venv-opendsm` and set `DT_OPENDSM_PYTHON` to its Python.

## How it works

- `prototype/` is the read-only DT Prototype codebase.
- Each tool in `src/spheere_dt_api/tools/` runs a DT Prototype command independently, sharing helpers for input and execution.
- Run files are stored in `inputs/<run_id>/` and `results/<run_id>/` under `DT_API_RUNS_ROOT`.
- Long runs (`/pipeline`, OpenDSM) use dedicated workers and return `202` responses.

| Setting                 | Default                             | Effect                                  |
| ----------------------- | ----------------------------------- | --------------------------------------- |
| `DT_API_RUNS_ROOT`      | `.runs`                             | Run storage                             |
| `DT_API_FAST_WORKERS`   | `4`                                 | Parallel runs in the fast lane          |
| `DT_API_SLOW_WORKERS`   | `1`                                 | Parallel runs in the slow lane          |
| `DT_API_TIMEOUT_<TOOL>` | per tool                            | Seconds before a run is stopped         |
| `DT_API_DISABLED_TOOLS` | none                                | Comma-separated tools that answer `503` |
| `DT_OPENDSM_PYTHON`     | `/opt/opendsm/bin/python` in Docker | OpenDSM environment                     |

Tools: `thermal`, `vbdd`, `energy`, `validate`, `footprints`, `quantities`, `assessment`, `lcc`, `lca`, `circularity`, `inverse`, `acceptance`, `pipeline`.

## Releases

The API and OpenAPI spec share one version, shown by `task version`. From `main`:

```sh
task release:patch  # or release:minor / release:major
git show
task release:push
```

GitHub Actions builds pull requests and publishes images on `main`, `v*` tags and manual runs:

```sh
docker run --rm -p 8000:8000 ghcr.io/spheere-horizon-project/dt-prototype-api:0.2.1
```

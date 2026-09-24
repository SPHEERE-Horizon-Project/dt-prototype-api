# DT Prototype API

Exposes the DT Prototype (dynamic, monthly, simplified) via a local HTTP API. The unmodified prototype is in `prototype/`, with the API wrapper in `src/spheere_dt_api/`.

## Start

Install [Task](https://taskfile.dev/) and [uv](https://docs.astral.sh/uv/), then run:

```sh
task setup
task serve
```

The server listens at `http://127.0.0.1:8000`. Its contract is [DT-PROTOTYPE-OPENAPI.yaml](DT-PROTOTYPE-OPENAPI.yaml), also available at `/openapi.json` and `/docs` while the server runs.

In another terminal, run a complete one-zone example for each engine:

```sh
task example:dynamic
task example:monthly
task example:simplified
```

## Docker

To run the API in a container instead, use the Compose stack. It listens on the same port, so the examples above work unchanged:

```sh
task compose:up
task compose:down
```

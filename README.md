# DT Prototype API

The **DT Prototype API** provides annual heating and cooling estimates for buildings. Submit a single request with a building description—including its zones, walls, windows, schedules, and systems—plus a weather file for the target location. The API performs the calculations and returns results as JSON showing both monthly and annual heating and cooling demand (kWh).

All three calculation methods accept the same input:

- **Dynamic**: Simulates each hour of the year to capture how demand varies throughout the day.
- **Monthly**: Uses monthly-averaged inputs; ideal if you just need total demand per month.
- **Simplified**: A coarser, alternative approach for cross-checking results from the other methods.

This project wraps the DT Prototype engines (dynamic, monthly, and simplified) in an HTTP API. The original prototype code is located in `prototype/`, and the API wrapper can be found in `src/spheere_dt_api/`.

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

## Releases

The API package and OpenAPI document share a version, separate from the bundled
calculation engine. Print it with `task version`.

From a clean working tree on `main`, prepare a release:

```sh
task release:patch  # or release:minor / release:major
git show
task release:push
```

Preparation bumps the package, lockfile, and OpenAPI version, runs the existing
checks, and creates a release commit and annotated `vX.Y.Z` tag locally. Failed
checks leave the version edits available for inspection without committing or
tagging. The separate push command publishes `main` and that tag atomically;
a failed push can be retried without preparing another release.

GitHub Actions builds pull requests without publishing and publishes images on
`main`, `v*` tags, and manual runs. A release tag publishes a versioned image:

```sh
docker run --rm -p 8000:8000 ghcr.io/spheere-horizon-project/dt-prototype-api:0.2.1
```

The `latest` image follows `main`; release tags do not move it. Releases use Git
tags and GHCR images without creating GitHub Release records.

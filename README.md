# collect-data-ytb

Collects places to eat, drink, visit and play in Ho Chi Minh City from short YouTube videos.
Requirements: `RAW_REQUIREMENTS.md`. Working guide: `CLAUDE.md`.

## Setup

Requires Docker, [uv](https://docs.astral.sh/uv/) and Python 3.11.

```bash
cp .env.example .env
docker compose up -d --wait              # Postgres 16 + PostGIS on localhost:5433 (+ test DB)
uv sync
uv run alembic upgrade head
uv run python -m app.geo.gadm fetch      # download GADM boundaries (asks first)
uv run python -m app.geo.gadm load --districts data/geo/raw/<file>
uv run uvicorn app.main:app --reload     # GET /health
uv run pytest && uv run ruff check .
```

The `postgis/postgis` image is published for `amd64` only; on Apple Silicon Docker Desktop
runs it through Rosetta, which is fine for development.

GADM boundary files are not committed (license forbids redistribution); see `data/geo/README`.

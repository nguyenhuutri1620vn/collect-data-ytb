# CLAUDE.md

Guidance for Claude Code working in this repository.

## Communication

- Respond to the user in **Vietnamese**. Code, identifiers, commit messages and code comments in English.
- The user is a backend engineer (Go main, also Ruby on Rails). Skip beginner explanations; explain Python/FastAPI idioms only when they differ meaningfully from Go.

## Project

Fully automated pipeline that collects places to eat, drink, visit and play across all of Ho Chi Minh City (old city boundary, before 1/7/2025, all 22 legacy districts) from short YouTube videos, analyzed by Gemini and verified with Google Places. Output is a places dataset, as complete as the videos allow (price, time slots, vibes, group fit, amenities, contacts, tips, media links), for a separate, non-commercial Saigon itinerary web app. **This repo only collects and normalizes data.** The deliverable is data: read-only views in the Postgres schema `output` (R10), which the web app reads directly. FastAPI is an internal ops/debug tool only. Google content (phone, photos, rating, opening hours) is fetched live by the web app via `google_place_id`, not stored here.

**Source of truth: `RAW_REQUIREMENTS.md`.** Every feature must map to a requirement ID (FR-x.y, NFR-x, C-x). If a request conflicts with it, stop and ask; if requirements change, update that file first.

## Hard rules (NEVER break)

1. NEVER scrape, crawl or download content from TikTok or any platform that forbids automated access (C1). New sources go through the `VideoSource` interface and only via an authorized API.
2. NEVER download video files. Gemini reads YouTube videos by URL (C2).
3. NEVER call real external APIs (YouTube, Gemini, Places) in tests. Use fixtures in `tests/fixtures/`.
4. NEVER hardcode API keys or tokens. Read config via `app/core/config.py` (pydantic-settings).
5. NEVER let extraction guess facts (name, address, district, price, hours, group size, contacts, duration, reservation). Missing data is `null` or `[]` (C8). Do not add fallbacks that invent them. Classification fields (`vibes`, `suitable_for`, `time_slots`, `amenities`, `setting`) may be inferred from video content but must have `evidence`; never infer them from category alone.
6. NEVER change the category enum (`an`, `uong`, `tham_quan`, `vui_choi`, `khac`), the fixed enums (`time_slots`, `suitable_for`, `setting`, `price_unit`, `Contact.type`) or the extraction schema without bumping `SCHEMA_VERSION` and asking first. `vibes` and `amenities` are open tags (R9): adding a tag or alias is not a schema change.
7. Schema changes only through Alembic migrations. Never edit the DB by hand in code.
8. NEVER persist Google Places content other than `google_place_id`. No coordinates, raw Places responses, names, addresses, phone, photos, ratings, hours or `businessStatus` in the DB or logs (C7). Coordinates are used in memory only, inside R3, to derive `legacy_district` / `ward` / `legacy_sub_area` and the out-of-scope check (FR-5.2). Places fixtures in `tests/fixtures/` must be synthetic, not copied from real responses. Our own derived values (`match_status`, `closed_permanently`, districts/wards) are fine.
9. NEVER keep YouTube API data (title, description, thumbnail) older than `YOUTUBE_DATA_TTL_DAYS` (30) without refreshing; delete it when a video becomes unavailable (C10).

## Stop and ask before

- Adding a new dependency.
- Writing or running anything that consumes real API quota.
- Dropping or renaming tables or columns, or any destructive migration.
- Changing prompts in `app/analysis/prompts/` (requires `PROMPT_VERSION` bump + eval run). Exception: appending suggested tags to the end of the tag list (FR-9.3).
- Changing matching thresholds, publish rules or aggregation rules (`ATTR_MIN_SHARE`, outlier cut).
- Storing any new field that comes from Google Places or YouTube API (check C7 / C10 first).
- Breaking changes to `output` views (drop, rename or retype a column): bump `OUTPUT_VERSION` (FR-10.4). Additive changes are fine but still update `docs/output.md`.
- Work that touches more than one pipeline stage at once.

## Scope discipline

Only make the changes requested. Do not refactor, rename or "improve" unrelated code. If you notice a problem outside the task, mention it instead of fixing it.

## Stack

Python 3.11 · FastAPI · SQLAlchemy 2.x async · Alembic · Postgres 16 + PostGIS · Pydantic v2 · httpx · google-genai · APScheduler · pytest · ruff · uv

## Commands

```bash
docker compose up -d --wait               # Postgres 16 + PostGIS on port 5433 (+ test DB)
uv sync                                   # install deps
uv run uvicorn app.main:app --reload      # API
uv run python -m app.worker               # scheduler / pipeline worker
uv run alembic upgrade head               # migrate
uv run alembic revision --autogenerate -m "msg"
uv run python -m app.geo.gadm fetch       # download GADM boundaries (asks first)
uv run python -m app.geo.gadm load --districts <file> [--sub-areas <file>]
uv run pytest                             # tests (no network)
uv run ruff check . && uv run ruff format .
uv run python -m app.eval --gold eval/gold   # quality eval (uses real Gemini: ask first)
```

## Layout

```
app/
  main.py               # FastAPI app factory
  worker.py             # APScheduler entrypoint
  core/                 # config, db session, logging, quota guard, retry
  models/               # SQLAlchemy models
  schemas/              # Pydantic API + extraction schemas (VideoExtraction lives here)
  sources/              # VideoSource interface + youtube.py
  discovery/            # R1: keyword matrix, channel tracking, video metadata refresh
  analysis/             # R2: Gemini client, prompts/ (versioned), validation
  enrichment/           # R3: Places client, matching, geo assignment, closed-status recheck
  resolution/           # R4: entity resolution, aggregation
  geo/                  # R5: legacy districts, aliases, point-in-polygon
  tags/                 # R9: open tags (vibes, amenities), seed + alias normalization
  api/                  # R6: routers
  eval/                 # R8: gold-set evaluation (analysis + matching)
migrations/             # Alembic (tables, `output` views, read-only role)
docs/output.md          # R10: output contract for the web app
data/geo/               # GADM boundary files + README (version, source, license)
eval/gold/  eval/match_gold/  eval/reports/
tests/  tests/fixtures/
```

## Pipeline

```
discovered → analyzed → enriched → resolved
     │           └──► rejected (is_relevant=false, or no places)
     └──────────────► failed (after MAX_RETRIES, error_message saved)
```

`videos.status` is processing progress only. Publishing belongs to `places.status` (`draft` / `published` / `hidden` / `out_of_scope`). Mentions have `match_status` (`pending` / `matched` / `unmatched` / `ambiguous` / `out_of_scope`). Refresh jobs (`refresh_videos`, `refresh_places`) run alongside and get quota before discovery.

Each stage:
- Is idempotent (keys: `source` + `video_id`; `analysis_fk` + `ordinal` for mentions; `google_place_id` for places).
- Selects work by status with `FOR UPDATE SKIP LOCKED`, processes it, saves results, then advances status in the same transaction.
- Stores raw Gemini output in `analyses.raw_output` (one row per analysis run). Never stores raw Places responses (hard rule 8).
- Checks `QuotaGuard` before every external call and stops the stage near the daily limit.
- Retries 429 (per-minute rate limit) and 5xx with exponential backoff. A 429 for an exhausted daily quota stops the stage and does not increment `retry_count`.
- Resolution and tag normalization can be re-run from `analyses.raw_output` without calling Gemini. Re-running enrichment calls Places again (FR-7.7).

## Domain notes

- **Administrative units changed on 1/7/2025**: districts (quận/huyện) no longer exist officially; HCMC now has 168 commune-level units. Store both `ward` (new) and `legacy_district` (old). For matched mentions, derive them in R3 from the Places coordinates via point-in-polygon, then drop the coordinates; otherwise fall back to normalized `district_raw` text. Record `district_source`. Keep `legacy_sub_area` for "Quận 2", "Quận 9", "Thủ Đức".
- **No coordinates in output**: the dataset gives places (name, address, district/ward, `google_place_id`), not coordinates. The web app resolves coordinates itself. PostGIS is only for boundary polygons.
- **Output contract (R10)**: the web app reads only schema `output` (`places`, `place_mentions`, `place_media`, `tags`, `legacy_districts`) via a SELECT-only role. Views expose only `published` places, no `raw_output` / pipeline state, no GADM polygons (C11). Internal tables may change freely as long as the views stay compatible.
- **District aliases**: "Q1", "Q.1", "quận nhất" → `Quận 1`, etc. Defined in `app/geo/aliases.py`; extend there, never inline.
- **Boundary data**: GADM (non-commercial license, C11; the project is non-commercial). Record version and source in `data/geo/README`. Never use OSM-derived datasets.
- **Prices**: integers in VND. "k"/"nghìn"/"ngàn" = 1,000; "tr"/"triệu" = 1,000,000. Single price → `min = max`; "miễn phí" → `0`. `price_unit` is `null` when the video does not say.
- **Vietnamese text matching**: normalize (NFC, lowercase, strip diacritics, drop generic words like "quán", "tiệm") before comparing names.
- **Mentions vs places**: a mention is one video's claim; a place is the canonical entity. Place fields are aggregated from mentions (FR-4.3): median for prices, group size and duration; per-value counts plus a filter list (values in ≥ `ATTR_MIN_SHARE` of mentions) for `time_slots`, `vibes`, `amenities`, `suitable_for`. Prefer `unmatched` / `ambiguous` over a wrong match.
- **Open tags** (`vibes`, `amenities`): snake_case, no diacritics. Normalize via `app/tags/` (alias → canonical slug); unseen tags are auto-registered. Homestay is category `khac`, `sub_category="homestay"`, vibe `rieng_tu`.
- **Media**: no frames from videos (C2). A place's media is YouTube thumbnail + `watch?v=<id>&t=<seconds>` links built at read time from evidence timestamps, only for `available` videos.
- **Gemini**: use `generateContent` with the YouTube URL as `file_data`, video part before the text prompt, `response_schema` = `VideoExtraction`. Model and media resolution come from env. YouTube URL input is a preview feature: free tier allows 8h of YouTube video/day, tracked in `quota_usage`.
- **Places**: Text Search (New), Pro-tier field mask only (`id, displayName, formattedAddress, location, businessStatus, types`). Place Details only for the periodic closed-status recheck, field mask `id, businessStatus` (FR-3.6). See hard rule 8 for what may be stored.
- **Timezones**: quota days use `QUOTA_TIMEZONE` (`America/Los_Angeles`, when YouTube and Gemini quotas reset). Schedules and reports use `TIMEZONE` (`Asia/Ho_Chi_Minh`).

## Code conventions

- Type hints everywhere; `ruff` clean.
- Async I/O for DB and HTTP. External clients are thin classes injected via dependencies so tests can swap fakes.
- Structured JSON logging; every pipeline log line includes `video_id` or `place_id`.
- Business logic in plain functions/services, not inside FastAPI routers.
- Tests: unit tests for normalization, price parsing, alias and tag mapping, matching and aggregation; integration tests for each stage with fixtures and a test database; compliance tests that no Places content beyond `place_id` (coordinates included) is persisted and that expired YouTube data is refreshed or deleted (NFR-7).

## Workflow

1. Read the relevant section of `RAW_REQUIREMENTS.md` and name the requirement IDs you are implementing.
2. Propose a short plan (files to touch, tests to add). Wait for approval on anything in "Stop and ask before".
3. Implement in small steps; run `pytest` and `ruff` after each step.
4. After each step, report: ✅ what was done, which requirement IDs it covers, what is next.

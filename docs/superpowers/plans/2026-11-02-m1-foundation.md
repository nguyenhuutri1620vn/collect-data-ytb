# M1 – Nền tảng: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dựng khung sườn chạy được: Postgres 16 + PostGIS qua Docker, project `uv`, config, logging, DB, toàn bộ bảng mục 6, seed quận cũ + tag, nạp polygon GADM, `GET /health`.

**Architecture:** FastAPI app factory + SQLAlchemy 2 async (asyncpg). Schema do Alembic quản lý (migration viết tay). Dữ liệu nền (quận, tag) seed bằng data migration; polygon GADM nạp bằng lệnh riêng vì file không được commit (C11, repo public).

**Tech Stack:** Python 3.11 · uv · FastAPI · SQLAlchemy 2 async · asyncpg · Alembic · GeoAlchemy2 · pydantic-settings · pytest + pytest-asyncio · httpx · ruff · Docker Compose (`postgis/postgis:16-3.6`).

**Spec:** `docs/superpowers/specs/2026-11-02-m1-foundation-design.md` (và `RAW_REQUIREMENTS.md`, `CLAUDE.md`).

## Global Constraints

- Python `>=3.11`, `.python-version` = `3.11`. Không dùng cú pháp chỉ có ở 3.12 (`type X = ...`, `class A[T]`). ruff `target-version = "py311"`, `line-length = 100`.
- Dependency chỉ gồm: runtime `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`, `geoalchemy2`; dev `pytest`, `pytest-asyncio`, `httpx`, `ruff`. Không thêm gói nào khác.
- Không gọi API ngoài (YouTube, Gemini, Places). Tải GADM chỉ ở Task 7, sau khi người dùng đồng ý.
- Không commit file GADM; `data/geo/raw/` nằm trong `.gitignore`.
- Không bảng nào có cột tọa độ địa điểm. Geometry chỉ ở `legacy_districts`, `legacy_sub_areas`, `wards` (MultiPolygon, SRID 4326).
- Giá trị cố định lưu `text` + `CHECK`, không dùng Postgres enum.
- Migration không import từ `app/`; giá trị seed chép thẳng vào file migration.
- Code, identifier, commit message, comment bằng tiếng Anh. Commit kết thúc bằng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Làm trên branch `feat/m1-foundation` (tạo ở Task 1 từ `develop`).
- DB dev: `postgresql+asyncpg://saigon:saigon@localhost:5433/saigon_places`; DB test: `.../saigon_places_test`.

## Review Focus

1. `resolve_legacy_district("Quận 10")` / `"q11"` / `"Q.12"` phải ra đúng Quận 10/11/12, không bị khớp tiền tố thành Quận 1 → test ở Task 4.
2. File GADM đã gộp TP Thủ Đức (feature "Thủ Đức" = cả thành phố) và file trước 2021 (tách Quận 2, 9, Thủ Đức) đều nạp đúng; "Thủ Đức" trong file gộp không bị coi là sub-area → test ở Task 6.
3. Feature ngoài TP.HCM trùng tên quận (ví dụ "Tân Phú" của Đồng Nai) không được nạp → test ở Task 6.
4. Chạy lại `load`, và `alembic downgrade base` rồi `upgrade head`, không lỗi và không nhân đôi dữ liệu → test ở Task 3, 5, 6.
5. `/health` khi DB không kết nối được trả 503 nhanh, không 500 hay treo → test ở Task 2.

---

### Task 1: Tài liệu, môi trường và config

**Files:**
- Modify: `RAW_REQUIREMENTS.md` (NFR-1 dòng 378; bảng mục 14 thêm D21–D23), `CLAUDE.md` (dòng Stack; khối Commands)
- Create: `.gitignore`, `docker-compose.yml`, `docker/initdb/20-create-test-db.sql`, `pyproject.toml`, `.python-version`, `.env.example`, `app/__init__.py`, `app/core/__init__.py`, `app/core/config.py`, `tests/__init__.py`, `tests/conftest.py`, `tests/unit/test_config.py`

**Interfaces:**
- Produces: `app.core.config.Settings` (BaseSettings, đọc `.env`, không phân biệt hoa thường; field snake_case tương ứng mọi biến mục 11 của requirements, cộng `test_database_url: str | None = None`); `get_settings() -> Settings` (cache bằng `functools.lru_cache`). Key API và `admin_token`: `SecretStr | None = None`. `database_url: str` bắt buộc.

- [ ] **Step 1: Tạo branch và sửa tài liệu**

`git switch -c feat/m1-foundation`. Sửa NFR-1 thành "Python 3.11". Thêm vào mục 14:
- D21 | 2026-11-02 | Python 3.11 (bản có sẵn trên máy dev) thay 3.12; không dùng cú pháp riêng của 3.12.
- D22 | 2026-11-02 | Postgres 16 + PostGIS chạy bằng Docker Compose (`postgis/postgis:16-3.6`), cổng 5433.
- D23 | 2026-11-02 | Repo public nên không commit file GADM (C11); tải bằng `python -m app.geo.gadm fetch`, nạp bằng `load`.

`CLAUDE.md`: Stack → `Python 3.11`; Commands thêm `docker compose up -d db`, `uv run python -m app.geo.gadm fetch`, `uv run python -m app.geo.gadm load --districts <file> [--sub-areas <file>]`.

- [ ] **Step 2: `.gitignore`, Docker Compose, init script**

`.gitignore`: `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.env`, `data/geo/raw/`, `.DS_Store`.
`docker-compose.yml`: service `db`, image `postgis/postgis:16-3.6`, env `POSTGRES_USER=saigon`, `POSTGRES_PASSWORD=saigon`, `POSTGRES_DB=saigon_places`, ports `5433:5432`, volume `pgdata`, mount file `./docker/initdb/20-create-test-db.sql:/docker-entrypoint-initdb.d/20-create-test-db.sql:ro` (mount từng file, vì image đã có script `10_postgis.sh` trong thư mục đó); healthcheck `pg_isready -U saigon -d saigon_places`.
Init SQL: `CREATE DATABASE saigon_places_test TEMPLATE template_postgis;`
`README.md`: phần cài đặt (các lệnh ở mục 1 của spec) và ghi chú image PostGIS chỉ có `amd64`, chạy qua Rosetta trên Apple Silicon.

- [ ] **Step 3: Cài `uv`, bật DB**

Run: `brew install uv && docker compose up -d db && docker compose ps`
Expected: service `db` ở trạng thái `healthy`; `docker compose exec db psql -U saigon -d saigon_places_test -Atc "select postgis_version()"` in ra phiên bản 3.6.

- [ ] **Step 4: `pyproject.toml`, `.python-version`, `.env.example`, `uv sync`**

Dependency đúng danh sách Global Constraints (dev nằm trong `[dependency-groups] dev`). `[tool.pytest.ini_options]`: `asyncio_mode = "auto"`, `testpaths = ["tests"]`. `.env.example`: mọi biến mục 11 với giá trị mặc định như requirements, `DATABASE_URL` và `TEST_DATABASE_URL` như Global Constraints. Chép thành `.env`.
Run: `uv sync` → Expected: tạo `.venv` dùng Python 3.11.

- [ ] **Step 5: Viết test config (failing)**

`tests/unit/test_config.py`:
- `test_settings_reads_env(monkeypatch)`: đặt `DATABASE_URL=postgresql+asyncpg://u:p@h:1/d`, `NAME_MATCH_THRESHOLD=0.75`; `Settings(_env_file=None)` → `database_url` đúng, `name_match_threshold == 0.75`, `attr_min_share == 0.3`, `youtube_data_ttl_days == 30`, `quota_timezone == "America/Los_Angeles"`, `gemini_api_key is None`.
- `test_settings_requires_database_url(monkeypatch)`: xóa `DATABASE_URL` → `Settings(_env_file=None)` raise `pydantic.ValidationError`.
- `test_secret_not_in_repr(monkeypatch)`: `GEMINI_API_KEY=abc123` → `"abc123" not in repr(settings)`.

Run: `uv run pytest tests/unit/test_config.py -v` → FAIL (ImportError).

- [ ] **Step 6: Implement `Settings`, `get_settings()` trong `app/core/config.py`**

- [ ] **Step 7: Test pass + lint**

Run: `uv run pytest tests/unit -v && uv run ruff check . && uv run ruff format --check .` → PASS.

- [ ] **Step 8: Commit**

```bash
git add .gitignore README.md docker-compose.yml docker pyproject.toml uv.lock .python-version .env.example app tests RAW_REQUIREMENTS.md CLAUDE.md docs/superpowers
git commit -m "chore: scaffold project, docker postgis and settings"
```

---

### Task 2: Logging, DB session, `/health`

**Files:**
- Create: `app/core/logging.py`, `app/core/db.py`, `app/main.py`, `app/api/__init__.py`, `app/api/health.py`, `tests/unit/test_logging.py`, `tests/integration/__init__.py`, `tests/integration/test_health.py`
- Modify: `tests/conftest.py`

**Interfaces:**
- Consumes: `Settings`, `get_settings()`.
- Produces:
  - `app.core.logging.JsonFormatter(logging.Formatter)`; `configure_logging(level: str = "INFO") -> None`. Mỗi dòng là một JSON object có `ts`, `level`, `logger`, `msg`, cộng mọi key trong `extra` (ví dụ `video_id`, `place_id`).
  - `app.core.db.create_engine(url: str) -> AsyncEngine` (asyncpg, `connect_args={"timeout": 5}`); `get_session(request: Request) -> AsyncIterator[AsyncSession]` (lấy `request.app.state.sessionmaker`).
  - `app.main.create_app(settings: Settings | None = None) -> FastAPI`: lifespan tạo `app.state.engine`, `app.state.sessionmaker` từ `settings or get_settings()`, dispose khi tắt. Module-level `app = create_app()` (không đọc settings lúc import).
  - `GET /health` → 200 `{"status": "ok", "db": "ok"}` hoặc 503 `{"status": "degraded", "db": "error"}`.
  - Fixture `tests/conftest.py`: `test_db_url() -> str` (session scope, đọc `TEST_DATABASE_URL`, fail rõ ràng nếu thiếu); `client` (async, chạy `app.router.lifespan_context` + `httpx.AsyncClient(transport=ASGITransport(app))`, settings trỏ `test_db_url`).

- [ ] **Step 1: Viết test (failing)**

- `test_json_formatter_includes_extra`: log `logger.info("analyzed", extra={"video_id": "abc"})` qua `JsonFormatter` → `json.loads(line)` có `msg == "analyzed"`, `video_id == "abc"`, `level == "INFO"`.
- `test_health_ok(client)`: `GET /health` → 200, body `{"status": "ok", "db": "ok"}`.
- `test_health_db_down`: app với `database_url="postgresql+asyncpg://saigon:saigon@127.0.0.1:1/x"` → 503, body `{"status": "degraded", "db": "error"}`, thời gian < 6s.

Run: `uv run pytest tests -v` → FAIL.

- [ ] **Step 2: Implement logging, db, main, health theo Interfaces**

`/health` bắt mọi exception khi chạy `SELECT 1`, log lỗi (không log URL có mật khẩu), trả 503.

- [ ] **Step 3: Test pass + lint**

Run: `uv run pytest tests -v && uv run ruff check . && uv run ruff format --check .` → PASS.
Run thêm: `uv run uvicorn app.main:app` rồi `curl -s localhost:8000/health` → `{"status":"ok","db":"ok"}`.

- [ ] **Step 4: Commit** — `feat: add json logging, async db session and /health`

---

### Task 3: Models và migration khởi tạo

**Files:**
- Create: `alembic.ini`, `migrations/env.py`, `migrations/script.py.mako`, `migrations/versions/0001_initial_schema.py`, `app/models/__init__.py`, `app/models/base.py`, các module model (cách chia file do người build chọn), `tests/integration/test_migrations.py`, `tests/unit/test_compliance_schema.py`
- Modify: `tests/conftest.py`

**Interfaces:**
- Consumes: `get_settings()`.
- Produces:
  - `app.models.base.Base` (`DeclarativeBase`); `app.models` import mọi model để `Base.metadata` đủ bảng.
  - Class: `Video`, `Analysis`, `Mention`, `Place`, `Tag`, `Channel`, `Keyword`, `KeywordRun`, `VideoKeyword`, `QuotaUsage`, `LegacyDistrict`, `LegacySubArea`, `Ward` — tên bảng và cột đúng mục 6 của `RAW_REQUIREMENTS.md`.
  - Migration revision `0001_initial_schema` (down_revision `None`).
  - `migrations/env.py` async; URL lấy từ `config.get_main_option("sqlalchemy.url")` nếu có, không thì `get_settings().database_url`.
  - Fixture `migrated_db` (session scope, **sync**): chạy `alembic downgrade base` rồi `upgrade head` trên `test_db_url` qua `alembic.command` với `Config` set `sqlalchemy.url`. Fixture `session` (async, function scope): connection + transaction bọc ngoài, rollback sau test.

Quy ước bắt buộc (từ spec 5.4):
- PK: `bigint` identity cho bảng có `id`; `tags` (`kind`, `slug`); `legacy_districts`/`legacy_sub_areas`/`wards` (`name`); `quota_usage` (`date`, `service`, `metric`); `video_keywords` (`video_fk`, `keyword_fk`, `keyword_run_fk`); `channels` (`channel_id`).
- CHECK: `videos.source in ('youtube')`, `videos.status in ('discovered','analyzed','enriched','resolved','rejected','failed')`, `videos.availability in ('available','unavailable')`, `mentions.match_status in ('pending','matched','unmatched','ambiguous','out_of_scope')`, `mentions.district_source in ('coordinates','district_raw')`, `category in ('an','uong','tham_quan','vui_choi','khac')` (mentions, places), `setting in ('indoor','outdoor','mixed')`, `price_unit in ('per_item','per_person','ticket')`, `places.status in ('draft','published','hidden','out_of_scope')`, `tags.kind in ('vibe','amenity')`. Cột nullable cho phép NULL.
- Unique: `videos(source, video_id)`, `mentions(analysis_fk, ordinal)`, `places(google_place_id)`, `keywords(text)`.
- FK như spec 5.4; `videos.current_analysis_fk` thêm bằng `op.create_foreign_key` sau khi tạo `analyses`.
- Index: `videos(status)`, `mentions(match_status)`, `places(status)`.
- Geometry: `geoalchemy2.Geometry("MULTIPOLYGON", srid=4326, spatial_index=False)`, nullable; GiST index khai báo tường minh ở cả model (`Index("ix_<table>_geom", "geom", postgresql_using="gist")` trong `__table_args__`) và migration (`op.create_index(..., postgresql_using="gist")`) để `compare_metadata` không báo lệch.
- `created_at`, `updated_at`: `timestamptz`, `server_default=now()`; model đặt `onupdate=func.now()`.
- Upgrade bắt đầu bằng `CREATE EXTENSION IF NOT EXISTS postgis`. Downgrade drop bảng theo thứ tự ngược, không drop extension.

- [ ] **Step 1: Viết test (failing)**

- `test_upgrade_creates_all_tables(migrated_db)`: query `information_schema.tables` (schema `public`) chứa đủ 13 bảng mục 6.
- `test_migration_matches_models(migrated_db)`: so sánh bằng `alembic.autogenerate.compare_metadata` giữa DB và `Base.metadata` → danh sách diff rỗng (bỏ qua bảng của PostGIS như `spatial_ref_sys`).
- `test_downgrade_then_upgrade(test_db_url)` (sync): `downgrade base` → chỉ còn `spatial_ref_sys` và `alembic_version`; `upgrade head` lại thành công.
- `test_check_constraint_rejects_bad_status(session)`: insert `videos` với `status='published'` → `IntegrityError`.
- `tests/unit/test_compliance_schema.py::test_no_location_columns`: duyệt `Base.metadata`; cột kiểu `Geometry`/`Geography` chỉ có ở `legacy_districts.geom`, `legacy_sub_areas.geom`, `wards.geom`; không cột nào tên `lat`, `lng`, `latitude`, `longitude`, `location`, `coordinates`.

Run: `uv run pytest tests -v` → FAIL.

- [ ] **Step 2: Implement models**
- [ ] **Step 3: Implement `alembic.ini`, `env.py`, `0001_initial_schema.py`**

Viết migration tay; chạy `uv run alembic revision --autogenerate -m check` trên DB trống chỉ để đối chiếu, xóa file sinh ra sau khi đối chiếu.

- [ ] **Step 4: Test pass + chạy trên DB dev**

Run: `uv run pytest tests -v && uv run alembic upgrade head && uv run ruff check .` → PASS.

- [ ] **Step 5: Commit** — `feat: add models and initial schema migration`

---

### Task 4: Chuẩn hóa văn bản và alias quận

**Files:**
- Create: `app/core/text.py`, `app/geo/__init__.py`, `app/geo/districts.py`, `app/geo/aliases.py`, `tests/unit/test_text.py`, `tests/unit/test_aliases.py`

**Interfaces:**
- Produces:
  - `app.core.text.normalize_text(s: str) -> str`: NFC → lowercase → bỏ dấu (`đ` → `d`) → gộp khoảng trắng, strip.
  - `app.geo.districts.LEGACY_DISTRICTS: tuple[str, ...]` — đúng 22 tên theo thứ tự FR-5.3: `"Quận 1", "Quận 3", "Quận 4", "Quận 5", "Quận 6", "Quận 7", "Quận 8", "Quận 10", "Quận 11", "Quận 12", "Bình Thạnh", "Gò Vấp", "Phú Nhuận", "Tân Bình", "Tân Phú", "Bình Tân", "TP Thủ Đức", "Bình Chánh", "Củ Chi", "Hóc Môn", "Nhà Bè", "Cần Giờ"`.
  - `app.geo.districts.TARGET_PLACES: dict[str, int]` — 50 cho Quận 1, 3, 4, 5, 6, 7, 8, 10, 11, Bình Thạnh, Phú Nhuận, Tân Bình; 80 cho TP Thủ Đức; 30 cho Quận 12, Gò Vấp, Tân Phú, Bình Tân; 10 cho Bình Chánh, Củ Chi, Hóc Môn, Nhà Bè, Cần Giờ.
  - `app.geo.districts.LEGACY_SUB_AREAS: tuple[str, ...] = ("Quận 2", "Quận 9", "Quận Thủ Đức")`; `SUB_AREA_PARENT = "TP Thủ Đức"`.
  - `app.geo.aliases.DISTRICT_ALIASES: dict[str, str]` (khóa = alias đã qua `alias_key`, giá trị = tên trong `LEGACY_DISTRICTS`); `DISTRICT_ALIAS_LISTS: dict[str, list[str]]` (tên chuẩn → alias hiển thị, dùng cho seed `legacy_districts.aliases`).
  - `app.geo.aliases.alias_key(s: str) -> str`: `normalize_text`, thay `.`, `,`, `-` bằng khoảng trắng, gộp khoảng trắng.
  - `resolve_legacy_district(raw: str | None) -> str | None`: so khớp **chính xác** `alias_key(raw)` với `DISTRICT_ALIASES`; không tìm chuỗi con; không khớp hoặc rỗng → `None`.
  - `resolve_legacy_sub_area(raw: str | None) -> str | None`: "Quận 2"/"Q2"/"q.2"/"District 2" → `"Quận 2"`; tương tự Quận 9; "Quận Thủ Đức"/"Thủ Đức" → `"Quận Thủ Đức"`; còn lại `None`.

- [ ] **Step 1: Viết test (failing)**

`test_text.py`: `normalize_text("  Quán  Cà Phê Đường ") == "quan ca phe duong"`; chuỗi NFD (`unicodedata.normalize("NFD", "Phú Nhuận")`) cho cùng kết quả với NFC.

`test_aliases.py`, parametrize `(raw, expected)`:
- `"Q1"`, `"Q.1"`, `"q 1"`, `"quận 1"`, `"Quận nhất"`, `"District 1"` → `"Quận 1"`
- `"Quận 10"` → `"Quận 10"`; `"q11"` → `"Quận 11"`; `"Q.12"` → `"Quận 12"`
- `"BT"`, `"bình thạnh"`, `"Q. Bình Thạnh"` → `"Bình Thạnh"`
- `"Tân Bình"` → `"Tân Bình"`; `"Bình Tân"` → `"Bình Tân"`
- `"Quận 2"`, `"Q9"`, `"Thủ Đức"`, `"TP. Thủ Đức"`, `"thành phố Thủ Đức"` → `"TP Thủ Đức"`
- `"huyện Củ Chi"`, `"Củ Chi"` → `"Củ Chi"`; `"H. Nhà Bè"` → `"Nhà Bè"`
- `"Quận 13"`, `"Biên Hòa"`, `""`, `"   "`, `None` → `None`
- `test_every_district_resolves_itself`: mọi `name` trong `LEGACY_DISTRICTS` → `resolve_legacy_district(name) == name`.
- `test_alias_values_are_canonical`: mọi giá trị trong `DISTRICT_ALIASES` thuộc `LEGACY_DISTRICTS`.
- `test_targets`: `set(TARGET_PLACES) == set(LEGACY_DISTRICTS)`, `sum(TARGET_PLACES.values()) == 850`.
- sub-area: `"Q2"` → `"Quận 2"`, `"quận 9"` → `"Quận 9"`, `"Thủ Đức"` → `"Quận Thủ Đức"`, `"Quận 1"` → `None`.

Run: `uv run pytest tests/unit -v` → FAIL.

- [ ] **Step 2: Implement `text.py`, `districts.py`, `aliases.py`**

Alias cho quận số sinh bằng vòng lặp (`quan N`, `q N`, `qN`, `district N`, `dN`), cộng chữ số tiếng Việt thông dụng ("quận nhất" cho 1). Quận 2 và Quận 9 nằm trong alias của `TP Thủ Đức`. Quận/huyện tên chữ có thêm dạng tiền tố `q`, `quan`, `h`, `huyen` và tắt phổ biến (`bt` → Bình Thạnh, `gv` → Gò Vấp, `pn` → Phú Nhuận, `tb` → Tân Bình, `tp` **không** dùng vì mơ hồ).

- [ ] **Step 3: Test pass + lint**

Run: `uv run pytest tests/unit -v && uv run ruff check .` → PASS.

- [ ] **Step 4: Commit** — `feat: add text normalization and legacy district aliases`

---

### Task 5: Seed quận cũ và tag gợi ý

**Files:**
- Create: `app/tags/__init__.py`, `app/tags/seed.py`, `migrations/versions/0002_seed_reference_data.py`, `tests/integration/test_seed.py`

**Interfaces:**
- Consumes: `LEGACY_DISTRICTS`, `TARGET_PLACES`, `LEGACY_SUB_AREAS`, `DISTRICT_ALIAS_LISTS` (Task 4); models `LegacyDistrict`, `LegacySubArea`, `Tag` (Task 3).
- Produces:
  - `app.tags.seed.SeedTag(NamedTuple)`: `kind: str`, `slug: str`, `label: str`, `aliases: tuple[str, ...]`.
  - `app.tags.seed.SEED_TAGS: tuple[SeedTag, ...]` — thứ tự đúng mục 7 (thêm tag mới chỉ nối vào cuối, FR-9.3):
    - vibe: `lang_man` "Lãng mạn" (`hen_ho`), `rieng_tu` "Riêng tư", `giai_tri` "Giải trí", `nang_dong` "Năng động", `thu_gian` "Thư giãn" (`chill`, `yen_tinh`), `soi_dong` "Sôi động", `song_ao` "Sống ảo" (`check_in`, `chup_anh`), `hoai_niem` "Hoài niệm" (`co_xua`), `sang_trong` "Sang trọng", `binh_dan` "Bình dân", `gan_gui_thien_nhien` "Gần gũi thiên nhiên", `van_hoa_lich_su` "Văn hóa lịch sử"
    - amenity: `wifi` "Wifi", `may_lanh` "Máy lạnh", `cho_dau_xe_may` "Chỗ đậu xe máy", `cho_dau_o_to` "Chỗ đậu ô tô", `phong_rieng` "Phòng riêng", `cho_thu_cung` "Cho thú cưng", `khu_vui_choi_tre_em` "Khu vui chơi trẻ em", `o_cam_sac` "Ổ cắm sạc", `nhan_dat_cho` "Nhận đặt chỗ", `giao_hang` "Giao hàng"
  - Migration `0002_seed_reference_data` (down_revision `0001_initial_schema`): insert 22 `legacy_districts` (`name`, `aliases`, `target_places`, `geom` null), 3 `legacy_sub_areas` (`legacy_district = 'TP Thủ Đức'`), 22 `tags` (`mention_count = 0`, `canonical_slug` null, `first_seen_at = now()`). Giá trị chép thẳng vào file. Downgrade xóa đúng các dòng này.

- [ ] **Step 1: Viết test (failing)**

`tests/integration/test_seed.py` (dùng `migrated_db`, `session`):
- `test_districts_seeded`: tập `name` trong DB == `set(LEGACY_DISTRICTS)`; `sum(target_places) == 850`; mỗi dòng có `aliases` chứa đúng `DISTRICT_ALIAS_LISTS[name]`.
- `test_sub_areas_seeded`: 3 dòng, tên == `set(LEGACY_SUB_AREAS)`, `legacy_district == "TP Thủ Đức"`, `geom is None`.
- `test_tags_seeded_match_seed_file`: tập (`kind`, `slug`, `label`, `aliases`) trong DB == tập từ `SEED_TAGS`; 12 vibe, 10 amenity.
- `test_seed_slugs_are_snake_case`: mọi `slug` và alias trong `SEED_TAGS` khớp `^[a-z0-9]+(_[a-z0-9]+)*$`.

Run → FAIL.

- [ ] **Step 2: Implement `app/tags/seed.py` và migration `0002`**
- [ ] **Step 3: Test pass, chạy trên DB dev**

Run: `uv run pytest tests -v && uv run alembic upgrade head && uv run ruff check .` → PASS.
Run: `docker compose exec db psql -U saigon -d saigon_places -Atc "select count(*), sum(target_places) from legacy_districts"` → `22|850`.

- [ ] **Step 4: Commit** — `feat: seed legacy districts, sub-areas and suggested tags`

---

### Task 6: Lệnh GADM `fetch` / `load`

**Files:**
- Create: `app/geo/gadm.py`, `data/geo/README`, `tests/fixtures/geo/districts_pre2021.geojson`, `tests/fixtures/geo/districts_merged.geojson`, `tests/integration/test_gadm_load.py`, `tests/unit/test_gadm_fetch.py`

**Interfaces:**
- Consumes: `resolve_legacy_district`, `resolve_legacy_sub_area`, `LEGACY_DISTRICTS`, `normalize_text`; bảng đã seed (Task 5).
- Produces:
  - `GADM_SOURCES: dict[str, str]` — `"4.1"` → `https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_VNM_2.json.zip`. Bản `"3.6"` thêm ở Task 7 nếu cần.
  - `fetch(version: str, dest_dir: Path, *, assume_yes: bool, confirm: Callable[[str], bool] = ...) -> Path`: HEAD lấy dung lượng, in tên file + URL + dung lượng, gọi `confirm` (mặc định `input`) trừ khi `assume_yes`; tải bằng `urllib.request`, giải nén zip vào `dest_dir`, trả path file `.json`. Từ chối → raise `SystemExit(1)`, không tải.
  - `class BoundaryLoadError(Exception)`.
  - `@dataclass LoadReport`: `districts_loaded: int`, `sub_areas_loaded: int`, `sub_areas_missing: list[str]`.
  - `async def load_boundaries(session: AsyncSession, districts_file: Path, sub_areas_file: Path | None = None) -> LoadReport`.
  - CLI: `python -m app.geo.gadm fetch [--version 4.1] [--dest data/geo/raw] [--yes]`; `python -m app.geo.gadm load --districts PATH [--sub-areas PATH]` (in `LoadReport`, exit 1 khi `BoundaryLoadError`).

Thuật toán `load_boundaries` (spec 5.7, không suy được từ chữ ký):
1. Đọc FeatureCollection; chỉ giữ feature có `normalize_text(NAME_1) in {"ho chi minh", "thanh pho ho chi minh"}`.
2. Với mỗi feature: `resolve_legacy_district(NAME_2)`; feature HCM nào không map được → `BoundaryLoadError` liệt kê tên.
3. File là **trước 2021** nếu có feature map sang sub-area `"Quận 2"` và `"Quận 9"`. Khi đó sub-area polygon lấy từ chính file (Quận 2, Quận 9, Thủ Đức). Nếu **đã gộp**, feature "Thủ Đức" là cả `TP Thủ Đức`; sub-area lấy từ `sub_areas_file` theo quy tắc trước-2021 (bước 1–3 trên file đó, chỉ lấy 3 sub-area); không có file → sub-area giữ `null`, ghi vào `sub_areas_missing`.
4. `UPDATE legacy_districts SET geom = ST_Multi(ST_Union(ARRAY[ST_SetSRID(ST_GeomFromGeoJSON(:g), 4326), ...])) WHERE name = :name` cho từng quận; tương tự `legacy_sub_areas`. Thiếu quận nào trong `LEGACY_DISTRICTS` → `BoundaryLoadError`.
5. `load_boundaries` không tự commit (để test rollback được); CLI mở session, gọi hàm, rồi commit một lần. Ghi đè geom nên chạy lại idempotent.

- [ ] **Step 1: Tạo fixture tổng hợp**

Polygon là hình vuông nhỏ không chồng nhau, tọa độ giả quanh (106.7, 10.8), **không** chép từ GADM. Thuộc tính theo định dạng GADM: `NAME_1`, `NAME_2`.
- `districts_pre2021.geojson`: 24 feature HCM (`NAME_1 = "Hồ Chí Minh"`): 21 quận/huyện ngoài TP Thủ Đức + `"Quận 2"`, `"Quận 9"`, `"Thủ Đức"`; thêm 1 feature `NAME_1 = "Đồng Nai"`, `NAME_2 = "Tân Phú"` ở vị trí khác.
- `districts_merged.geojson`: 22 feature HCM, trong đó `"Thủ Đức"` là một hình vuông bao trùm.

- [ ] **Step 2: Viết test (failing)**

`test_gadm_load.py` (dùng `session` sau `migrated_db`):
- `test_load_pre2021`: report `districts_loaded == 22`, `sub_areas_loaded == 3`, `sub_areas_missing == []`; mọi `legacy_districts.geom` khác null, `ST_GeometryType = 'ST_MultiPolygon'`, `ST_SRID = 4326`; `ST_Area` của TP Thủ Đức == tổng diện tích 3 hình vuông Quận 2, 9, Thủ Đức (sai số 1e-9).
- `test_ignores_other_provinces`: polygon "Tân Phú" trong DB không giao (`ST_Intersects = false`) với hình vuông của Đồng Nai.
- `test_load_merged_without_sub_areas`: report `sub_areas_loaded == 0`, `sub_areas_missing == ["Quận 2", "Quận 9", "Quận Thủ Đức"]`; `legacy_sub_areas.geom` vẫn null; TP Thủ Đức có geom bằng hình vuông bao trùm.
- `test_load_merged_with_sub_area_file`: `load_boundaries(session, merged, pre2021)` → `sub_areas_loaded == 3`; geom TP Thủ Đức lấy từ file merged.
- `test_load_twice_is_idempotent`: chạy 2 lần → cùng kết quả, không lỗi.
- `test_unmapped_name_raises`: fixture tạo trong `tmp_path` thêm feature HCM `NAME_2 = "Quận 99"` → `BoundaryLoadError` chứa `"Quận 99"`.
- `test_missing_district_raises`: fixture bỏ feature "Cần Giờ" → `BoundaryLoadError` chứa `"Cần Giờ"`.

`test_gadm_fetch.py`: monkeypatch `urllib.request.urlopen` → không có network thật:
- `test_fetch_declined_downloads_nothing`: `confirm=lambda _: False` → `SystemExit`, `dest_dir` rỗng.
- `test_fetch_prints_name_url_size(capsys)`: HEAD giả trả `Content-Length: 1048576` → output chứa `gadm41_VNM_2.json.zip`, URL, `1.0 MB`.

Run → FAIL.

- [ ] **Step 3: Implement `app/geo/gadm.py` theo Interfaces và thuật toán**
- [ ] **Step 4: Viết `data/geo/README`**

Nội dung: nguồn (GADM, https://gadm.org), phiên bản dùng (điền ở Task 7), URL, ngày tải, giấy phép (phi thương mại, không phân phối lại, C11), lý do không commit (repo public, D23), lệnh `fetch` / `load`, bảng `wards` chưa có nguồn polygon.

- [ ] **Step 5: Test pass + lint**

Run: `uv run pytest tests -v && uv run ruff check . && uv run ruff format --check .` → PASS.

- [ ] **Step 6: Commit** — `feat: add gadm fetch and boundary loader`

---

### Task 7: Tải GADM thật và nạp polygon

**Files:**
- Modify: `data/geo/README` (phiên bản, ngày tải, kết quả), `app/geo/gadm.py` (chỉ khi cần thêm nguồn 3.6 hoặc alias tên GADM), `app/geo/aliases.py` (chỉ khi tên GADM có dạng chưa map — thêm alias, kèm test case trong `test_aliases.py`)

**Interfaces:**
- Consumes: CLI `fetch` / `load` (Task 6).

- [ ] **Step 1: Hỏi người dùng trước khi tải**

Chạy `fetch` không có `--yes`; báo người dùng tên file, nguồn, dung lượng; chỉ tiếp tục khi họ đồng ý trong chat.

- [ ] **Step 2: Kiểm tra bản 4.1**

Liệt kê `NAME_2` của feature HCM. Nếu có cả "Quận 2", "Quận 9" → file trước 2021, nạp thẳng. Nếu chỉ có "Thủ Đức" gộp → cần nguồn sub-area GADM 3.6:
- Thêm `GADM_SOURCES["3.6"]` (URL bản Việt Nam của GADM 3.6; nếu không có GeoJSON thì tải shapefile, nạp tạm bằng `shp2pgsql` trong container `db` rồi xuất GeoJSON bằng `ST_AsGeoJSON` vào `data/geo/raw/`; không thêm dependency Python).
- Hỏi người dùng lần nữa trước khi tải bản 3.6.

- [ ] **Step 3: Nạp và kiểm tra**

Run: `uv run python -m app.geo.gadm load --districts data/geo/raw/<file> [--sub-areas <file>]`
Expected: `districts_loaded=22`; kiểm tra `select name from legacy_districts where geom is null` → rỗng; `select name, ST_IsValid(geom) from legacy_sub_areas`.
Kiểm tra hợp lý: `select name from legacy_districts where ST_Contains(geom, ST_SetSRID(ST_Point(106.7009, 10.7769), 4326))` → `Quận 1` (Nhà thờ Đức Bà, điểm tham chiếu công khai, chỉ dùng trong lệnh kiểm tra, không lưu).

- [ ] **Step 4: Cập nhật README, xác nhận không commit file GADM**

Run: `git status --porcelain data/geo` → chỉ thấy `data/geo/README`.

- [ ] **Step 5: Toàn bộ test + lint, commit**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check .` → PASS.
Commit: `docs: record gadm version and load results`

---

## Sau M1

Báo cáo theo mẫu ✅ của CLAUDE.md (requirement IDs: FR-5.1, FR-5.3, FR-5.4, FR-5.6, FR-9.1, FR-9.3, mục 6, NFR-1, NFR-2, NFR-3, FR-7.6, C9, C11, R6 `/health`). Bước tiếp theo: M2 – Analysis.

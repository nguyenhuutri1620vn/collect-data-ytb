# Thiết kế M1 – Nền tảng

Ngày: 2026-11-02 · Lộ trình: `RAW_REQUIREMENTS.md` mục 10, M1.

## 1. Mục đích

Dựng khung sườn để các milestone sau (M2 Analysis, M3 Enrichment & Resolution, M4 Discovery & Scheduler) chỉ việc gắn logic vào. M1 **không gọi API ngoài nào** (YouTube, Gemini, Places), không tốn quota.

Khi xong M1, người vận hành làm được trên terminal:

```bash
docker compose up -d db
uv sync
uv run alembic upgrade head
uv run python -m app.geo.gadm fetch      # tải GADM (lần đầu, có xác nhận)
uv run python -m app.geo.gadm load       # nạp polygon vào DB
uv run uvicorn app.main:app --reload     # GET /health → {"status":"ok","db":"ok"}
uv run pytest && uv run ruff check .
```

và query ra 22 quận/huyện cũ (kèm alias, chỉ tiêu, polygon), 3 sub-area của TP Thủ Đức, bộ tag gợi ý.

## 2. Requirement IDs

FR-5.1, FR-5.3, FR-5.4, FR-5.6 (dữ liệu nền), FR-9.1, FR-9.3 (seed tag), mục 6 (toàn bộ bảng), NFR-1, NFR-2, NFR-3, FR-7.6 (logging), C9, C11, R6 `/health`.

## 3. Ngoài phạm vi M1

- Mọi client API ngoài, prompt, `SCHEMA_VERSION` / `PROMPT_VERSION` (M2).
- Chuẩn hóa tag FR-9.2 (M2), matching, aggregation, schema `output` + role chỉ đọc + `docs/output.md` (M3).
- Scheduler, quota guard, retry (M4). Có thư mục rỗng/`__init__.py` cho các package này theo layout CLAUDE.md, không có code giả.
- Polygon phường mới: chưa có nguồn, bảng `wards` để trống, `ward = null` (FR-5.2 cho phép).

## 4. Quyết định đã chốt với người dùng

| # | Quyết định |
|---|---|
| U1 | Đi theo lộ trình M1 → M5; khung sườn = M1. |
| U2 | Output chính thức là schema Postgres `output` (R10), không xuất file. |
| U3 | Python **3.11** (bản có sẵn trên máy) thay vì 3.12. Sửa NFR-1 và CLAUDE.md trước khi code. Không dùng cú pháp chỉ có ở 3.12 (`type X = ...`, generic `class A[T]`). |
| U4 | Postgres 16 + PostGIS chạy bằng Docker Compose, image `postgis/postgis:16-3.6`, map cổng **5433** (5432 đang bị Postgres 14 Homebrew và container `postgres-db` chiếm). |
| U5 | Chỉ cài cái còn thiếu: `uv` (Homebrew) và image PostGIS. Không cài Python mới. |
| U6 | Repo GitHub đang public → **không commit file GADM** (C11 cấm phân phối lại). `data/geo/` chỉ commit `README`; file polygon nằm trong `.gitignore`, tải bằng lệnh `fetch`. Lần tải đầu báo tên file, nguồn, dung lượng để người dùng đồng ý. |
| U7 | Dependency đã duyệt — runtime: `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`, `geoalchemy2`; dev: `pytest`, `pytest-asyncio`, `httpx`, `ruff`. Không thêm gì khác ở M1. |

## 5. Thiết kế

### 5.1. Môi trường

- `docker-compose.yml`: một service `db`, image `postgis/postgis:16-3.6`, cổng `5433:5432`, named volume, healthcheck `pg_isready`. Một script init tạo thêm database test (`saigon_places_test`) và bật extension `postgis` cho cả hai DB.
- Image chỉ có bản `amd64` (~238 MB nén); trên Mac Apple Silicon chạy qua Rosetta của Docker Desktop. Đủ dùng cho dev; ghi chú trong README.
- `pyproject.toml`: `requires-python = ">=3.11"` kèm `.python-version` = `3.11` để `uv` dùng Python có sẵn; cấu hình ruff (target `py311`, line-length 100) và pytest (`asyncio_mode = "auto"`).
- `.env.example` liệt kê đủ biến ở mục 11 của requirements, `DATABASE_URL` trỏ cổng 5433; thêm `TEST_DATABASE_URL`.

### 5.2. Config (`app/core/config.py`)

- Một class `Settings(BaseSettings)` chứa mọi biến mục 11, đúng kiểu và mặc định như requirements.
- `DATABASE_URL` bắt buộc. API key (`YOUTUBE_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_PLACES_API_KEY`) và `ADMIN_TOKEN` kiểu `SecretStr | None` ở M1 (chưa dùng); stage nào dùng thì tự kiểm tra có key.
- Truy cập qua `get_settings()` có cache, để test override được.

### 5.3. DB và logging

- `app/core/db.py`: async engine + `async_sessionmaker`, dependency FastAPI `get_session()`.
- `app/core/logging.py`: formatter JSON trên `logging` chuẩn, nhận `extra` (`video_id`, `place_id`, ...) và in thành field. Cấu hình một lần ở `app/main.py` (và `app/worker.py` sau này).

### 5.4. Model và migration

- `app/models/`: SQLAlchemy 2 typed models (`Mapped[...]`) cho **toàn bộ** bảng mục 6 của requirements, đúng tên cột.
- Một migration khởi tạo, viết tay rõ ràng (autogenerate chỉ để đối chiếu), gồm `CREATE EXTENSION IF NOT EXISTS postgis`.
- Quy ước:
  - Khóa chính `bigint` identity cho bảng có `id`. `tags`: PK (`kind`, `slug`). `legacy_districts`: PK `name`. `legacy_sub_areas`: PK `name`. `wards`: PK `name`. `quota_usage`: PK (`date`, `service`, `metric`). `video_keywords`: PK (`video_fk`, `keyword_fk`, `keyword_run_fk`).
  - Giá trị cố định (`status`, `match_status`, `category`, `setting`, `price_unit`, `district_source`, `availability`, `tags.kind`, ...) lưu `text` + `CHECK` constraint, không dùng Postgres enum type (đổi giá trị chỉ cần sửa CHECK trong migration).
  - Unique: `videos(source, video_id)`, `mentions(analysis_fk, ordinal)`, `places(google_place_id)` (nullable), `keywords(text)`.
  - FK: `analyses.video_fk`, `mentions.video_fk/analysis_fk/place_fk`, `videos.current_analysis_fk` (FK thêm sau khi tạo `analyses`), `keyword_runs.keyword_fk`, `video_keywords.*`, `legacy_sub_areas.legacy_district`, `mentions.legacy_district` và `places.legacy_district` → `legacy_districts.name`.
  - Index cho cột chọn việc theo trạng thái: `videos(status)`, `mentions(match_status)`, `places(status)`.
  - Geometry: `MultiPolygon`, SRID 4326, có GiST index. `legacy_districts.geom` nullable (seed tên trước, polygon nạp sau).
  - `created_at` / `updated_at` dạng `timestamptz` default `now()`; `updated_at` cập nhật bằng ORM (`onupdate`), không dùng trigger.
- Không bảng nào có cột tọa độ địa điểm (C7, D16).

### 5.5. Seed dữ liệu nền (data migration)

- **Quận cũ** (FR-5.3): migration dữ liệu thứ hai insert 22 dòng `legacy_districts` với `aliases` và `target_places` theo mục 9 (tổng 850), và 3 dòng `legacy_sub_areas` (`Quận 2`, `Quận 9`, `Quận Thủ Đức` thuộc `TP Thủ Đức`, `geom` null).
- Nguồn alias trong code là `app/geo/aliases.py` (CLAUDE.md). Migration **chép giá trị** vào chính file migration, không import từ `app/`, để migration cũ không đổi khi code đổi. Alias thêm về sau đi qua migration dữ liệu mới. Downgrade của migration dữ liệu xóa đúng các dòng đã seed.
- **Tag** (FR-9.3): file seed `app/tags/seed.py` chứa danh sách gợi ý mục 7 (`slug`, `label` có dấu, `aliases` khởi tạo), insert bằng migration dữ liệu. `mention_count = 0`, `canonical_slug = null`.

### 5.6. Chuẩn hóa văn bản và alias quận

- `app/core/text.py`: `normalize_text(s)` = NFC → lowercase → bỏ dấu (kể cả `đ` → `d`) → gộp khoảng trắng. Dùng chung cho alias quận, tag (M2) và tên (M3). Chưa có danh sách từ chung "quán", "tiệm" ở M1.
- `app/geo/aliases.py`: map alias đã chuẩn hóa → tên quận chuẩn, và hàm `resolve_legacy_district(raw: str | None) -> str | None` (không khớp → `None`, không đoán, C8). Bao gồm các dạng "Q1", "Q.1", "q 1", "quận 1", "quận nhất", "District 1", "BT", "Thủ Đức", "Quận 2", "Quận 9", "huyện Củ Chi", ...
- Tách riêng `resolve_legacy_sub_area(raw)` cho "Quận 2" / "Quận 9" / "Thủ Đức".

### 5.7. GADM (`app/geo/gadm.py`)

- `fetch`: tải file GeoJSON cấp quận (level 2) của Việt Nam từ trang chính thức GADM vào `data/geo/raw/` (gitignored), dùng `urllib` chuẩn. In tên file, URL, dung lượng; hỏi xác nhận trước khi tải (flag `--yes` để bỏ hỏi).
- Phiên bản: thử GADM 4.1 trước. Nếu 4.1 đã gộp TP Thủ Đức, lấy thêm level 2 của GADM 3.6 cho polygon Quận 2, Quận 9, Thủ Đức (FR-5.6). Nếu 4.1 còn tách ba quận này thì gộp chúng thành `TP Thủ Đức` khi nạp và dùng polygon gốc cho `legacy_sub_areas`.
- `load`: lọc tỉnh Hồ Chí Minh, ghép tên GADM (`NAME_2`) sang tên chuẩn qua `resolve_legacy_district`, nạp bằng `ST_Multi(ST_GeomFromGeoJSON(...))`, `UPDATE` vào dòng đã seed. Lệnh báo lỗi và dừng nếu thiếu quận nào hoặc có tên không map được; chạy lại an toàn (idempotent).
- Nếu bản GADM cần dùng không có GeoJSON (chỉ có shapefile/GeoPackage): chuyển đổi bằng `shp2pgsql` / `ogr2ogr` có sẵn trong container PostGIS, không thêm dependency Python. *(Lựa chọn của Claude.)*
- `data/geo/README`: phiên bản GADM, URL, ngày tải, giấy phép (phi thương mại, không phân phối lại), lý do không commit file.

### 5.8. API

- `app/main.py`: factory `create_app()`, lifespan dựng/đóng engine, cấu hình logging.
- `app/api/health.py`: `GET /health` chạy `SELECT 1`; trả `200 {"status":"ok","db":"ok"}` hoặc `503 {"status":"degraded","db":"error"}`.

### 5.9. Test

- Không gọi mạng. Test DB qua `TEST_DATABASE_URL`; fixture chạy `alembic upgrade head` một lần mỗi session, mỗi test trong transaction rollback.
- Unit: `normalize_text`, `resolve_legacy_district` / `resolve_legacy_sub_area` (bảng case), `Settings` đọc env.
- Integration: migration up/down sạch; seed đủ 22 quận, tổng `target_places = 850`, 3 sub-area, đủ tag gợi ý; `/health` 200 khi DB sống và 503 khi DB lỗi (engine trỏ cổng sai).
- GADM `load`: test với file GeoJSON **tổng hợp** trong `tests/fixtures/geo/` (vài hình vuông đặt tên giả theo định dạng GADM), không dùng dữ liệu GADM thật.
- Compliance (NFR-7) phần tĩnh: test duyệt metadata SQLAlchemy, khẳng định không bảng nào có cột kiểu Geometry/Geography ngoài ba bảng ranh giới, và không có cột tên `lat`, `lng`, `latitude`, `longitude`, `location`.

### 5.10. Sửa tài liệu trước khi code

- `RAW_REQUIREMENTS.md`: NFR-1 → Python 3.11; thêm D21 (Python 3.11), D22 (Postgres 16 + PostGIS qua Docker Compose cổng 5433), D23 (repo public → không commit GADM, tải bằng lệnh).
- `CLAUDE.md`: dòng Stack → Python 3.11; mục Commands thêm `docker compose up -d db` và hai lệnh GADM.
- `.gitignore`: Python, `.env`, `data/geo/raw/`, `.DS_Store`.

## 6. Thứ tự thực hiện

1. Sửa tài liệu (5.10), `.gitignore`.
2. Cài `uv`; `docker-compose.yml`; `pyproject.toml` + `uv sync`; config, logging, db; `/health`; test.
3. Models + migration khởi tạo; test migration + compliance tĩnh.
4. `text.py`, `aliases.py`, tag seed, migration dữ liệu; test.
5. `gadm.py` + fixture tổng hợp + test; `data/geo/README`.
6. Tải GADM thật (hỏi trước), `load`, kiểm tra 22 quận có polygon.

Sau mỗi bước chạy `pytest` + `ruff`, báo cáo theo mẫu ✅ của CLAUDE.md.

## 7. Để lại cho người build

- Tên biến/hàm nội bộ, cách chia file trong `app/models/`.
- Danh sách alias quận đầy đủ (theo mẫu 5.6, không đoán quá mức).
- Cách bố trí fixture pytest.

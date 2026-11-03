# RAW_REQUIREMENTS — Saigon Places Collector (MVP)

> Tài liệu yêu cầu gốc. Mọi quyết định kiến trúc trong code phải truy được về một mục ở đây.
> Khi yêu cầu thay đổi, cập nhật file này trước rồi mới sửa code.
> Lịch sử quyết định: xem mục 14.

---

## 1. Mục tiêu

Xây dựng hệ thống **tự động hoàn toàn** thu thập dữ liệu địa điểm ăn, uống, tham quan, vui chơi trên **toàn TP.HCM cũ** từ video ngắn trên mạng, làm nguồn dữ liệu cho một **web app lập lịch trình đi chơi Sài Gòn** (dự án riêng): người dùng lên plan đi chơi, đi date, đi hội nhóm mà không mất nhiều thời gian lên kế hoạch.

Lý do dùng video làm nguồn: Google Maps và các bản đồ khác đôi khi thiếu những địa điểm nổi tiếng trên mạng xã hội, và không có thông tin như giá món, thời điểm nên đi, không khí, phù hợp đi với ai.

**Phạm vi của dự án này chỉ là thu thập và chuẩn hóa dữ liệu.** Không xây app lập kế hoạch, không xây giao diện người dùng cuối. Dữ liệu phải **đầy đủ nhất có thể** để người dùng web app xem và đánh giá một địa điểm trước khi chọn.

**Output của dự án là dữ liệu**: một bộ view chỉ đọc trong Postgres (schema `output`, R10) mà web app đọc trực tiếp. Web app là dự án phi thương mại.

### 1.1. Thông tin cần thu thập cho mỗi địa điểm

Mỗi thuộc tính truy về một trường trong schema (mục 7) và bảng `places` (mục 6).

**A. Dữ liệu của hệ thống** (trích từ video, lưu lâu dài):

| Thuộc tính | Trường | Ghi chú |
|---|---|---|
| Tên | `name` | Xác minh bằng Places |
| Quận (cũ), phường (mới) | `legacy_district`, `ward`, `legacy_sub_area` | Từ tọa độ; fallback `district_raw` |
| Địa chỉ | `address_raw` | Như video nói |
| Loại hình | `category`, `sub_category` | `sub_category` tự do |
| Khung giờ trong ngày | `time_slots` | sáng / trưa / chiều / tối / khuya |
| Budget | `price_min_vnd`, `price_max_vnd`, `price_unit`, `items` | Không bắt buộc; `items` = món/vé kèm giá |
| Hình thức / không khí | `vibes` | **Tag mở**, không cố định số lượng (xem R9) |
| Phù hợp đi với ai, số người | `suitable_for`, `group_size_min`, `group_size_max` | |
| Tiện ích | `amenities` | Tag mở: wifi, chỗ đậu xe, máy lạnh, cho thú cưng, ... |
| Trong nhà / ngoài trời | `setting` | Planner dùng khi trời mưa |
| Thời gian nên ở lại | `visit_duration_min_minutes`, `visit_duration_max_minutes` | Chỉ khi video nói |
| Cần đặt chỗ | `reservation_required` | |
| Liên hệ | `contacts` | SĐT, Facebook, Instagram, TikTok, Zalo, website — chỉ khi hiện/nói trong video |
| Điểm nổi bật, lưu ý | `highlights`, `tips` | Câu ngắn, ví dụ "đông cuối tuần, nên đến trước 18h" |
| Hình ảnh, video | `media` | Link YouTube nhảy tới đúng timestamp + thumbnail (xem C10) |
| Giờ mở cửa (theo video) | `opening_hours_raw` | |

**B. Dữ liệu Google** (web app lấy trực tiếp bằng `google_place_id`, **hệ thống này không lưu**, xem C7): **tọa độ**, số điện thoại, website, ảnh, rating, số lượt đánh giá, giờ mở cửa, địa chỉ chuẩn. Output của hệ thống này không có tọa độ. Link Google Maps dựng từ `google_place_id` theo dạng Maps URLs (`https://www.google.com/maps/search/?api=1&query=<name>&query_place_id=<id>`).

---

## 2. Phạm vi MVP

### Trong phạm vi
- Khu vực: **toàn bộ TP.HCM cũ** (ranh giới trước ngày 1/7/2025), gồm 22 quận/huyện cũ ở FR-5.3. Không thu thập Bình Dương, Bà Rịa – Vũng Tàu cũ.
- Nguồn video: **YouTube** (ưu tiên Shorts và video ngắn), video công khai.
- Phân tích video: **Gemini API** qua YouTube URL (không tải video về máy).
- Xác minh địa điểm: **Google Places API (New)**.
- Output dữ liệu cho web app qua schema `output` (R10).
- FastAPI là công cụ vận hành nội bộ: xem, lọc dữ liệu và kích hoạt job thủ công khi cần debug. Web app không dùng FastAPI.

### Ngoài phạm vi
- App lập kế hoạch đi chơi, giao diện người dùng cuối.
- Lưu bất kỳ nội dung Google Places nào ngoài `place_id`, kể cả tọa độ (C7). Tọa độ do web app xử lý.
- TikTok, Facebook, Instagram (xem ràng buộc C1).
- Các tỉnh thành khác.
- OpenStreetMap và mọi bộ dữ liệu dựng từ OSM.
- Dữ liệu song ngữ (D5).

---

## 3. Ràng buộc

| ID | Ràng buộc |
|---|---|
| C1 | **Không scrape, không tự động tải nội dung từ TikTok** hoặc bất kỳ nền tảng nào cấm truy cập tự động trong điều khoản. Hệ thống phải có lớp `VideoSource` adapter để có thể thêm nguồn khác sau này nếu có quyền truy cập hợp lệ (ví dụ API chính thức). |
| C2 | **Không tải file video về máy.** Gemini đọc video trực tiếp từ YouTube URL. Không trích ảnh (frame) từ video; hình ảnh chỉ là thumbnail do YouTube API trả về và link timestamp. |
| C3 | **Tự động hoàn toàn.** Không có bước thủ công trong vận hành hằng ngày. Ngoại lệ duy nhất: gán nhãn một lần cho gold set Analysis và gold set matching (R8). |
| C4 | Tính năng YouTube URL của Gemini đang ở trạng thái **preview**: giá và giới hạn có thể thay đổi. Free tier giới hạn **8 giờ video YouTube mỗi ngày**. Hệ thống phải theo dõi tổng số giây video đã xử lý trong ngày quota. |
| C5 | Quota YouTube Data API theo đơn vị mỗi ngày (mặc định khoảng 10.000; `search.list` tốn nhiều đơn vị hơn `playlistItems.list` và `videos.list`). Kiểm tra lại số liệu trên Google Cloud Console. |
| C6 | **Địa giới hành chính mới**: cấp quận/huyện đã bị bỏ từ 1/7/2025. TP.HCM hiện có 168 đơn vị cấp xã (113 phường, 54 xã, 1 đặc khu). Người dùng và creator vẫn dùng tên quận cũ. |
| C7 | **Điều khoản Google Maps Platform** (đã tra ngày 2026-11-02; xem lại khi Google cập nhật): `place_id` được lưu vô thời hạn (Places API Policies). Hệ thống này **chỉ lưu `place_id`**. Tọa độ và mọi nội dung khác (tên, địa chỉ, SĐT, website, ảnh, rating, review, giờ mở cửa, `businessStatus`) chỉ dùng trong bộ nhớ lúc xử lý một mention, không ghi vào DB hay log. Giá trị hệ thống tự suy ra (`legacy_district`, `ward`, `legacy_sub_area`, `match_status`, `closed_permanently`) được lưu. Hiển thị ảnh/review của Google phải ghi công tác giả và có link về Google Maps — trách nhiệm của web app. |
| C8 | Không suy đoán dữ liệu **sự kiện** (tên, địa chỉ, quận, giá, giờ mở cửa, số người, liên hệ, thời gian ở lại, cần đặt chỗ): video không nói thì để `null` hoặc danh sách rỗng. Các trường **phân loại** (`vibes`, `suitable_for`, `time_slots`, `amenities`, `setting`) được phép suy ra từ nội dung video (lời nói, chữ trên màn hình, hình ảnh) nhưng phải có `evidence`; không có tín hiệu trong video thì để rỗng / `null`, không suy từ loại hình. |
| C9 | API key chỉ lấy từ biến môi trường. Không commit key. |
| C10 | **Điều khoản YouTube API Services** (Developer Policies §III.E.4, đã tra ngày 2026-11-02): dữ liệu lấy từ YouTube API (tiêu đề, mô tả, thumbnail, thống kê) chỉ lưu tối đa **30 ngày**, sau đó phải làm mới hoặc xóa, và phải giữ nhất quán với dữ liệu hiện tại trên YouTube. Kết quả phân tích của Gemini không phải dữ liệu YouTube API. |
| C11 | **Giấy phép GADM** chỉ cho mục đích phi thương mại và không cho phân phối lại. Dự án và web app hiện phi thương mại nên dùng được (D19). Không đưa file polygon GADM ra ngoài; schema `output` chỉ chứa tên quận/phường, không chứa polygon. Nếu web app chuyển sang thương mại phải xin phép GADM hoặc thay nguồn polygon. |

---

## 4. Kiến trúc tổng quan

```
Scheduler
  └─► [R1] Discovery     : sinh từ khóa → YouTube Data API → lưu video (status=discovered)
  └─► [R2] Analysis      : Gemini đọc YouTube URL → JSON theo schema → lưu analysis + mentions (status=analyzed | rejected)
  └─► [R3] Enrichment    : Google Places xác minh từng mention → place_id; dùng tọa độ tức thời để gán quận/phường, rồi bỏ tọa độ (status=enriched)
  └─► [R4] Resolution    : gộp mentions thành places chuẩn, tổng hợp thuộc tính, quyết định publish (status=resolved)
  └─► Refresh            : làm mới metadata video (C10, R1) và kiểm tra quán đóng cửa (R3)
[R5] Geography : thư viện dùng chung — R3 gọi để kiểm tra ranh giới và gán ward / legacy_district từ tọa độ tức thời
[R9] Tags      : chuẩn hóa tag mở (vibes, amenities) — dùng ở R2 và R4
[R10] Output   : schema `output` (view chỉ đọc) → web app đọc trực tiếp
FastAPI [R6] : công cụ vận hành nội bộ — đọc dữ liệu, thống kê, kích hoạt job
[R7] Quota & vận hành, [R8] Đánh giá chất lượng
```

### 4.1. Máy trạng thái

`videos.status` (tiến độ xử lý một video, **không** phải trạng thái publish):

```
discovered → analyzed → enriched → resolved
     │           └──► rejected (is_relevant = false, hoặc relevant nhưng không có địa điểm nào)
     └──────────────► failed (sau MAX_RETRIES lần; lưu error_message)
```

- Video chuyển `enriched` khi mọi mention của nó đã có `match_status` khác `pending`.
- Video `failed` không tự chạy lại. Có thể đưa về trạng thái trước qua `POST /jobs/{stage}?retry_failed=true`.
- `videos.availability`: `available` | `unavailable` (video bị xóa/riêng tư, phát hiện ở job refresh).

`mentions.match_status`: `pending` → `matched` | `unmatched` | `ambiguous` | `out_of_scope`.

`places.status` (quyết định ở R4): `draft` | `published` | `hidden` (đóng cửa vĩnh viễn) | `out_of_scope` (ngoài TP.HCM cũ).

---

## 5. Yêu cầu chức năng

### R1. Discovery (tìm video)

- **FR-1.1** Sinh từ khóa từ ma trận: `khu vực × loại hình × bổ ngữ`, bao phủ **toàn bộ 22 quận/huyện cũ**.
  - Khu vực: tên quận cũ, tên phường mới, địa danh (ví dụ "phố Hồ Thị Kỷ").
  - Loại hình: ăn, uống, cafe, ăn vặt, tham quan, vui chơi, homestay, ...
  - Bổ ngữ: "ăn gì", "review", "giá rẻ", "hẹn hò", "đi date", "đi nhóm", "riêng tư", "food tour", "chill".
- **FR-1.2** Gọi YouTube `search.list` với `regionCode=VN`, `relevanceLanguage=vi`, `type=video`, `videoDuration=short` (mặc định), `publishedAfter` = cấu hình (mặc định 18 tháng). Chọn từ khóa theo `priority` giảm dần; khi các quận có số places published chênh lệch, tăng `priority` cho từ khóa của quận đang thiếu (so với chỉ tiêu ở mục 9).
- **FR-1.3** Lấy chi tiết video bằng `videos.list` (thời lượng, tiêu đề, mô tả, kênh, ngày đăng, thumbnail). Bỏ qua video vượt `MAX_VIDEO_SECONDS` (mặc định 300).
- **FR-1.4** Idempotent theo (`source`, `video_id`): video đã có trong DB thì không thêm lại, chỉ ghi thêm liên kết `video_keywords`.
- **FR-1.5** Mỗi lần chạy một từ khóa ghi một bản ghi `keyword_runs`: số kết quả, số video mới, số đơn vị quota. Keyword yield (số places published thu được) tính qua `video_keywords` → `mentions` → `places`.
- **FR-1.6** Theo dõi kênh (`channels`): tỷ lệ video liên quan của từng kênh. Kênh có ít nhất `MIN_CHANNEL_VIDEOS` video đã phân tích và tỷ lệ ≥ `GOOD_CHANNEL_RATIO` được quét định kỳ qua playlist uploads (`playlistItems.list`, rẻ hơn search).
- **FR-1.7** Từ khóa có yield bằng 0 trong `KEYWORD_LOW_YIELD_RUNS` lần chạy liên tiếp bị giảm `priority` một bậc. `priority` không xuống dưới mức tối thiểu.
- **FR-1.8** Job refresh metadata video (theo C10): mỗi video được gọi lại `videos.list` (gộp 50 id/lần) trước khi `metadata_fetched_at` quá `YOUTUBE_DATA_TTL_DAYS` (mặc định 30). Video không còn khả dụng → `availability = unavailable`, xóa `title`, `description`, `thumbnail_url`; mentions và places vẫn giữ, nhưng `media` của video đó không trả ra API.

**Tiêu chí chấp nhận:** chạy discovery 2 lần liên tiếp không tạo bản ghi trùng; mọi query đều có `keyword_runs`; không bản ghi nào có `metadata_fetched_at` cũ hơn 30 ngày.

### R2. Analysis (phân tích video bằng Gemini)

- **FR-2.1** Gọi Gemini `generateContent` với video là YouTube URL (`file_data.file_uri`, dạng `https://www.youtube.com/watch?v=<id>`) và prompt trích xuất. Đặt video trước, prompt sau.
- **FR-2.2** Dùng `response_mime_type=application/json` và `response_schema` (Pydantic, mục 7). Validate lại phía server; nếu sai schema thì gọi lại 1 lần (không tính vào `MAX_RETRIES`), vẫn sai thì `failed`.
- **FR-2.3** Model và `media_resolution` cấu hình qua biến môi trường (`GEMINI_MODEL`, `GEMINI_MEDIA_RESOLUTION`).
- **FR-2.4** Prompt phải yêu cầu:
  - Trả `null` / danh sách rỗng khi video không nói rõ dữ liệu sự kiện (C8).
  - Chuẩn hóa giá tiếng Việt: "k", "nghìn", "ngàn" = 1.000; "tr", "triệu" = 1.000.000. Khoảng giá → `price_min_vnd`, `price_max_vnd`; một mức giá → `min = max`; "miễn phí" → `0`. Ghi đơn vị (theo món / theo người / vé); không rõ đơn vị thì `price_unit = null`.
  - Một video có thể chứa nhiều địa điểm → trả danh sách.
  - Mỗi địa điểm có `evidence` gồm timestamp `MM:SS`, nguồn (`audio` | `onscreen_text` | `description` | `visual`) và đoạn trích hoặc mô tả ngắn. Có ít nhất một evidence có timestamp nếu địa điểm xuất hiện trong video (dùng làm `media`).
  - `vibes`, `amenities`: tag tiếng Việt không dấu dạng `snake_case`, tối đa 5 tag mỗi trường. Ưu tiên dùng danh sách gợi ý (mục 7); được tạo tag mới nếu không có tag phù hợp.
  - `contacts`: chỉ ghi khi số điện thoại / tài khoản / website hiện trên màn hình, được đọc ra, hoặc có trong mô tả video. Ghi đúng như hiển thị.
  - `highlights`, `tips`: tối đa 5 câu mỗi trường, mỗi câu ≤ 100 ký tự, diễn đạt lại ngắn gọn (không chép nguyên lời thoại dài).
  - `video_summary` viết bằng tiếng Việt.
  - `is_relevant=false` nếu video không giới thiệu địa điểm cụ thể nào ở TP.HCM.
- **FR-2.5** Mỗi lần phân tích lưu một bản ghi `analyses`: nguyên văn response JSON (`raw_output`), `prompt_version`, `schema_version`, `model`, `media_resolution`, số token, số giây video. `videos.current_analysis_fk` trỏ tới lần phân tích hiện hành.
- **FR-2.6** Mỗi địa điểm trong output thành một bản ghi `mentions` gắn với `analysis_fk`. Khóa idempotent: (`analysis_fk`, `ordinal`). Phân tích lại một video tạo `analyses` mới và bộ mentions mới; mentions của lần cũ bị gỡ khỏi `places` trong cùng transaction.
- **FR-2.7** `is_relevant=true` nhưng `places` rỗng → video `rejected`.
- **FR-2.8** Tag `vibes` và `amenities` được chuẩn hóa qua R9 trước khi lưu vào `mentions`; tag gốc giữ trong `raw_output`.

**Tiêu chí chấp nhận:** trên gold set đạt ngưỡng ở mục 9.

### R3. Enrichment (Google Places)

- **FR-3.1** Với mỗi mention, gọi Places **Text Search (New)** với chuỗi `name + address_raw + "TP. Hồ Chí Minh"`, kèm location bias theo `legacy_district` của mention (tâm polygon quận) nếu có.
- **FR-3.2** Field mask: `places.id, places.displayName, places.formattedAddress, places.location, places.businessStatus, places.types` (nhóm SKU Pro; kiểm tra lại phân nhóm SKU trước khi cài đặt). Place Details chỉ được gọi cho FR-3.6.
- **FR-3.3** Xét tối đa `PLACES_TOP_N` (mặc định 5) kết quả. Một kết quả là ứng viên khi độ giống tên ≥ `NAME_MATCH_THRESHOLD` (mặc định 0.8). Độ giống tên tính trên tên đã chuẩn hóa (NFC, lowercase, bỏ dấu, bỏ từ chung như "quán", "tiệm") bằng một metric token-based cố định; metric cụ thể chốt ở M3 và ghi vào mục 14.
  - Đúng 1 ứng viên → `matched`.
  - Nhiều ứng viên (ví dụ chuỗi nhiều chi nhánh) và video không có `address_raw` để phân biệt → `ambiguous` (không gán).
  - Không có ứng viên → `unmatched`.
  - Ứng viên được chọn có tọa độ nằm ngoài polygon TP.HCM cũ → `out_of_scope`.
  - `businessStatus = CLOSED_PERMANENTLY` → vẫn `matched`, nhưng R4 đặt place thành `hidden`.
- **FR-3.4** `unmatched` / `ambiguous` vẫn giữ mention, không gán sang quán khác.
- **FR-3.5** Theo C7, chỉ lưu: `google_place_id` và kết quả xử lý của hệ thống (`match_status`, `match_score`, `closed_permanently`, và `legacy_district` / `ward` / `legacy_sub_area` suy ra từ tọa độ theo FR-5.2). Tọa độ và raw response của Places **không** được lưu; log chỉ ghi `place_id` và điểm match. Chạy lại Enrichment hoặc tính lại quận/phường nghĩa là gọi lại Places.
- **FR-3.6** Job định kỳ (mỗi `PLACES_RECHECK_DAYS`, mặc định 30) gọi Place Details cho mỗi `google_place_id` với field mask chỉ `id, businessStatus`. Quán `CLOSED_PERMANENTLY` → `closed_permanently = true`, `places.status = hidden`.

### R4. Entity resolution & tổng hợp

- **FR-4.1** Mentions `matched` có cùng `google_place_id` → cùng một bản ghi `places`.
- **FR-4.2** Mentions `unmatched` / `ambiguous`: gộp nếu tên chuẩn hóa giống nhau ≥ `NAME_MATCH_THRESHOLD` **và** cùng `legacy_district` (suy từ `district_raw`). Mention không có `legacy_district` thì không gộp. Không chắc thì không gộp.
- **FR-4.3** Trường tổng hợp trên `places`:
  - `price_min_vnd`, `price_max_vnd`: trung vị của các mentions có giá, sau khi bỏ giá trị lệch quá 3 lần trung vị. `price_unit`: giá trị xuất hiện nhiều nhất.
  - Trường tag và danh sách phân loại (`time_slots`, `vibes`, `suitable_for`, `amenities`): lưu số đếm theo từng giá trị (`*_counts`, jsonb) và danh sách để lọc gồm các giá trị xuất hiện ở ≥ `ATTR_MIN_SHARE` (mặc định 0.3) số mentions có trường đó không rỗng.
  - `setting`, `reservation_required`: giá trị xuất hiện nhiều nhất; hòa thì `null` (với `setting`: hòa giữa `indoor` và `outdoor` → `mixed`).
  - `group_size_min/max`, `visit_duration_min/max_minutes`: trung vị của các mentions có giá trị.
  - `contacts`: hợp các contact (bỏ trùng sau chuẩn hóa: SĐT chỉ giữ chữ số, URL bỏ query), kèm số mentions nêu.
  - `highlights`, `tips`: hợp các câu, mỗi câu gắn `video_id`; giới hạn 10 câu mỗi trường, ưu tiên câu từ mention có confidence cao.
  - `items`: hợp các món theo tên chuẩn hóa, giá = trung vị.
  - `mention_count`, `source_video_ids`.
  - `confidence`: kết hợp confidence của mentions, trạng thái match và số mentions. Công thức chốt ở M3 và ghi vào mục 14.
- **FR-4.4** `places` chuyển `published` khi `confidence ≥ PUBLISH_THRESHOLD`, có `legacy_district`, và không `out_of_scope` / `hidden`.
- **FR-4.5** `media` của place được dựng khi đọc (không lưu riêng): với mỗi mention thuộc video `available`, trả `thumbnail_url` và link `https://www.youtube.com/watch?v=<id>&t=<giây>` theo evidence có timestamp.

### R5. Địa lý hành chính

- **FR-5.1** Lưu hai lớp: `ward` (phường/xã mới) và `legacy_district` (quận/huyện cũ).
- **FR-5.2** Với mention `matched`, R3 dùng tọa độ Places ngay lúc nhận response (không lưu) để suy ra `legacy_district` bằng point-in-polygon với ranh giới quận cũ, `ward` từ polygon phường mới (không có polygon thì `null`), và `legacy_sub_area`. Mention không có tọa độ (`unmatched`, `ambiguous`) lấy `legacy_district` từ `district_raw` sau khi chuẩn hóa. `mentions.district_source` ghi nguồn: `coordinates` | `district_raw`. Place lấy quận/phường từ mention có `district_source = coordinates` nếu có.
- **FR-5.3** Bảng `legacy_districts` (enum chuẩn hóa): Quận 1, 3, 4, 5, 6, 7, 8, 10, 11, 12, Bình Thạnh, Gò Vấp, Phú Nhuận, Tân Bình, Tân Phú, Bình Tân, TP Thủ Đức (alias "Quận 2", "Quận 9", "Thủ Đức"), Bình Chánh, Củ Chi, Hóc Môn, Nhà Bè, Cần Giờ.
  - Giữ thêm `legacy_sub_area` (`Quận 2` | `Quận 9` | `Quận Thủ Đức`) cho địa điểm thuộc TP Thủ Đức. Cần polygon trước năm 2021 của ba quận này; thiếu polygon thì suy từ `district_raw`, không có thì `null`.
- **FR-5.4** Bảng alias chuẩn hóa: "Q1", "Q.1", "quận nhất", "q1" → `Quận 1`; "BT" → `Bình Thạnh`; ...
- **FR-5.5** Địa điểm có tọa độ nằm ngoài polygon TP.HCM cũ (union các polygon quận cũ) → `places.status = out_of_scope`, không publish.
- **FR-5.6** Nguồn polygon: **GADM** (theo C11). Chọn phiên bản GADM có ranh giới quận cũ; nếu phiên bản đó đã gộp TP Thủ Đức thì lấy polygon Quận 2, 9, Thủ Đức từ phiên bản cũ hơn. Ghi phiên bản và nguồn tải vào `data/geo/README`. Không dùng bộ dữ liệu dựng từ OSM.

### R6. FastAPI

| Method | Path | Mô tả |
|---|---|---|
| GET | `/health` | Healthcheck |
| GET | `/places` | Lọc theo `legacy_district`, `ward`, `category`, `sub_category`, `price_max`, `time_slot`, `vibe`, `suitable_for`, `group_size`, `amenity`, `setting`, `status` (mặc định `published`), phân trang |
| GET | `/places/{id}` | Toàn bộ thuộc tính mục 1.1-A + mentions + evidence + `media` + `google_place_id` + link Google Maps |
| GET | `/videos/{video_id}` | Trạng thái, các lần phân tích (raw output), mentions |
| GET | `/tags` | Danh sách tag `vibes` / `amenities` kèm số lần dùng, alias, tag chuẩn |
| GET | `/stats` | Số video theo trạng thái, số places theo trạng thái và theo `legacy_district` (so với chỉ tiêu mục 9), quota đã dùng hôm nay, chi phí ước tính trên mỗi place published |
| GET | `/keywords` | Từ khóa, priority và yield |
| POST | `/jobs/{stage}` | Kích hoạt một stage (`discover`, `analyze`, `enrich`, `resolve`, `refresh_videos`, `refresh_places`) |
| POST | `/ingest/youtube` | Đưa một YouTube URL cụ thể vào pipeline (dùng để test/debug) |

- Endpoint `POST` yêu cầu header `Authorization: Bearer <ADMIN_TOKEN>`.
- Endpoint `GET` không xác thực; API chỉ chạy nội bộ, không public ra internet. Lý do: API này dành cho người vận hành và trả cả dữ liệu vận hành (`raw_output`, quota, chi phí); web app lấy dữ liệu qua R10, không qua API.

### R7. Scheduler, quota, vận hành

- **FR-7.1** Worker chạy riêng tiến trình với API, lập lịch bằng APScheduler.
- **FR-7.2** Bảng `quota_usage` theo ngày quota: đơn vị YouTube, số giây video Gemini, số request Gemini, số request Places. Ngày quota tính theo `QUOTA_TIMEZONE` (mặc định `America/Los_Angeles`, giờ reset quota của YouTube Data API và Gemini; xác minh lại trên console). Lịch chạy và báo cáo dùng `TIMEZONE` (`Asia/Ho_Chi_Minh`).
- **FR-7.3** Trước mỗi lời gọi API, kiểm tra quota; gần chạm ngưỡng (`QUOTA_SAFETY_RATIO`, mặc định 0.9) thì dừng stage đó đến ngày quota sau. Job refresh (FR-1.8, FR-3.6) được ưu tiên dùng quota trước discovery để không vi phạm C7, C10.
- **FR-7.4** Retry exponential backoff cho 429 (rate limit theo phút) và 5xx; tối đa `MAX_RETRIES` (mặc định 3), sau đó `failed` kèm `error_message`. 429 do hết quota ngày **không** tính là lỗi của bản ghi: dừng stage như FR-7.3, không tăng `retry_count`.
- **FR-7.5** Xử lý tuần tự hoặc concurrency nhỏ cấu hình được (`WORKER_CONCURRENCY`, mặc định 1). Chọn việc bằng `SELECT ... FOR UPDATE SKIP LOCKED` để scheduler và `POST /jobs` chạy đồng thời không xử lý trùng.
- **FR-7.6** Log có cấu trúc (JSON), mọi dòng log của pipeline có `video_id` hoặc `place_id`.
- **FR-7.7** Resolution và chuẩn hóa tag (R9) chạy lại được từ `analyses.raw_output` mà không gọi lại Gemini. Enrichment chạy lại thì gọi lại Places (FR-3.5); đổi bộ polygon thì phải chạy lại Enrichment cho các mention `matched` để tính lại quận/phường. Phân tích lại bằng prompt mới (gọi Gemini) chỉ chạy khi được kích hoạt rõ ràng cho các video có `prompt_version` cũ, và tuân theo FR-2.6.

### R8. Đánh giá chất lượng

- **FR-8.1** Thư mục `eval/gold/` chứa gold set Analysis: 50 video gán nhãn tay (một lần), định dạng JSON giống output chuẩn, rải đều các quận và loại hình.
- **FR-8.2** Lệnh `eval` chạy Analysis trên gold set và báo cáo precision/recall cho: tên quán, giá, category, quận (`district_raw` sau chuẩn hóa → `legacy_district`), `contacts`, `time_slots`, `vibes` và `amenities` (sau chuẩn hóa R9), `suitable_for`, `setting`; và tỷ lệ bịa (trường sự kiện có giá trị trong khi gold là `null`).
  - Ghép địa điểm dự đoán với gold bằng cùng metric độ giống tên của FR-3.3.
  - Giá đúng khi `price_min_vnd`, `price_max_vnd` khớp chính xác sau chuẩn hóa.
- **FR-8.3** Mỗi lần đổi prompt, model, hoặc `media_resolution` phải chạy `eval` và lưu kết quả vào `eval/reports/` kèm `prompt_version`.
- **FR-8.4** Thư mục `eval/match_gold/` chứa gold set matching: khoảng 100 mentions gán nhãn tay `google_place_id` đúng hoặc `none`. Lệnh eval matching báo cáo precision/recall của R3 theo từng mức `NAME_MATCH_THRESHOLD`. Gold set chỉ lưu `place_id` (C7).

### R9. Tag mở (vibes, amenities)

Mục tiêu: không cố định số loại "hình thức" hay tiện ích; thêm loại mới không cần đổi schema hay `SCHEMA_VERSION`.

- **FR-9.1** Bảng `tags` (`kind` = `vibe` | `amenity`): `slug`, `label` (tiếng Việt có dấu), `aliases` (text[]), `canonical_slug` (nullable; khác null nghĩa là tag này là alias của tag khác), `mention_count`, `first_seen_at`.
- **FR-9.2** Chuẩn hóa tag: bỏ dấu, lowercase, `snake_case` → tra alias → tag chuẩn. Tag chưa từng thấy được tự động thêm vào `tags` (không cần duyệt tay, theo C3).
- **FR-9.3** Danh sách tag gợi ý và alias khởi tạo nằm trong một file seed trong code, cập nhật qua migration dữ liệu; danh sách gợi ý được đưa vào prompt. Thêm tag gợi ý hoặc alias **không** cần bump `PROMPT_VERSION` nếu chỉ thêm vào cuối danh sách; mọi thay đổi khác của danh sách trong prompt cần bump và chạy eval.
- **FR-9.4** Khi thêm alias mới, chạy lại R4 để cập nhật `places` (không gọi API).
- **FR-9.5** `GET /tags` và `/stats` hiển thị tag mới xuất hiện trong 7 ngày để người vận hành bổ sung alias khi rảnh (không bắt buộc cho pipeline chạy).

### R10. Output dataset (hợp đồng dữ liệu với web app)

Output của dự án là dữ liệu. Web app đọc trực tiếp từ Postgres qua một schema riêng, không đọc bảng nội bộ và không gọi FastAPI.

- **FR-10.1** Schema `output` gồm các view chỉ đọc, tạo bằng Alembic migration:

  | View | Nội dung |
  |---|---|
  | `output.places` | Một dòng mỗi place `published`: toàn bộ thuộc tính mục 1.1-A, `google_place_id`, `maps_url` (dựng từ `google_place_id` theo mục 1.1-B, `null` nếu không có), `mention_count`, `confidence`, `updated_at` |
  | `output.place_mentions` | Mentions của các place trong `output.places`: `place_id`, `video_id`, thuộc tính trích từ video, `evidence` |
  | `output.place_media` | Mỗi dòng một link: `place_id`, `video_id`, `video_url` có `&t=<giây>`, `thumbnail_url`, `title` — chỉ video `available` (FR-4.5, C10) |
  | `output.tags` | Tag chuẩn (`kind`, `slug`, `label`) để web app hiển thị và dịch |
  | `output.legacy_districts` | Tên quận/huyện cũ, `legacy_sub_area`, tên phường mới thuộc quận (không có polygon, C11) |

- **FR-10.2** View chỉ chứa dữ liệu đã chuẩn hóa: không có `raw_output`, quota, lỗi, trạng thái pipeline, place `draft` / `hidden` / `out_of_scope`.
- **FR-10.3** Web app dùng một role Postgres chỉ có quyền `SELECT` trên schema `output` (role và quyền tạo bằng migration; mật khẩu đăng nhập cấu hình ngoài code).
- **FR-10.4** Schema `output` là hợp đồng có phiên bản (`OUTPUT_VERSION`, ghi trong `COMMENT ON SCHEMA output`). Thêm cột hoặc view mới là thay đổi tương thích. Xóa, đổi tên, đổi kiểu cột là thay đổi phá vỡ: tăng `OUTPUT_VERSION` và báo trước cho web app.
- **FR-10.5** Dữ liệu trong `output` luôn tuân thủ C7 và C10 tại thời điểm đọc: không có tọa độ hay nội dung Google ngoài `google_place_id`; metadata YouTube không quá `YOUTUBE_DATA_TTL_DAYS`.
- **FR-10.6** Có tài liệu mô tả từng view và cột trong `docs/output.md`, cập nhật cùng migration thay đổi view.

---

## 6. Mô hình dữ liệu (Postgres + PostGIS)

| Bảng | Trường chính |
|---|---|
| `videos` | `id`, `source` (`youtube`), `video_id` (unique theo source), `url`, `title`, `description`, `thumbnail_url`, `channel_id`, `published_at`, `duration_s`, `availability`, `metadata_fetched_at`, `status`, `is_relevant`, `current_analysis_fk`, `retry_count`, `error_message`, `created_at`, `updated_at` |
| `analyses` | `id`, `video_fk`, `raw_output` (jsonb), `prompt_version`, `schema_version`, `model`, `media_resolution`, `tokens_in`, `tokens_out`, `video_seconds`, `created_at` |
| `mentions` | `id`, `video_fk`, `analysis_fk`, `ordinal`, `place_fk` (nullable), `google_place_id` (nullable), `match_status`, `match_score`, `name_raw`, `name_normalized`, `address_raw`, `district_raw`, `legacy_district`, `ward`, `legacy_sub_area`, `district_source` (`coordinates` / `district_raw`), `category`, `sub_category`, `items` (jsonb), `price_min_vnd`, `price_max_vnd`, `price_unit`, `time_slots` (text[]), `opening_hours_raw`, `vibes` (text[]), `amenities` (text[]), `suitable_for` (text[]), `group_size_min`, `group_size_max`, `setting`, `visit_duration_min_minutes`, `visit_duration_max_minutes`, `reservation_required`, `contacts` (jsonb), `highlights` (text[]), `tips` (text[]), `evidence` (jsonb), `confidence`, `retry_count`, `error_message` |
| `places` | `id`, `google_place_id` (unique, nullable), `name`, `name_normalized`, `address_raw`, `ward`, `legacy_district`, `legacy_sub_area`, `category`, `sub_category`, `items` (jsonb), `price_min_vnd`, `price_max_vnd`, `price_unit`, `opening_hours_raw`, `time_slots` (text[]), `time_slot_counts` (jsonb), `vibes` (text[]), `vibe_counts` (jsonb), `amenities` (text[]), `amenity_counts` (jsonb), `suitable_for` (text[]), `suitable_for_counts` (jsonb), `group_size_min`, `group_size_max`, `setting`, `visit_duration_min_minutes`, `visit_duration_max_minutes`, `reservation_required`, `contacts` (jsonb), `highlights` (jsonb), `tips` (jsonb), `mention_count`, `source_video_ids`, `closed_permanently`, `confidence`, `status`, `created_at`, `updated_at` |
| `tags` | `kind`, `slug`, `label`, `aliases` (text[]), `canonical_slug`, `mention_count`, `first_seen_at` |
| `channels` | `channel_id`, `title`, `uploads_playlist_id`, `videos_seen`, `videos_relevant`, `last_scanned_at` |
| `keywords` | `id`, `text`, `area`, `category`, `modifier`, `priority`, `runs`, `low_yield_streak`, `last_run_at` |
| `keyword_runs` | `id`, `keyword_fk`, `ran_at`, `results_count`, `new_videos_count`, `quota_units` |
| `video_keywords` | `video_fk`, `keyword_fk`, `keyword_run_fk` |
| `quota_usage` | `date` (theo `QUOTA_TIMEZONE`), `service`, `metric`, `value` |
| `legacy_districts` | `name`, `aliases` (text[]), `target_places` (chỉ tiêu mục 9), `geom` (MultiPolygon) |
| `legacy_sub_areas` | `name`, `legacy_district`, `geom` (MultiPolygon, nullable) |
| `wards` | `name`, `legacy_districts` (text[]), `geom` (MultiPolygon, nullable) |

Ghi chú:
- Các bảng trên là bảng nội bộ; web app chỉ đọc schema `output` (R10).
- Không bảng nào lưu tọa độ địa điểm (C7). PostGIS chỉ dùng cho polygon ranh giới (`legacy_districts`, `legacy_sub_areas`, `wards`). Web app lấy tọa độ từ Google bằng `google_place_id`.
- Category enum (cố định): `an`, `uong`, `tham_quan`, `vui_choi`, `khac`. "Ăn uống" của planner = `an` ∪ `uong`. Homestay, staycation → `khac`, `sub_category = "homestay"`; planner lọc theo vibe `rieng_tu`. Đổi enum là thay đổi phá vỡ, cần migration và chạy lại dữ liệu.

---

## 7. Schema trích xuất của Gemini (v1)

```python
TimeSlot = Literal["sang", "trua", "chieu", "toi", "khuya"]
GroupType = Literal["mot_minh", "cap_doi", "nhom_nho", "nhom_lon", "gia_dinh"]


class Evidence(BaseModel):
    timestamp: str | None  # "MM:SS"; null khi source = description
    source: Literal["audio", "onscreen_text", "description", "visual"]
    text: str  # trích hoặc mô tả ngắn, tối đa ~120 ký tự


class Item(BaseModel):
    name: str
    price_vnd: int | None


class Contact(BaseModel):
    type: Literal["phone", "facebook", "instagram", "tiktok", "zalo", "website", "other"]
    value: str  # đúng như hiển thị trong video


class ExtractedPlace(BaseModel):
    name: str
    address_raw: str | None
    district_raw: str | None  # đúng như video nói, ví dụ "quận 12"
    category: Literal["an", "uong", "tham_quan", "vui_choi", "khac"]
    sub_category: str | None  # tự do, ví dụ "cafe", "homestay", "bảo tàng"
    items: list[Item]
    price_min_vnd: int | None
    price_max_vnd: int | None
    price_unit: Literal["per_item", "per_person", "ticket"] | None
    time_slots: list[TimeSlot]  # [] = video không nói
    opening_hours_raw: str | None
    vibes: list[str]  # tag mở, snake_case, tối đa 5 (R9)
    amenities: list[str]  # tag mở, snake_case, tối đa 5 (R9)
    suitable_for: list[GroupType]  # [] = không có tín hiệu
    group_size_min: int | None  # chỉ khi video nói con số
    group_size_max: int | None
    setting: Literal["indoor", "outdoor", "mixed"] | None
    visit_duration_min_minutes: int | None  # chỉ khi video nói
    visit_duration_max_minutes: int | None
    reservation_required: bool | None  # chỉ khi video nói
    contacts: list[Contact]
    highlights: list[str]  # tối đa 5, mỗi câu ≤ 100 ký tự
    tips: list[str]  # tối đa 5, mỗi câu ≤ 100 ký tự
    evidence: list[Evidence]
    confidence: float  # 0..1, model tự đánh giá


class VideoExtraction(BaseModel):
    is_relevant: bool
    video_summary: str  # tiếng Việt
    places: list[ExtractedPlace]
```

Định nghĩa giá trị cố định (đưa nguyên văn vào prompt):

| Trường | Giá trị | Nghĩa |
|---|---|---|
| `time_slots` | `sang` | 5:00–11:00 |
| | `trua` | 11:00–13:00 |
| | `chieu` | 13:00–17:00 |
| | `toi` | 17:00–22:00 |
| | `khuya` | 22:00–5:00 |
| | (cả ngày) | Video nói đi giờ nào cũng hợp → liệt kê mọi khung video ủng hộ |
| `suitable_for` | `mot_minh` | Đi một mình |
| | `cap_doi` | 2 người, đi date |
| | `nhom_nho` | Nhóm 3–5 người |
| | `nhom_lon` | Nhóm từ 6 người |
| | `gia_dinh` | Có trẻ em hoặc người lớn tuổi |
| `setting` | `indoor` / `outdoor` / `mixed` | Trong nhà / ngoài trời / có cả hai |

Tag gợi ý khởi tạo (R9, mở rộng được):

| Loại | Tag gợi ý |
|---|---|
| `vibes` | `lang_man` (hẹn hò), `rieng_tu` (không gian riêng, ít người: homestay, phòng riêng), `giai_tri`, `nang_dong` (vận động), `thu_gian` (chill, yên tĩnh), `soi_dong` (đông vui, nhạc lớn), `song_ao` (check-in, chụp ảnh), `hoai_niem` (cổ, xưa), `sang_trong`, `binh_dan`, `gan_gui_thien_nhien`, `van_hoa_lich_su` |
| `amenities` | `wifi`, `may_lanh`, `cho_dau_xe_may`, `cho_dau_o_to`, `phong_rieng`, `cho_thu_cung`, `khu_vui_choi_tre_em`, `o_cam_sac`, `nhan_dat_cho`, `giao_hang` |

`SCHEMA_VERSION` và `PROMPT_VERSION` là hằng số trong code, lưu vào mỗi bản ghi `analyses`.

---

## 8. Yêu cầu phi chức năng

- **NFR-1** Python 3.11 (D21), FastAPI, SQLAlchemy 2.x (async), Alembic, Pydantic v2, `httpx`, SDK `google-genai`, APScheduler, pytest, ruff. Quản lý package bằng `uv`.
- **NFR-2** Cấu hình qua biến môi trường (`pydantic-settings`), có `.env.example`.
- **NFR-3** Test không bao giờ gọi API thật: mock YouTube, Gemini, Places bằng fixture JSON.
- **NFR-4** Mỗi stage idempotent và có thể chạy lại an toàn.
- **NFR-5** Đo chi phí: báo cáo chi phí ước tính trên mỗi place published, dùng đơn giá trong biến môi trường (mục 11).
- **NFR-6** Lớp `VideoSource` (interface) tách phần tìm video và lấy metadata khỏi logic phân tích. Analysis cần một URL mà Gemini đọc được trực tiếp (C2), nên một nguồn mới chỉ dùng được R2 nếu Gemini hỗ trợ đọc nguồn đó; nếu không, cần bổ sung yêu cầu riêng.
- **NFR-7** Tuân thủ điều khoản dữ liệu (C7, C10): có test kiểm tra không lưu trường Places nào ngoài `place_id` (kể cả tọa độ), và job refresh không để metadata YouTube quá hạn.

---

## 9. Tiêu chí thành công của MVP

| Chỉ số | Ngưỡng |
|---|---|
| Bao phủ theo quận | Mọi quận/huyện cũ đạt `legacy_districts.target_places` (số places published): Quận 1, 3, 4, 5, 6, 7, 8, 10, 11, Bình Thạnh, Phú Nhuận, Tân Bình ≥ 50 mỗi quận; TP Thủ Đức ≥ 80; Quận 12, Gò Vấp, Tân Phú, Bình Tân ≥ 30 mỗi quận; Bình Chánh, Củ Chi, Hóc Môn, Nhà Bè, Cần Giờ ≥ 10 mỗi huyện. Tổng tối thiểu 850. Chưa có mốc thời gian |
| Precision tên quán (gold set) | ≥ 90% |
| Precision giá, category | ≥ 80% |
| Precision quận (`district_raw` → `legacy_district`, gold set) | ≥ 85% |
| Tỷ lệ bịa (giá trị sự kiện khi gold là null) | ≤ 5% |
| Precision contacts (gold set) | ≥ 95% |
| Precision matching Places (match gold set) | ≥ 95% |
| Precision/recall `time_slots`, `vibes`, `amenities`, `suitable_for`, `setting` | Đo và báo cáo; ngưỡng chốt sau eval đầu tiên |
| Pipeline chạy liên tục 7 ngày không cần can thiệp | Có |
| Không có dữ liệu YouTube / Places quá hạn (C7, C10) | Có |

---

## 10. Lộ trình

1. **M1 – Nền tảng**: scaffold dự án, DB schema + migrations, PostGIS, `legacy_districts` + aliases + polygon GADM, `tags` + seed, `.env.example`, `/health`.
2. **M2 – Analysis**: client Gemini (free tier), prompt v1, schema v1, chuẩn hóa tag, `POST /ingest/youtube`, gold set + lệnh `eval`. Lặp đến khi đạt ngưỡng mục 9.
3. **M3 – Enrichment & Resolution**: chốt metric độ giống tên và công thức confidence, client Places, match gold set, matching, gán quận/phường từ tọa độ tức thời, gộp mentions, tổng hợp, `GET /places`, schema `output` + role chỉ đọc + `docs/output.md` (R10).
4. **M4 – Discovery, Refresh & Scheduler**: ma trận từ khóa toàn thành phố, YouTube client, theo dõi kênh, job refresh video và Places, quota, worker.
5. **M5 – Mở rộng**: cân bằng bao phủ theo quận, tối ưu chi phí, chuyển paid tier nếu cần.

---

## 11. Biến môi trường

```
DATABASE_URL=
YOUTUBE_API_KEY=
GEMINI_API_KEY=
GEMINI_MODEL=
GEMINI_MEDIA_RESOLUTION=low|default
GOOGLE_PLACES_API_KEY=
ADMIN_TOKEN=
TIMEZONE=Asia/Ho_Chi_Minh
QUOTA_TIMEZONE=America/Los_Angeles
MAX_VIDEO_SECONDS=300
PUBLISHED_AFTER_MONTHS=18
NAME_MATCH_THRESHOLD=0.8
PUBLISH_THRESHOLD=0.6
ATTR_MIN_SHARE=0.3
PLACES_TOP_N=5
PLACES_RECHECK_DAYS=30
YOUTUBE_DATA_TTL_DAYS=30
QUOTA_SAFETY_RATIO=0.9
GEMINI_DAILY_VIDEO_SECONDS=28800
GEMINI_DAILY_REQUESTS=
YOUTUBE_DAILY_UNITS=10000
PLACES_DAILY_REQUESTS=
GOOD_CHANNEL_RATIO=0.5
MIN_CHANNEL_VIDEOS=5
KEYWORD_LOW_YIELD_RUNS=3
WORKER_CONCURRENCY=1
MAX_RETRIES=3
GEMINI_PRICE_INPUT_PER_1M_USD=0
GEMINI_PRICE_OUTPUT_PER_1M_USD=0
PLACES_TEXT_SEARCH_PRICE_PER_1K_USD=
```

---

## 12. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Gemini YouTube URL đổi giá/giới hạn (preview) | Model, quota cấu hình được; adapter `VideoSource`; theo dõi chi phí |
| Nội dung YouTube về ăn chơi Sài Gòn ít hơn TikTok, đặc biệt ở huyện ngoại thành | Đo keyword yield, theo dõi kênh tốt, tăng priority cho quận thiếu, chỉ tiêu theo quận thấp hơn cho huyện |
| Gemini bịa địa chỉ/giá/SĐT | Prompt yêu cầu null, evidence bắt buộc, đo tỷ lệ bịa và precision contacts trên gold set |
| Gemini gán tag theo cảm tính; tag mở bị phân mảnh (nhiều tag cùng nghĩa) | Danh sách gợi ý trong prompt, alias trong `tags`, tổng hợp theo tỷ lệ (`ATTR_MIN_SHARE`), theo dõi tag mới ở `/tags` |
| Gán nhầm quán khi match Places (đặc biệt chuỗi nhiều chi nhánh) | Ngưỡng tên + ranh giới, trạng thái `ambiguous`, ưu tiên `unmatched` hơn match sai, match gold set |
| Vi phạm điều khoản Google Places hoặc YouTube API | Chỉ lưu `place_id` (không lưu tọa độ); refresh metadata YouTube ≤ 30 ngày; test NFR-7 |
| Hết quota vì job refresh tăng theo số dữ liệu | Refresh dùng `videos.list` 50 id/lần (rẻ); theo dõi tỷ lệ quota refresh / discovery ở `/stats` |
| Dữ liệu cũ (quán đóng, đổi giá) | `publishedAfter`, refresh `businessStatus` định kỳ, giá lấy trung vị |
| Ranh giới quận cũ và phường mới không trùng khớp | Suy ra quận cũ từ tọa độ, không chỉ từ tên phường |
| GADM không cho dùng thương mại (C11) | Dự án phi thương mại; không đưa polygon ra `output`; xin phép hoặc thay nguồn nếu web app chuyển sang thương mại |
| Web app phụ thuộc chặt vào schema DB | Chỉ cho đọc schema `output` có phiên bản (R10); bảng nội bộ đổi tự do miễn view giữ nguyên |

---

## 13. Câu hỏi mở (cần chốt)

Hiện không có câu hỏi mở. Các câu hỏi đã chốt nằm ở mục 14.

---

## 14. Quyết định đã chốt

| ID | Ngày | Quyết định |
|---|---|---|
| D1 | 2026-11-02 | ~~Khu vực ưu tiên chỉ dùng cho từ khóa~~ → thay bằng D11. |
| D2 | 2026-11-02 | Polygon dùng GADM cho cả dev và dữ liệu chính thức (C11, FR-5.6). |
| D3 | 2026-11-02 | Gemini free tier cho M1–M2; code không phụ thuộc tier, giới hạn đọc từ biến môi trường. Chuyển paid khi free tier làm vỡ tiêu chí "7 ngày không can thiệp". |
| D4 | 2026-11-02 | Ngưỡng matching chỉnh dựa trên match gold set (FR-8.4); `NAME_MATCH_THRESHOLD=0.8`, `PUBLISH_THRESHOLD=0.6` chỉ là giá trị khởi điểm. |
| D5 | 2026-11-02 | Không lưu song ngữ. Dữ liệu tiếng Việt; các trường phân loại dùng slug để planner dịch bằng bảng tra. |
| D6 | 2026-11-02 | Thuộc tính cho planner: `time_slots` (thay `best_time`), `suitable_for`, `group_size_min/max`; `price_unit` cho phép `null`; thêm evidence source `visual`. |
| D7 | 2026-11-02 | ~~Tách dữ liệu Google vào `place_google_cache` có TTL~~ → thay bằng D14. |
| D8 | 2026-11-02 | Trạng thái video kết thúc bằng `resolved`; publish là trạng thái của `places`. Thêm `match_status = ambiguous`. |
| D9 | 2026-11-02 | Lưu mỗi lần phân tích vào bảng `analyses`; thêm `keyword_runs`, `video_keywords`, `legacy_sub_areas`. |
| D10 | 2026-11-02 | Ngày quota tính theo `QUOTA_TIMEZONE` (giờ Pacific); 429 hết quota ngày không làm video `failed`. |
| D11 | 2026-11-02 | Bao phủ toàn TP.HCM cũ; bỏ danh sách khu vực ưu tiên; chỉ tiêu tính theo từng quận/huyện cũ. |
| D12 | 2026-11-02 | Homestay giữ category `khac` (không đổi enum), `sub_category = "homestay"`, vibe `rieng_tu`. |
| D13 | 2026-11-02 | `vibes` và `amenities` là tag mở, chuẩn hóa qua bảng `tags` (R9); thêm loại mới không cần đổi schema. |
| D14 | 2026-11-02 | Theo điều khoản đã tra (C7): chỉ lưu `place_id` lâu dài ~~và tọa độ ≤ 30 ngày (`place_locations`)~~ (tọa độ: xem D16); không lưu raw response Places. SĐT, ảnh, rating, giờ mở cửa của Google do web app lấy trực tiếp. Hệ thống tự thu thập thông tin đầy đủ từ video: contacts, amenities, setting, thời gian ở lại, đặt chỗ, highlights, tips, media. |
| D15 | 2026-11-02 | Theo YouTube Developer Policies (C10): metadata video làm mới ≤ 30 ngày (FR-1.8); video không còn khả dụng thì xóa tiêu đề, mô tả, thumbnail. |
| D16 | 2026-11-02 | Không lưu tọa độ. Tọa độ Places chỉ dùng tức thời ở R3 để gán quận/phường và lọc ngoài phạm vi; output chỉ có địa điểm (tên, địa chỉ, quận/phường), web app tự xử lý tọa độ. Bỏ bảng `place_locations` và bộ lọc `near`. |
| D17 | 2026-11-02 | Giữ `legacy_district` / `ward` / `legacy_sub_area` suy ra từ tọa độ Places (dữ liệu của hệ thống, không phải nội dung Google). Kiểm tra quán đóng cửa bằng Place Details chỉ với field `id, businessStatus`. |
| D18 | 2026-11-02 | Chỉ tiêu bao phủ tính theo từng quận/huyện cũ, số liệu ở mục 9. Chưa đặt mốc thời gian. |
| D19 | 2026-11-02 | Dự án và web app phi thương mại; dùng GADM theo giấy phép phi thương mại (C11). |
| D20 | 2026-11-02 | Output là dữ liệu: web app đọc trực tiếp schema `output` (view chỉ đọc, có phiên bản) bằng role chỉ đọc (R10). FastAPI chỉ là công cụ vận hành nội bộ. |
| D21 | 2026-11-02 | Python 3.11 (bản có sẵn trên máy dev) thay 3.12; không dùng cú pháp riêng của 3.12. |
| D22 | 2026-11-02 | Postgres 16 + PostGIS chạy bằng Docker Compose (`postgis/postgis:16-3.6`), cổng 5433. |
| D23 | 2026-11-02 | Repo public nên không commit file GADM (C11); tải bằng `python -m app.geo.gadm fetch`, nạp bằng `load`. |
| D25 | 2026-11-03 | Bỏ Google Places hoàn toàn. Không gọi Places, không lưu `google_place_id`, không có `maps_url`, không kiểm tra quán đóng cửa, không gán quận/phường từ tọa độ. Gộp mention thành place chỉ theo FR-4.2 (tên chuẩn hóa ≥ `NAME_MATCH_THRESHOLD` và cùng `legacy_district` từ `district_raw`; không chắc thì không gộp). Thay thế: FR-3.1–3.6, FR-4.1, FR-8.4, FR-10.1 (`google_place_id`, `maps_url`), D14, D16, D17. Hệ quả cần chốt lại: không còn khớp Places nên mọi place dùng hệ số 0.7 trong công thức confidence, khiến một mention đơn (0.9) chỉ đạt 0.441 dưới ngưỡng publish 0.6. Công thức confidence và `PUBLISH_THRESHOLD` cần chốt lại trước khi publish. |
| D26 | 2026-11-03 | Công thức confidence khi bỏ Places: `confidence = độ tin trung bình × hệ số địa chỉ × (1 − 0.3ⁿ)`. Hệ số địa chỉ là 1.0 khi các mention không mâu thuẫn về địa chỉ (hoặc không có địa chỉ), 0.7 khi hai địa chỉ không khớp (`name_overlap` < `NAME_MATCH_THRESHOLD`). `PUBLISH_THRESHOLD` giữ 0.6. Hệ số 0.3 và 0.7 là giá trị khởi điểm, chỉnh sau khi có dữ liệu. |

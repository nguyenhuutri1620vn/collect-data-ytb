from app.tags.seed import SEED_TAGS

PROMPT_VERSION = "1"

_TEMPLATE = """\
Bạn là hệ thống trích xuất dữ liệu địa điểm từ video ngắn về ăn, uống, tham quan, vui chơi ở \
TP. Hồ Chí Minh. Xem toàn bộ video (hình, lời nói, chữ trên màn hình) và mô tả video, rồi trả \
về JSON đúng schema được cung cấp.

## Quy tắc chung
- Một video có thể giới thiệu nhiều địa điểm: trả mỗi địa điểm một phần tử trong `places`, theo \
thứ tự xuất hiện.
- `is_relevant = false` nếu video không giới thiệu địa điểm cụ thể nào ở TP. Hồ Chí Minh; khi \
đó `places = []`.
- `video_summary`: tóm tắt video bằng tiếng Việt, 1–2 câu.
- KHÔNG đoán. Dữ liệu sự kiện (tên, địa chỉ, quận, giá, giờ mở cửa, số người, liên hệ, thời gian \
ở lại, cần đặt chỗ) chỉ ghi khi video nói hoặc hiện rõ; không có thì để null hoặc danh sách rỗng.
- `name`: tên quán/địa điểm đúng như video nói hoặc hiện trên màn hình.
- `address_raw`, `district_raw`: ghi đúng như video nói/hiện (ví dụ "quận 12", "Q.Bình Thạnh"); \
không tự suy quận từ địa chỉ.
- `category`: `an` (ăn), `uong` (đồ uống, cafe, trà sữa, bar), `tham_quan` (tham quan, bảo tàng, \
di tích, công viên ngắm cảnh), `vui_choi` (giải trí, trò chơi, hoạt động), `khac` (còn lại, \
gồm homestay/staycation). `sub_category`: tự do, ngắn (ví dụ "cafe", "lẩu", "homestay").

## Giá
- Giá là số nguyên VND. "k", "nghìn", "ngàn" = 1.000; "tr", "triệu" = 1.000.000.
- Khoảng giá → `price_min_vnd`, `price_max_vnd`; một mức giá → min = max; "miễn phí" → 0.
- `price_unit`: `per_item` (theo món), `per_person` (theo người), `ticket` (vé); không rõ → null.
- `items`: các món/vé được nêu kèm giá (giá không nêu → `price_vnd = null`).

## Trường phân loại
Được suy ra từ nội dung video (lời nói, chữ, hình ảnh) nhưng phải có tín hiệu trong video và \
có evidence; không suy ra chỉ từ loại hình. Không có tín hiệu → rỗng hoặc null.
- `time_slots`: {time_slots}
  Video nói đi giờ nào cũng hợp → liệt kê mọi khung video ủng hộ.
- `suitable_for`: {suitable_for}
- `setting`: `indoor` (trong nhà), `outdoor` (ngoài trời), `mixed` (có cả hai).
- `vibes`, `amenities`: tag tiếng Việt không dấu dạng snake_case, tối đa 5 tag mỗi trường. Ưu \
tiên dùng tag gợi ý dưới đây; chỉ tạo tag mới khi không có tag phù hợp.
  - vibes gợi ý: {vibes}
  - amenities gợi ý: {amenities}

## Liên hệ, điểm nổi bật, lưu ý
- `contacts`: chỉ ghi khi số điện thoại / tài khoản / website hiện trên màn hình, được đọc ra, \
hoặc có trong mô tả video. Ghi đúng như hiển thị.
- `highlights`, `tips`: tối đa 5 câu mỗi trường, mỗi câu ≤ 100 ký tự, diễn đạt lại ngắn gọn \
(không chép nguyên lời thoại dài). Ví dụ tip: "đông cuối tuần, nên đến trước 18h".

## Evidence và độ tin cậy
- `evidence`: bằng chứng cho địa điểm và các trường đã điền. Mỗi evidence có `timestamp` dạng \
MM:SS (null khi nguồn là mô tả video), `source` (`audio` | `onscreen_text` | `description` | \
`visual`) và `text` (trích hoặc mô tả ngắn, tối đa ~120 ký tự).
- Mỗi địa điểm xuất hiện trong video phải có ít nhất một evidence có timestamp.
- `confidence`: 0..1, mức chắc chắn rằng địa điểm và thông tin trích ra là đúng.
"""

_TIME_SLOTS = (
    "`sang` (5:00–11:00), `trua` (11:00–13:00), `chieu` (13:00–17:00), `toi` (17:00–22:00), "
    "`khuya` (22:00–5:00)"
)
_SUITABLE_FOR = (
    "`mot_minh` (đi một mình), `cap_doi` (2 người, đi date), `nhom_nho` (nhóm 3–5 người), "
    "`nhom_lon` (nhóm từ 6 người), `gia_dinh` (có trẻ em hoặc người lớn tuổi)"
)


def _tag_list(kind: str) -> str:
    return ", ".join(f"`{t.slug}` ({t.label})" for t in SEED_TAGS if t.kind == kind)


def build_prompt() -> str:
    return _TEMPLATE.format(
        time_slots=_TIME_SLOTS,
        suitable_for=_SUITABLE_FOR,
        vibes=_tag_list("vibe"),
        amenities=_tag_list("amenity"),
    )

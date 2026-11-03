# Output contract (`output` schema)

Written for: developers of the web app that reads this database.

- **Version:** `OUTPUT_VERSION=1` (stored in `COMMENT ON SCHEMA output`).
- **Access:** role `output_reader` (SELECT only). The login role and its password are created outside
  the code. The views run with the owner's rights, so the reader cannot read the base tables.
- **Change rules (FR-10.4):** adding a column or view is compatible. Dropping, renaming, or changing
  the type of a column is breaking: bump `OUTPUT_VERSION` and announce it to the web app first.

## Views

### `output.places`
One row per place with `status = 'published'`.

| Column | Meaning |
|---|---|
| `id` | Place id (stable within this database) |
| `name`, `name_normalized`, `address_raw` | Name and address as the videos say them |
| `legacy_district`, `legacy_sub_area`, `ward` | Pre-2025 district, sub-area, and new ward (`ward` is null for now) |
| `category`, `sub_category` | `an`, `uong`, `tham_quan`, `vui_choi`, `khac` |
| `items` | `[{name, mentions, price_vnd}]` |
| `price_min_vnd`, `price_max_vnd`, `price_unit` | VND; unit is `per_item`, `per_person`, `ticket`, or null |
| `opening_hours_raw` | Opening hours as the video says them |
| `time_slots`, `time_slot_counts` | Slots that appear in at least 30% of mentions with that field, and counts |
| `vibes`, `vibe_counts`, `amenities`, `amenity_counts` | Open tags (snake_case slugs), same rule |
| `suitable_for`, `suitable_for_counts` | Group types, same rule |
| `setting` | `indoor`, `outdoor`, `mixed`, or null |
| `group_size_min`, `group_size_max` | Median of mentions |
| `visit_duration_min_minutes`, `visit_duration_max_minutes` | Median of mentions |
| `reservation_required` | Most common value, or null on a tie |
| `contacts` | `[{type, value, mentions}]`, de-duplicated after normalization |
| `highlights`, `tips` | `[{text, video_id}]`, at most 10 each |
| `mention_count`, `source_video_ids` | How many mentions and from which videos |
| `confidence` | 0 to 1, see D26 |
| `updated_at` | Last time the place was rebuilt |

### `output.place_mentions`
One row per mention of a published place.

`place_id`, `video_id`, `name_raw`, `address_raw`, `district_raw`, `legacy_district`, price fields,
`time_slots`, `vibes`, `amenities`, `suitable_for`, `setting`, `contacts`, `highlights`, `tips`,
`evidence` (`[{timestamp, source, text}]`), `confidence`.

### `output.place_media`
One row per (place, video, evidence timestamp).

`place_id`, `video_id`, `video_url` (`https://www.youtube.com/watch?v=<id>&t=<seconds>`),
`thumbnail_url` (`https://i.ytimg.com/vi/<id>/hqdefault.jpg`).
Only videos with `availability = 'available'`. There is no title column: titles are not stored (C10).

### `output.tags`
`kind`, `slug`, `label`, `mention_count`. Use it to display and translate tags.

### `output.legacy_districts`
`legacy_district`, `legacy_sub_area` (null for most rows), `target_places`. No polygons (C11).

## Not in the output

`google_place_id`, `maps_url`, `closed_permanently` (dropped by D25); `raw_output`; quota and error
fields; `status`; draft places and places marked hidden or out_of_scope.

## Confidence and publishing

`confidence = mean mention confidence × address factor × (1 − 0.3^n)` (D26). The address factor is 1.0
when the mentions agree on an address, and 0.7 when two of them name different addresses. A place is
published when it has a legacy district and `confidence >= 0.6`. These values are starting points and
will be tuned with real labels.

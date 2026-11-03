import asyncio
import json
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.core.quota import QuotaExceeded
from app.eval.candidates import (
    PRESETS,
    build_queries,
    collect,
    estimate_units,
    gold_video_ids,
    load_previous,
    months_before,
    open_slots,
    plan_exclusions,
    preset_queries,
)
from app.geo.districts import LEGACY_DISTRICTS
from app.sources.youtube import API_BASE, YouTubeClient, parse_iso_duration

KEY = "test-youtube-key"
AFTER = datetime(2025, 5, 3, tzinfo=UTC)


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> YouTubeClient:
    http = httpx.AsyncClient(
        base_url=API_BASE, headers={"X-Goog-Api-Key": KEY}, transport=httpx.MockTransport(handler)
    )
    return YouTubeClient(http)


@pytest.mark.parametrize(
    ("value", "seconds"),
    [("PT1M30S", 90), ("PT45S", 45), ("PT1H", 3600), ("PT0S", 0), ("P1D", None), ("", None)],
)
def test_parse_iso_duration(value: str, seconds: int | None) -> None:
    assert parse_iso_duration(value) == seconds


async def test_search_sends_key_in_header_not_in_url() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"items": [{"id": {"videoId": "aaaaaaaaaaa"}}]})

    ids = await _client(handler).search_video_ids("đi chơi Quận 1", published_after=AFTER)

    assert ids == ["aaaaaaaaaaa"]
    (request,) = seen
    assert request.headers["X-Goog-Api-Key"] == KEY
    assert KEY not in str(request.url)
    assert request.url.params["videoDuration"] == "short"
    assert request.url.params["publishedAfter"] == "2025-05-03T00:00:00Z"


async def test_durations_are_fetched_in_chunks_of_50() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        ids = request.url.params["id"].split(",")
        calls.append(len(ids))
        items = [{"id": i, "contentDetails": {"duration": "PT2M"}} for i in ids]
        return httpx.Response(200, json={"items": items})

    video_ids = [f"{n:011d}" for n in range(60)]
    durations = await _client(handler).durations(video_ids)

    assert calls == [50, 10]
    assert len(durations) == 60 and set(durations.values()) == {120}


async def test_collect_keeps_short_videos_capped_per_district_and_deduplicated() -> None:
    # Search results per query; "a" appears in two districts and must be kept once.
    results = {
        "q1": ["a" * 11, "b" * 11, "c" * 11, "d" * 11],
        "q2": ["a" * 11, "e" * 11],
    }
    durations = {"a" * 11: 60, "b" * 11: 400, "c" * 11: 90, "d" * 11: 30, "e" * 11: 200}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search"):
            return httpx.Response(
                200,
                json={"items": [{"id": {"videoId": v}} for v in results[request.url.params["q"]]]},
            )
        ids = request.url.params["id"].split(",")
        items = [{"id": i, "contentDetails": {"duration": f"PT{durations[i]}S"}} for i in ids]
        return httpx.Response(200, json={"items": items})

    spent: list[int] = []

    async def spend(units: int) -> None:
        spent.append(units)

    queries = [("Quận 1", "q1"), ("Quận 3", "q2")]
    candidates, stopped = await collect(
        _client(handler),
        queries,
        published_after=AFTER,
        max_seconds=300,
        needed={"Quận 1": 2, "Quận 3": 2},
        exclude=set(),
        max_results=25,
        spend=spend,
    )

    assert stopped is None
    # "b" is too long; "d" is cut by the per-district cap; "a" is kept once, under Quận 1.
    assert [(c.video_id[0], c.district) for c in candidates] == [
        ("a", "Quận 1"),
        ("c", "Quận 1"),
        ("e", "Quận 3"),
    ]
    # one search + one detail call per query that still had ids to check
    assert spent == [100, 1, 100, 1]


async def test_collect_keeps_partial_results_when_quota_runs_out() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={"items": [{"id": {"videoId": "a" * 11}}]})
        return httpx.Response(
            200, json={"items": [{"id": "a" * 11, "contentDetails": {"duration": "PT1M"}}]}
        )

    budget = [101]  # first search fits, second does not, the 1-unit detail call still fits

    async def spend(units: int) -> None:
        if units > budget[0]:
            raise QuotaExceeded("youtube.units: exhausted")
        budget[0] -= units

    candidates, stopped = await collect(
        _client(handler),
        [("Quận 1", "q1"), ("Quận 3", "q2")],
        published_after=AFTER,
        max_seconds=300,
        needed={"Quận 1": 3, "Quận 3": 3},
        exclude=set(),
        max_results=25,
        spend=spend,
    )

    assert stopped is not None and stopped.startswith("quota:")
    assert [c.district for c in candidates] == ["Quận 1"]


def test_build_queries_uses_place_name_without_tp_prefix() -> None:
    queries = build_queries(["TP Thủ Đức", "Quận 12"], ["đi chơi {place}", "ăn {place}"])
    assert queries == [
        ("TP Thủ Đức", "đi chơi Thủ Đức"),
        ("TP Thủ Đức", "ăn Thủ Đức"),
        ("Quận 12", "đi chơi Quận 12"),
        ("Quận 12", "ăn Quận 12"),
    ]


def test_months_before_handles_year_boundary_and_short_months() -> None:
    assert months_before(datetime(2026, 11, 3, tzinfo=UTC), 18) == datetime(2025, 5, 3, tzinfo=UTC)
    assert months_before(datetime(2026, 3, 31, tzinfo=UTC), 1) == datetime(2026, 2, 28, tzinfo=UTC)


def test_estimate_units_counts_searches_and_detail_calls() -> None:
    assert estimate_units(22, 25) == 22 * 100 + 11  # 550 ids -> 11 videos.list calls
    assert estimate_units(0, 25) == 0


def async_run(coro: Coroutine[Any, Any, Any]) -> Any:
    return asyncio.run(coro)


def _write_previous(tmp_path: Path, candidates: list[dict]) -> None:
    (tmp_path / "20260101T000000Z_candidates.json").write_text(
        json.dumps({"candidates": candidates}), encoding="utf-8"
    )


def test_excluded_videos_are_never_searched_into_candidates() -> None:
    durations_called: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search"):
            return httpx.Response(
                200, json={"items": [{"id": {"videoId": "a" * 11}}, {"id": {"videoId": "b" * 11}}]}
            )
        ids = request.url.params["id"].split(",")
        durations_called.append(ids)
        return httpx.Response(
            200, json={"items": [{"id": i, "contentDetails": {"duration": "PT1M"}} for i in ids]}
        )

    async def spend(units: int) -> None:
        return None

    candidates, stopped = async_run(
        collect(
            _client(handler),
            [("Quận 1", "q1")],
            published_after=AFTER,
            max_seconds=300,
            max_results=25,
            needed={"Quận 1": 3},
            exclude={"a" * 11},
            spend=spend,
        )
    )
    assert stopped is None
    assert [c.video_id for c in candidates] == ["b" * 11]
    assert durations_called == [["b" * 11]]  # the excluded id is not even looked up


def test_district_without_slots_is_not_searched() -> None:
    searched: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search"):
            searched.append(request.url.params["q"])
            return httpx.Response(200, json={"items": []})
        return httpx.Response(200, json={"items": []})

    async def spend(units: int) -> None:
        return None

    async_run(
        collect(
            _client(handler),
            [("Quận 1", "q1"), ("Quận 3", "q2")],
            published_after=AFTER,
            max_seconds=300,
            max_results=25,
            needed={"Quận 3": 1},
            exclude=set(),
            spend=spend,
        )
    )
    assert searched == ["q2"]


def test_plan_exclusions_and_open_slots_track_pending_and_labeled(tmp_path: Path) -> None:
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    (gold_dir / ("g" * 11 + ".json")).write_text("{}", encoding="utf-8")
    previous = [
        {"video_id": "p" * 11, "district": "Quận 1"},
        {"video_id": "q" * 11, "district": "Quận 1"},
        {"video_id": "g" * 11, "district": "Quận 3"},  # already labeled: not pending
    ]

    exclusions = plan_exclusions(["d" * 11], gold_video_ids(gold_dir), previous)

    assert exclusions.video_ids == {"d" * 11, "g" * 11, "p" * 11, "q" * 11}
    assert exclusions.pending == {"Quận 1": 2}
    # Quận 1 is full (2 pending of 2); Quận 3 is open with all its slots.
    assert open_slots(["Quận 1", "Quận 3"], 2, exclusions.pending) == {"Quận 3": 2}


def test_load_previous_reads_all_earlier_runs(tmp_path: Path) -> None:
    assert load_previous(tmp_path / "missing") == []
    _write_previous(tmp_path, [{"video_id": "a" * 11, "district": "Quận 1"}])
    assert [c["video_id"] for c in load_previous(tmp_path)] == ["a" * 11]


def test_extra_preset_limits_nightlife_and_landmarks_to_their_districts() -> None:
    queries = preset_queries(PRESETS["extra"], ["Quận 1", "Củ Chi", "Quận 3"])
    assert {d for d, _ in queries} == {"Quận 1", "Quận 3"}  # Củ Chi is in neither group
    assert ("Quận 1", "dinh độc lập Quận 1") in queries
    assert ("Quận 3", "rooftop Quận 3") in queries
    assert len(preset_queries(PRESETS["extra"], list(LEGACY_DISTRICTS))) == 8 * 3 + 2 * 2


def test_v2_preset_covers_every_district_with_food_drink_and_checkin_terms() -> None:
    queries = preset_queries(PRESETS["v2"], list(LEGACY_DISTRICTS))
    assert len(queries) == 22 * 3
    assert ("Quận 1", "quán ăn ngon Quận 1 Sài Gòn") in queries
    assert all("Sài Gòn" in q for _, q in queries)

"""Find candidate short videos for the gold set by keyword search, per legacy district (FR-8.1).

    python -m app.eval.candidates --dry-run            # plan and quota estimate, no API calls
    python -m app.eval.candidates [--district "Quận 12" ...] [--template "quán ăn {place}" ...]

Each search costs YouTube quota (search.list = 100 units). Usage goes through the same
QuotaGuard as the rest of the pipeline. Only video ids and durations are kept (C10): titles are
not stored, so open the URL to check a candidate before labeling it.

Avoiding repeat work:
- Videos already in the `videos` table, in `eval/gold/`, or in earlier candidate files are never
  picked again (no re-analysis, no re-labeling).
- A district that already has `--per-district` candidates waiting for labels is skipped. Label
  them (move them into `eval/gold/`) and the district opens up again.
- Within a run, a district's remaining queries are skipped once it is full.
"""

import argparse
import asyncio
import json
import math
import sys
from collections import Counter
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.db import create_engine
from app.core.logging import configure_logging
from app.core.quota import QuotaExceeded, add_usage, ensure_quota, quota_day
from app.geo.districts import LEGACY_DISTRICTS
from app.models import Video
from app.sources.youtube import SEARCH_UNITS, VIDEOS_UNITS, YouTubeClient, canonical_url

# One template per category the gold set must cover: an, uong, tham_quan/vui_choi.
DEFAULT_TEMPLATES: tuple[str, ...] = (
    "đi chơi {place}",
    "quán ăn ngon {place}",
    "quán cafe {place}",
)
# Day 2 (extra): nightlife where it exists, landmarks only in the districts that have them.
EXTRA_TEMPLATES: tuple[str, ...] = (
    "rooftop {place}",
    "quán bar sôi động {place}",
    "quán bar yên tĩnh trong hẻm {place}",
)
NIGHTLIFE_DISTRICTS: tuple[str, ...] = (
    "Quận 1",
    "Quận 3",
    "Quận 4",
    "Quận 7",
    "Quận 10",
    "Bình Thạnh",
    "Phú Nhuận",
    "Tân Bình",
)
# v3: different angle from v2 (vlog, outdoor, sightseeing) to reach videos v2 did not return.
V3_TEMPLATES: tuple[str, ...] = (
    "vlog ăn uống {place} Sài Gòn",
    "hoạt động ngoài trời {place} Sài Gòn",
    "điểm tham quan {place} Sài Gòn",
)
LANDMARK_TEMPLATES: tuple[str, ...] = (
    "dinh độc lập {place}",
    "bảo tàng chứng tích chiến tranh {place}",
)
LANDMARK_DISTRICTS: tuple[str, ...] = ("Quận 1", "Quận 3")
# v2: food, drink and check-in terms plus "Sài Gòn" so "Quận 1" means HCMC, not another city.
V2_TEMPLATES: tuple[str, ...] = (
    "quán ăn ngon {place} Sài Gòn",
    "quán cafe bar {place} Sài Gòn",
    "địa điểm check-in {place} Sài Gòn",
)

# A preset is a list of (districts, templates) groups. Day 1 and day 2 run separately because
# the YouTube quota resets daily; the combined cost is more than one day's budget.
PRESETS: dict[str, tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]] = {
    "base": ((tuple(LEGACY_DISTRICTS), DEFAULT_TEMPLATES),),
    "v2": ((tuple(LEGACY_DISTRICTS), V2_TEMPLATES),),
    "v3": ((tuple(LEGACY_DISTRICTS), V3_TEMPLATES),),
    "extra": (
        (NIGHTLIFE_DISTRICTS, EXTRA_TEMPLATES),
        (LANDMARK_DISTRICTS, LANDMARK_TEMPLATES),
    ),
}
_VIDEOS_PER_CALL = 50

Spend = Callable[[int], Awaitable[None]]


@dataclass(frozen=True)
class Candidate:
    video_id: str
    district: str
    query: str
    duration_seconds: int


@dataclass
class Exclusions:
    video_ids: set[str] = field(default_factory=set)  # never pick these again
    pending: dict[str, int] = field(default_factory=dict)  # district -> unlabeled candidates


def place_name(district: str) -> str:
    """Search-friendly name: "TP Thủ Đức" -> "Thủ Đức"."""
    return district.removeprefix("TP ")


def build_queries(districts: Sequence[str], templates: Sequence[str]) -> list[tuple[str, str]]:
    return [(d, t.format(place=place_name(d))) for d in districts for t in templates]


def preset_queries(
    groups: Sequence[tuple[Sequence[str], Sequence[str]]], districts: Sequence[str]
) -> list[tuple[str, str]]:
    """Queries for each group, limited to the requested districts."""
    return [
        pair
        for group_districts, templates in groups
        for pair in build_queries([d for d in group_districts if d in districts], templates)
    ]


def months_before(now: datetime, months: int) -> datetime:
    index = now.year * 12 + (now.month - 1) - months
    year, month0 = divmod(index, 12)
    return now.replace(year=year, month=month0 + 1, day=min(now.day, 28))


def estimate_units(n_queries: int, max_results: int) -> int:
    detail_calls = math.ceil(n_queries * max_results / _VIDEOS_PER_CALL)
    return n_queries * SEARCH_UNITS + detail_calls * VIDEOS_UNITS


def load_previous(candidates_dir: Path) -> list[dict]:
    """Candidates from every earlier run (eval/candidates/*_candidates.json)."""
    previous: list[dict] = []
    if candidates_dir.exists():
        for path in sorted(candidates_dir.glob("*_candidates.json")):
            previous.extend(json.loads(path.read_text(encoding="utf-8")).get("candidates", []))
    return previous


def gold_video_ids(gold_dir: Path) -> set[str]:
    return {p.stem for p in gold_dir.glob("*.json")} if gold_dir.exists() else set()


def plan_exclusions(db_ids: Iterable[str], gold: set[str], previous: list[dict]) -> Exclusions:
    """Videos to skip, and per-district counts of candidates still waiting for labels."""
    previous_ids = {c["video_id"] for c in previous}
    pending = Counter(c["district"] for c in previous if c["video_id"] not in gold)
    return Exclusions(
        video_ids=set(db_ids) | gold | previous_ids,
        pending=dict(pending),
    )


def open_slots(
    districts: Sequence[str], per_district: int, pending: dict[str, int]
) -> dict[str, int]:
    """How many new candidates each district still needs. Full districts are left out."""
    slots = {d: per_district - pending.get(d, 0) for d in districts}
    return {d: n for d, n in slots.items() if n > 0}


async def collect(
    client: YouTubeClient,
    queries: Sequence[tuple[str, str]],
    *,
    published_after: datetime,
    max_seconds: int,
    max_results: int,
    needed: dict[str, int],
    exclude: set[str],
    spend: Spend,
) -> tuple[list[Candidate], str | None]:
    """Search query by query until each district has `needed` short videos.

    Durations are checked right after each search, so a district that is already full does not
    cost any further searches. Returns (candidates, stopped); if quota runs out mid-way, what was
    found so far is kept.
    """
    candidates: list[Candidate] = []
    picked: Counter[str] = Counter()
    seen = set(exclude)
    for district, query in queries:
        if picked[district] >= needed.get(district, 0):
            continue
        try:
            await spend(SEARCH_UNITS)
        except QuotaExceeded as exc:
            return candidates, f"quota: {exc}"
        try:
            found = await client.search_video_ids(
                query, published_after=published_after, max_results=max_results
            )
        except httpx.HTTPStatusError as exc:  # e.g. Google refuses once its own quota is gone
            return candidates, f"youtube api: HTTP {exc.response.status_code}"
        ids = list(dict.fromkeys(v for v in found if v not in seen))
        if not ids:
            continue
        try:
            await spend(VIDEOS_UNITS * math.ceil(len(ids) / _VIDEOS_PER_CALL))
        except QuotaExceeded as exc:
            return candidates, f"quota: {exc}"
        durations = await client.durations(ids)
        for video_id in ids:
            if picked[district] >= needed.get(district, 0):
                break  # left unseen: another district may still use it
            seen.add(video_id)
            seconds = durations.get(video_id)
            if seconds is None or not 0 < seconds <= max_seconds:
                continue
            picked[district] += 1
            candidates.append(Candidate(video_id, district, query, seconds))
    return candidates, None


def _write(candidates: list[Candidate], report: dict, out_dir: Path, now: datetime) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{now:%Y%m%dT%H%M%SZ}_candidates.json"
    body = {
        **report,
        "candidates": [{**asdict(c), "url": canonical_url(c.video_id)} for c in candidates],
    }
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


async def _db_video_ids(factory: async_sessionmaker) -> set[str]:
    async with factory() as session:
        rows = await session.scalars(select(Video.video_id).where(Video.source == "youtube"))
        return set(rows.all())


async def _run(args: argparse.Namespace) -> int:
    settings: Settings = get_settings()
    districts = args.district or list(LEGACY_DISTRICTS)
    unknown = [d for d in districts if d not in LEGACY_DISTRICTS]
    if unknown:
        print(json.dumps({"error": f"unknown district(s): {unknown}"}, ensure_ascii=False))
        return 1
    if args.template or args.district:
        groups = [(tuple(districts), tuple(args.template or DEFAULT_TEMPLATES))]
    else:
        groups = list(PRESETS[args.preset])
    now = datetime.now(UTC)
    published_after = months_before(now, settings.published_after_months)

    engine = create_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yt: YouTubeClient | None = None
    try:
        exclusions = plan_exclusions(
            await _db_video_ids(factory),
            gold_video_ids(args.gold),
            load_previous(args.out),
        )
        pending = {} if args.ignore_pending else exclusions.pending
        needed = open_slots(districts, args.per_district, pending)
        queries = [(d, q) for d, q in preset_queries(groups, districts) if d in needed]
        plan = {
            "queries": [q for _, q in queries],
            "skipped_districts": [d for d in districts if d not in needed],
            "pending_per_district": exclusions.pending,
            "excluded_video_ids": len(exclusions.video_ids),
            "published_after": published_after.isoformat(),
            "max_seconds": settings.max_video_seconds,
            "per_district": args.per_district,
            "needed_per_district": needed,
            "estimated_units": estimate_units(len(queries), args.max_results),
            "daily_units_limit": settings.youtube_daily_units,
        }
        print(json.dumps({"plan": plan}, ensure_ascii=False, indent=2))
        if args.dry_run or not queries:
            return 0

        yt = YouTubeClient.from_settings(settings)

        async def spend(units: int) -> None:
            async with factory() as session:
                day = quota_day(datetime.now(UTC), settings.quota_timezone)
                await ensure_quota(
                    session,
                    day,
                    "youtube",
                    "units",
                    limit=settings.youtube_daily_units,
                    safety_ratio=settings.quota_safety_ratio,
                )
                await add_usage(session, day, "youtube", "units", units)
                await session.commit()

        candidates, stopped = await collect(
            yt,
            queries,
            published_after=published_after,
            max_seconds=settings.max_video_seconds,
            max_results=args.max_results,
            needed=needed,
            exclude=exclusions.video_ids,
            spend=spend,
        )
    finally:
        if yt is not None:
            await yt.aclose()
        await engine.dispose()

    report = {"generated_at": now.isoformat(), "plan": plan, "stopped": stopped}
    path = _write(candidates, report, args.out, now)
    for c in candidates:
        print(f"{c.district:<14} {c.duration_seconds:>4}s  {canonical_url(c.video_id)}")
    print(f"\n{len(candidates)} candidate(s) -> {path}")
    if stopped:
        print(f"STOPPED: {stopped}")
    return 2 if stopped else 0


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(prog="python -m app.eval.candidates")
    parser.add_argument("--district", action="append", help="repeat; default: all 22 districts")
    parser.add_argument(
        "--template",
        action="append",
        help="search template with {place}, repeat; default: đi chơi / quán ăn ngon / quán cafe",
    )
    parser.add_argument("--preset", choices=sorted(PRESETS), default="base")
    parser.add_argument("--per-district", type=int, default=3)
    parser.add_argument("--max-results", type=int, default=25, help="per search, max 50")
    parser.add_argument(
        "--ignore-pending",
        action="store_true",
        help="ignore unlabeled candidates when counting a district as full",
    )
    parser.add_argument("--gold", type=Path, default=Path("eval/gold"))
    parser.add_argument("--out", type=Path, default=Path("eval/candidates"))
    parser.add_argument("--dry-run", action="store_true", help="print the plan, call nothing")
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())

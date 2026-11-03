"""Gold set helper: status, next candidate to label, and skeleton files (FR-8.1).

    python -m app.eval.gold status        # per-file state, progress, district spread
    python -m app.eval.gold next [--open] # next candidate with no gold file (--open: browser)
    python -m app.eval.gold new <video_id> # write a skeleton marked TODO

Labels are still written by hand. A skeleton carries TODO_MARKER in video_summary; app.eval
refuses to run while any gold file is a skeleton or invalid.
"""

import argparse
import json
import sys
import webbrowser
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from app.geo.aliases import resolve_legacy_district
from app.schemas.extraction import VideoExtraction
from app.sources.youtube import canonical_url

TODO_MARKER = "TODO"
TARGET_LABELED = 50  # FR-8.1: about 50 hand-labeled videos


def skeleton() -> dict:
    return {
        "is_relevant": False,
        "video_summary": TODO_MARKER,
        "places": [],
    }


def file_state(path: Path) -> tuple[str, str | None]:
    """("ok" | "todo" | "invalid", message)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return "invalid", f"not JSON: {exc}"
    if isinstance(data, dict) and data.get("video_summary") == TODO_MARKER:
        return "todo", None
    try:
        VideoExtraction.model_validate(data)
    except ValidationError as exc:
        return "invalid", str(exc).splitlines()[0]
    return "ok", None


def gold_files(gold_dir: Path) -> list[Path]:
    return sorted(gold_dir.glob("*.json")) if gold_dir.exists() else []


def pending_candidates(candidates_dir: Path, gold_dir: Path) -> list[dict]:
    """Candidates from every earlier run that have no gold file yet, oldest run first."""
    have = {p.stem for p in gold_files(gold_dir)}
    seen: set[str] = set()
    pending: list[dict] = []
    if not candidates_dir.exists():
        return pending
    for path in sorted(candidates_dir.glob("*_candidates.json")):
        for c in json.loads(path.read_text(encoding="utf-8")).get("candidates", []):
            if c["video_id"] not in have and c["video_id"] not in seen:
                seen.add(c["video_id"])
                pending.append(c)
    return pending


def write_skeleton(gold_dir: Path, video_id: str) -> Path:
    path = gold_dir / f"{video_id}.json"
    if path.exists():
        raise FileExistsError(f"{path} already exists")
    gold_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(skeleton(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _status(gold_dir: Path) -> int:
    files = gold_files(gold_dir)
    states = {"ok": [], "todo": [], "invalid": []}
    districts: Counter[str] = Counter()
    for path in files:
        state, message = file_state(path)
        states[state].append(path.stem)
        if state == "invalid":
            print(f"INVALID {path.name}: {message}")
        if state == "ok":
            data = VideoExtraction.model_validate_json(path.read_text(encoding="utf-8"))
            for place in data.places:
                if (legacy := resolve_legacy_district(place.district_raw)) is not None:
                    districts[legacy] += 1
    for video_id in states["todo"]:
        print(f"TODO    {video_id}.json (still a skeleton)")
    print(
        f"\nlabeled ok: {len(states['ok'])} / target {TARGET_LABELED} · "
        f"todo: {len(states['todo'])} · invalid: {len(states['invalid'])}"
    )
    if districts:
        print(
            "places per legacy district: "
            + ", ".join(f"{d} {n}" for d, n in sorted(districts.items()))
        )
    return 0 if not states["invalid"] and not states["todo"] else 1


def _next(candidates_dir: Path, gold_dir: Path, open_browser: bool) -> int:
    pending = pending_candidates(candidates_dir, gold_dir)
    if not pending:
        print("no pending candidates")
        return 0
    c = pending[0]
    url = canonical_url(c["video_id"])
    print(f"{c['video_id']}  district={c['district']}  query={c['query']!r}\n{url}")
    print(f"({len(pending) - 1} more pending after this)")
    if open_browser:
        webbrowser.open(url)
    return 0


def _new(gold_dir: Path, video_id: str) -> int:
    try:
        path = write_skeleton(gold_dir, video_id)
    except FileExistsError as exc:
        print(str(exc))
        return 1
    print(f"created {path} (fill it in, then remove the TODO summary)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.eval.gold")
    parser.add_argument("--gold", type=Path, default=Path("eval/gold"))
    parser.add_argument("--candidates", type=Path, default=Path("eval/candidates"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    nxt = sub.add_parser("next")
    nxt.add_argument("--open", action="store_true", help="open the URL in a browser")
    new = sub.add_parser("new")
    new.add_argument("video_id")
    args = parser.parse_args(argv)
    if args.command == "status":
        return _status(args.gold)
    if args.command == "next":
        return _next(args.candidates, args.gold, args.open)
    return _new(args.gold, args.video_id)


if __name__ == "__main__":
    sys.exit(main())

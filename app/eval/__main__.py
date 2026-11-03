"""Run the Analysis eval against the gold set (costs real Gemini quota).

python -m app.eval [--gold eval/gold] [--reports eval/reports] [--threshold 0.8]
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.analysis.gemini import GeminiClient
from app.core.config import get_settings
from app.core.db import create_engine
from app.core.logging import configure_logging
from app.eval.runner import build_report, format_summary, load_gold, run_eval, write_report


async def _run(gold_dir: Path, reports_dir: Path, threshold: float | None) -> int:
    settings = get_settings()
    threshold = settings.name_match_threshold if threshold is None else threshold
    gold = load_gold(gold_dir)
    if not gold:
        print(json.dumps({"error": f"no gold files in {gold_dir}"}, ensure_ascii=False))
        return 1

    now = datetime.now(UTC)
    engine = create_engine(settings.database_url)
    try:
        run = await run_eval(
            gold,
            GeminiClient.from_settings(settings),
            async_sessionmaker(engine, expire_on_commit=False),
            settings,
            threshold=threshold,
            now=now,
        )
    finally:
        await engine.dispose()

    report = build_report(run, settings, threshold=threshold, now=now)
    path = write_report(report, reports_dir, now)
    print(format_summary(report))
    print(f"\nreport: {path}")
    return 2 if run.stopped else 0


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(prog="python -m app.eval")
    parser.add_argument("--gold", type=Path, default=Path("eval/gold"))
    parser.add_argument("--reports", type=Path, default=Path("eval/reports"))
    parser.add_argument(
        "--threshold", type=float, default=None, help="default NAME_MATCH_THRESHOLD"
    )
    args = parser.parse_args(argv)
    return asyncio.run(_run(args.gold, args.reports, args.threshold))


if __name__ == "__main__":
    sys.exit(main())

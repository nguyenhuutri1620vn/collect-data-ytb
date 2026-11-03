"""R8 eval runner: gold set -> Analysis -> metrics -> report (FR-8.2, FR-8.3)."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.analysis.gemini import VideoAnalyzer
from app.analysis.prompts import PROMPT_VERSION
from app.analysis.service import call_gemini
from app.core.config import Settings
from app.core.quota import QuotaExceeded
from app.eval.gold import file_state, gold_files
from app.eval.metrics import FIELDS, Counts, VideoScore, aggregate, score_video
from app.schemas.extraction import SCHEMA_VERSION, VideoExtraction
from app.sources.youtube import canonical_url

logger = logging.getLogger(__name__)


@dataclass
class GoldItem:
    video_id: str
    url: str
    label: VideoExtraction


def load_gold(gold_dir: Path) -> list[GoldItem]:
    """One file per video: eval/gold/<video_id>.json, in the VideoExtraction output format.

    Refuses to load while any file is a TODO skeleton or invalid: a half-labeled gold set
    would score the model against empty labels.
    """
    bad = [
        f"{p.name}: {msg or state}"
        for p in gold_files(gold_dir)
        for state, msg in [file_state(p)]
        if state != "ok"
    ]
    if bad:
        raise ValueError("gold set is not ready:\n" + "\n".join(bad))
    items: list[GoldItem] = []
    for path in gold_files(gold_dir):
        label = VideoExtraction.model_validate_json(path.read_text(encoding="utf-8"))
        items.append(GoldItem(path.stem, canonical_url(path.stem), label))
    return items


@dataclass
class EvalRun:
    scores: list[VideoScore]
    details: list[dict]
    errors: list[dict]
    invalid_outputs: int = 0
    stopped: str | None = None


async def run_eval(
    gold: list[GoldItem],
    analyzer: VideoAnalyzer,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    threshold: float,
    now: datetime,
) -> EvalRun:
    """Analyze every gold video (quota-guarded, usage committed per video) and score it."""
    run = EvalRun(scores=[], details=[], errors=[])
    for item in gold:
        async with session_factory() as session:
            try:
                result = await call_gemini(session, analyzer, item.url, settings, now)
            except QuotaExceeded as exc:
                run.stopped = f"quota: {exc}"
                break
            except Exception as exc:  # noqa: BLE001 - one bad video must not stop the eval
                logger.error("eval call failed", extra={"video_id": item.video_id})
                run.errors.append({"video_id": item.video_id, "error": repr(exc)[:500]})
                continue
            await session.commit()

        try:
            pred = VideoExtraction.model_validate_json(result.text)
        except ValidationError:
            # Counted as "no places, not relevant": a bad output costs recall, not silently skipped.
            run.invalid_outputs += 1
            pred = VideoExtraction(is_relevant=False, video_summary="", places=[])

        score = score_video(pred, item.label, threshold)
        run.scores.append(score)
        run.details.append(
            {
                "video_id": item.video_id,
                "relevant_pred": pred.is_relevant,
                "relevant_gold": item.label.is_relevant,
                "places_pred": [p.name for p in pred.places],
                "places_gold": [p.name for p in item.label.places],
            }
        )
    return run


def _metric_row(c: Counts) -> dict:
    return {
        "tp": c.tp,
        "fp": c.fp,
        "fn": c.fn,
        "precision": c.precision(),
        "recall": c.recall(),
        "hallucination_rate": c.hallucination_rate(),
        "hallucinated": c.hallucinated,
        "gold_empty": c.gold_empty,
    }


def build_report(run: EvalRun, settings: Settings, *, threshold: float, now: datetime) -> dict:
    totals = aggregate(run.scores)
    keys = ("name", *FIELDS)
    return {
        "generated_at": now.isoformat(),
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "model": settings.gemini_model,
        "media_resolution": settings.gemini_media_resolution,
        "name_match_threshold": threshold,
        "scored_videos": len(run.scores),
        "relevance_accuracy": (
            sum(s.relevant_ok for s in run.scores) / len(run.scores) if run.scores else None
        ),
        "invalid_outputs": run.invalid_outputs,
        "errors": run.errors,
        "stopped": run.stopped,
        "metrics": {k: _metric_row(totals.get(k, Counts())) for k in keys},
        "details": run.details,
    }


def write_report(report: dict, report_dir: Path, now: datetime) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    name = f"{now:%Y%m%dT%H%M%SZ}_p{report['prompt_version']}_{report['model']}.json"
    path = report_dir / name
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _fmt(value: float | None) -> str:
    return "  -  " if value is None else f"{value:6.1%}"


def format_summary(report: dict) -> str:
    lines = [
        f"prompt v{report['prompt_version']} · schema v{report['schema_version']} · "
        f"model {report['model']} · scored {report['scored_videos']} video(s)",
        f"relevance accuracy {_fmt(report['relevance_accuracy'])} · "
        f"invalid outputs {report['invalid_outputs']} · errors {len(report['errors'])}",
        "",
        f"{'field':<14}{'precision':>10}{'recall':>10}{'bịa':>10}{'tp':>6}{'fp':>6}{'fn':>6}",
    ]
    for key, row in report["metrics"].items():
        lines.append(
            f"{key:<14}{_fmt(row['precision']):>10}{_fmt(row['recall']):>10}"
            f"{_fmt(row['hallucination_rate']):>10}{row['tp']:>6}{row['fp']:>6}{row['fn']:>6}"
        )
    if report["stopped"]:
        lines.append(f"\nSTOPPED: {report['stopped']}")
    return "\n".join(lines)

"""Versioned extraction prompts. Changing a prompt requires a PROMPT_VERSION bump and an eval run,
except appending suggested tags at the end of the seed list (FR-9.3)."""

from app.analysis.prompts.v1 import PROMPT_VERSION, build_prompt

__all__ = ["PROMPT_VERSION", "build_prompt"]

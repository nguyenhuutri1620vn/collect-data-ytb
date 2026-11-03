# Analysis gold set (FR-8.1)

One JSON file per video: `<video_id>.json` (the YouTube id, e.g. `v1qXO2ykm8Q.json`).
The content is the same shape as the Gemini output: `VideoExtraction` in `app/schemas/extraction.py`.

- Labels are hand-written, once. Missing facts are `null` or `[]`, never guessed (hard rule 5).
- Aim for about 50 videos spread across districts and categories.
- Run with `uv run python -m app.eval --gold eval/gold` (uses real Gemini quota; ask first).
- Reports go to `eval/reports/`, one file per run, with `prompt_version` and `model`.

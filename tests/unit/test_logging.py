import io
import json
import logging

from app.core.logging import JsonFormatter


def test_json_formatter_includes_extra() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("test.json_formatter")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    logger.info("analyzed", extra={"video_id": "abc"})

    line = json.loads(stream.getvalue().strip())
    assert line["msg"] == "analyzed"
    assert line["video_id"] == "abc"
    assert line["level"] == "INFO"
    assert line["logger"] == "test.json_formatter"
    assert "ts" in line

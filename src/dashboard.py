"""Render a self-contained, offline dashboard from stored query results."""

import json
from pathlib import Path

from src.dashboard_review import review_details


def write_dashboard(path: Path, data: dict) -> None:
    template = (Path(__file__).resolve().parents[1] / "web/dashboard.html").read_text()
    # Source text is data, never markup. Escape the script terminator as well as
    # JavaScript line separators; the UI uses textContent for all source values.
    view = {**data, "review": review_details(data)}
    encoded = json.dumps(view, ensure_ascii=False).replace("<", "\\u003c")
    encoded = encoded.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    with path.open("x", encoding="utf-8") as handle:
        handle.write(template.replace("__DASHBOARD_DATA__", encoded))

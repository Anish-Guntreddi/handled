"""Routing guardrails. The colon-suffix action style (``/{id}:action``) is mangled by
uvicorn's HTTP parser for some action names, so all actions must use slash sub-paths.
This static check can't be caught by ASGITransport (it only manifests under uvicorn)."""

from __future__ import annotations

import re

from captureos.main import create_app


def test_no_colon_action_routes() -> None:
    app = create_app()
    offenders: list[str] = []
    for route in app.routes:
        path = getattr(route, "path", "")
        # Path converters like {rel_key:path} are legitimate; strip {...} then look for ':'.
        without_params = re.sub(r"\{[^}]*\}", "", path)
        if ":" in without_params:
            offenders.append(path)
    assert not offenders, (
        f"colon-action routes are unsafe under uvicorn/httptools; use slash sub-paths: {offenders}"
    )

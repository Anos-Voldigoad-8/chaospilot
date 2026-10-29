"""Phase 3 stack restart behaviour without a Docker daemon."""

from __future__ import annotations

import asyncio

from stack import StackController


def test_restart_reports_missing_docker(monkeypatch) -> None:
    monkeypatch.setattr("stack.shutil.which", lambda _name: None)
    result = asyncio.run(StackController().restart(resilient=True))

    assert result["ok"] is False
    assert result["resilient"] is True
    assert "docker CLI not found" in result["error"]

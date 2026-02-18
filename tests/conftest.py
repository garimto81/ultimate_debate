"""Shared test fixtures."""

import pytest


@pytest.fixture(autouse=True)
def debates_tmp_dir(tmp_path, monkeypatch):
    """Redirect all debate file creation to tmp directory.

    Prevents tests from creating garbage folders in .claude/debates/.
    """
    monkeypatch.setattr(
        "ultimate_debate.storage.context_manager.DebateContextManager.DEFAULT_DEBATES_DIR",
        tmp_path / "debates",
    )

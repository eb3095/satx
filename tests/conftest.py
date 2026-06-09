from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _redirect_satx_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("SATX_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("SATX_IMAGE_DIR", str(tmp_path / "images"))

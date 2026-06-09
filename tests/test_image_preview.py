from __future__ import annotations

from unittest.mock import patch

import numpy as np

from satx.ui.image_preview import ImagePreview, preview_backend_name


def test_preview_backend_name_on_darwin():
    with patch("satx.ui.image_preview.sys.platform", "darwin"):
        assert preview_backend_name() == "preview.app"


def test_image_preview_update_without_crash(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "satx.ui.image_preview.default_image_dir",
        lambda: tmp_path,
    )
    preview = ImagePreview("test")
    preview.update(np.zeros((4, 8), dtype=np.uint8), status="test")
    assert (tmp_path / ".live_preview.png").exists()
    preview.close()


def test_image_preview_uses_preview_on_darwin():
    with patch("satx.ui.image_preview.sys.platform", "darwin"):
        preview = ImagePreview("test")
        assert preview._backend.__class__.__name__ == "PreviewAppImagePreview"

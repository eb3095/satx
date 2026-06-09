from __future__ import annotations

import re
from pathlib import Path

from satx.log_writer import image_save_path


def test_image_save_path():
    path = image_save_path(
        Path("/tmp/satx-images"),
        "apt",
        "noaa-19",
        when=1717880400.0,
    )
    assert path.parent == Path("/tmp/satx-images")
    assert re.fullmatch(r"apt_noaa-19_\d{8}_\d{6}\.png", path.name)

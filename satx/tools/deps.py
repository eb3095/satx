"""Check optional Homebrew SDR tools (not installable via pip)."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class OptionalDep:
    name: str
    brew_package: str
    paths: tuple[str, ...]

    def available(self) -> bool:
        for candidate in self.paths:
            if "/" in candidate:
                if shutil.which(candidate):
                    return True
            elif shutil.which(candidate):
                return True
        return False


OPTIONAL_DEPS: tuple[OptionalDep, ...] = (
    OptionalDep(
        "hackrf_transfer",
        "hackrf",
        (
            "hackrf_transfer",
            "/opt/homebrew/bin/hackrf_transfer",
            "/usr/local/bin/hackrf_transfer",
        ),
    ),
    OptionalDep(
        "rtl_sdr",
        "rtl-sdr",
        ("rtl_sdr", "/opt/homebrew/bin/rtl_sdr", "/usr/local/bin/rtl_sdr"),
    ),
    OptionalDep(
        "rtl_433",
        "rtl_433",
        ("rtl_433", "/opt/homebrew/bin/rtl_433", "/usr/local/bin/rtl_433"),
    ),
    OptionalDep(
        "satdump",
        "satdump",
        ("satdump", "/opt/homebrew/bin/satdump", "/usr/local/bin/satdump"),
    ),
)


def missing_deps() -> List[OptionalDep]:
    return [dep for dep in OPTIONAL_DEPS if not dep.available()]


def brew_install_command(deps: List[OptionalDep] | None = None) -> str:
    packages = deps or missing_deps()
    if not packages:
        return "brew install hackrf rtl-sdr rtl_433 satdump"
    names = " ".join(dep.brew_package for dep in packages)
    return f"brew install {names}"


def format_missing_warning() -> str | None:
    missing = missing_deps()
    if not missing:
        return None
    names = ", ".join(dep.name for dep in missing)
    return (
        f"Optional tools not installed: {names}. "
        f"SatX Python deps do not include native SDR binaries — run: "
        f"{brew_install_command(missing)}"
    )

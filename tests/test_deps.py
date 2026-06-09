from __future__ import annotations

from satx.tools.deps import brew_install_command


def test_missing_deps_brew_command():
    cmd = brew_install_command()
    assert "brew install" in cmd


def test_format_missing_warning_when_all_present(monkeypatch):
    monkeypatch.setattr(
        "satx.tools.deps.shutil.which",
        lambda _path: "/usr/bin/fake",
    )
    from satx.tools import deps

    assert deps.format_missing_warning() is None


def test_format_missing_warning_lists_packages(monkeypatch):
    monkeypatch.setattr(
        "satx.tools.deps.shutil.which",
        lambda _path: None,
    )
    from satx.tools import deps

    warning = deps.format_missing_warning()
    assert warning is not None
    assert "rtl_433" in warning
    assert "satdump" in warning
    assert "brew install" in warning


def test_missing_deps_returns_unavailable():
    from satx.tools.deps import OptionalDep

    dep = OptionalDep("test", "test-pkg", ("nonexistent_binary_xyz",))
    assert dep.available() is False

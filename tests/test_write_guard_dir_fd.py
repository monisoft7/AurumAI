"""Regression tests for the repository write guard in conftest.py.

pytest's temp-dir cleanup deletes trees with ``os.rmdir(name, dir_fd=fd)``. The
guard used to resolve ``name`` against the working directory, so removing a temp
folder named ``data`` raised "write to protected repository ... forbidden" and
made ``pytest`` exit with status 1 even though every test passed.
"""
import os
import shutil

import pytest

import conftest as guard

linux_only = pytest.mark.skipif(not os.path.isdir("/proc/self/fd"), reason="needs /proc/self/fd")


def test_rmtree_of_temp_dirs_named_like_protected_roots(tmp_path):
    for name in ("data", "outputs", "runtime"):
        (tmp_path / "t" / name / "nested").mkdir(parents=True)
        (tmp_path / "t" / name / "nested" / "f.txt").write_text("x")
    shutil.rmtree(tmp_path / "t")  # must not trip the guard
    assert not (tmp_path / "t").exists()


@linux_only
def test_dir_fd_relative_name_is_anchored_to_its_directory(tmp_path):
    fd = os.open(tmp_path, os.O_RDONLY)
    try:
        resolved = guard._resolve_dir_fd_path("data", fd)
    finally:
        os.close(fd)
    assert resolved == os.path.join(os.path.realpath(tmp_path), "data")
    assert not guard._is_protected_repository_path(resolved)


@linux_only
def test_dir_fd_inside_protected_root_is_still_blocked():
    fd = os.open(guard.ROOT, os.O_RDONLY)
    try:
        resolved = guard._resolve_dir_fd_path("data", fd)
    finally:
        os.close(fd)
    assert guard._is_protected_repository_path(resolved)
    with pytest.raises(AssertionError, match="protected repository"):
        guard._guard_repository_writes("os.rmdir", ("data", -1))


def test_absolute_and_plain_paths_unchanged():
    assert guard._resolve_dir_fd_path("/tmp/x", 5) == "/tmp/x"
    assert guard._resolve_dir_fd_path("rel", None) == "rel"

from pathlib import Path
import ntpath
import os
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


_PROTECTED_REPOSITORY_ROOTS = tuple(ROOT / name for name in ("data", "outputs", "runtime"))


def _is_windows_device(path: str) -> bool:
    if os.name != "nt":
        return False
    path = path.replace("/", "\\")
    # Extended filesystem paths may name real files called NUL; never exempt them.
    if path.startswith("\\\\?\\"):
        return False
    if path.startswith("\\\\.\\"):
        path = path[4:]
        if "\\" in path:
            return False
    name = ntpath.basename(path).rstrip(" .").split(".", 1)[0].upper()
    return name in {"NUL", "CON", "PRN", "AUX", "CONIN$", "CONOUT$"} or name in {
        f"{prefix}{digit}" for prefix in ("COM", "LPT") for digit in "123456789¹²³"
    }


def _is_protected_repository_path(path) -> bool:
    if isinstance(path, int):
        return False  # File descriptors such as stdout are not filesystem paths.
    raw = os.fsdecode(path)
    # Recognize devices before Path.resolve; logging passes an absolute NUL path.
    if raw == os.devnull or _is_windows_device(raw):
        return False
    if os.name == "nt":
        raw = raw.replace("/", "\\")
        if raw.startswith(("\\\\?\\", "\\\\.\\")):
            raw = raw[4:]
            if raw.upper().startswith("UNC\\"):
                raw = "\\\\" + raw[4:]
    # Pure lexical normalization avoids Windows GetFullPathName mapping NUL
    # back to a device after an extended filesystem prefix was removed.
    lexical = Path(os.path.normpath(os.path.join(os.getcwd(), raw)))
    # Check lexical containment too, so replacing an in-tree symlink is denied.
    if any(lexical.is_relative_to(root) for root in _PROTECTED_REPOSITORY_ROOTS):
        return True
    resolved = lexical.resolve()
    return any(resolved.is_relative_to(root.resolve()) for root in _PROTECTED_REPOSITORY_ROOTS)


def _guard_repository_writes(event, args) -> None:
    paths = ()
    if event == "open":
        path, mode, flags = args
        writing = (isinstance(mode, str) and any(char in mode for char in "wax+")) or (
            isinstance(flags, int)
            and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        )
        if writing:
            paths = (path,)
    elif event in {"os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.utime", "os.truncate"}:
        paths = args[:1]
    elif event in {"os.rename", "os.link"}:
        paths = args[:2]
    elif event == "os.symlink":
        paths = args[1:2]
    if any(_is_protected_repository_path(path) for path in paths):
        raise AssertionError("write to protected repository data/outputs/runtime forbidden")


sys.addaudithook(_guard_repository_writes)


@pytest.fixture(autouse=True)
def _clear_global_extractors() -> None:
    from knowledge.features.engine import FeatureExtractionEngine
    FeatureExtractionEngine.clear_global()
    yield
    FeatureExtractionEngine.clear_global()


@pytest.fixture(autouse=True)
def _paper_hermetic_boundary(request, monkeypatch):
    """Paper tests may launch only the offline CLI's --help command."""
    if request.module.__name__.split(".")[-1] not in {
        "test_paper_trading", "test_paper_trading_automation", "test_paper_timing_audit",
        "test_paper_stage_validation", "test_runtime_output_isolation",
    }:
        return
    import os
    import socket
    import subprocess

    original_popen = subprocess.Popen

    def denied(*args, **kwargs):
        raise AssertionError("network or external side effect forbidden in paper tests")

    def guarded_popen(command, *args, **kwargs):
        if not (
            isinstance(command, (list, tuple)) and len(command) == 3
            and command[0] == sys.executable
            and Path(command[1]).name == "paper_trading.py"
            and command[2] == "--help" and not kwargs.get("shell")
        ):
            return denied()
        kwargs["env"] = {
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        return original_popen(command, *args, **kwargs)

    from orchestration.orchestrator import InstitutionalOrchestrator
    from connectors.gold_data_provider import GoldDataProvider

    monkeypatch.setattr(InstitutionalOrchestrator, "run_all", denied)
    monkeypatch.setattr(GoldDataProvider, "refresh", denied)
    monkeypatch.setattr(subprocess, "Popen", guarded_popen)
    monkeypatch.setattr(os, "system", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)

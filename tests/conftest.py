from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


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

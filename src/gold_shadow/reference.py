"""Run the pinned production analysis in a disposable checkout, without notifications."""
import io
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

BASE = "49a790b27e81bcc601bf772d712e6e039d2e7c50"


def reference_run(root):
    archive = subprocess.check_output(["git", "archive", "--format=zip", BASE], cwd=root)
    with tempfile.TemporaryDirectory(prefix="aurum-reference-") as tmp:
        directory = Path(tmp)
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            z.extractall(directory)
        env = dict(os.environ, PYTHONPATH=str(directory / "src"), PYTHONUTF8="1")
        for name in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "PAPER_LEDGER_TOKEN"):
            env.pop(name, None)
        # Use a new output root to exclude the historical outputs bundled in the repository.
        cfg = json.loads((directory / "runtime_config.json").read_bytes())
        cfg["output_base_dir"] = "paired_outputs"
        config = directory / "shadow_reference.json"
        config.write_text(json.dumps(cfg), encoding="utf-8")
        run = subprocess.run([sys.executable, "run.py", "--config", str(config)],
                             cwd=directory, env=env, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, timeout=480)
        paths = list((directory / "paired_outputs").glob("*/*/summary.json"))
        if run.returncode or len(paths) != 1:
            stages = json.loads(paths[0].read_bytes()).get("failed_stages", []) if paths else []
            raise RuntimeError(f"reference exited {run.returncode}, failed stages {stages}")
        path, = paths
        result = json.loads(path.read_bytes())
        if not result["success"]:
            raise ValueError("incomplete baseline computation")
        return {"commit": BASE, "run": result["pipeline_id"], "issued": result["timestamp"],
                "execution": result["execution_decision"], "research": result["research_decision"]}

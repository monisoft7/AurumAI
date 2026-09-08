"""Deterministic GitHub Actions orchestration for paper trading only.

The live path invokes the frozen strategy as a subprocess exactly once.  It
contains no broker integration.  Network delivery is isolated in
``send_telegram_message`` so tests can remain fully hermetic.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .ledger import (
    FRESH_STATUSES,
    HorizonNotComplete,
    PaperTradingError,
    _freshness_snapshot,
    evaluate_prediction,
)


STRATEGY_BASELINE = "2acd5adb7ab286c9cb362d5d94dcea0f58f83277"
HARNESS_BASELINE = "6ce0d848cd24167317f228ffd8772274e9a58166"
COHORT_ID = "xauusd-paper-baseline-2acd5ad"
REQUIRED_SECRETS = (
    "FRED_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "PAPER_LEDGER_TOKEN",
)
SENSITIVE_KEYS = {
    "api_key",
    "token",
    "secret",
    "password",
    "authorization",
    "credential",
}
TELEGRAM_LIMIT = 3500


class AutomationFailure(RuntimeError):
    """A safe-stop condition with a concise, user-facing stage and reason."""

    def __init__(
        self,
        stage: str,
        reason: str,
        *,
        error_type: str | None = None,
        missing_module: str | None = None,
    ) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason
        self.error_type = error_type
        self.missing_module = missing_module


@dataclass(frozen=True)
class ModePlan:
    mode: str
    run_pipeline: bool
    write_ledger: bool


def resolve_mode(event_name: str, dispatch_mode: str | None = None) -> str:
    if event_name == "schedule":
        return "live-paper"
    if event_name == "workflow_dispatch":
        selected = dispatch_mode or "dry-run"
        if selected not in {"dry-run", "live-paper"}:
            raise AutomationFailure("mode", "unsupported workflow mode")
        return selected
    raise AutomationFailure("mode", "unsupported workflow event")


def mode_plan(mode: str) -> ModePlan:
    if mode == "dry-run":
        return ModePlan(mode, run_pipeline=False, write_ledger=False)
    if mode == "live-paper":
        return ModePlan(mode, run_pipeline=True, write_ledger=True)
    raise AutomationFailure("mode", "unsupported workflow mode")


def deterministic_evaluation_id(market_date: str) -> str:
    try:
        parsed = dt.date.fromisoformat(market_date)
    except ValueError as exc:
        raise AutomationFailure("evaluation-id", "invalid market date") from exc
    return f"paper-{parsed.isoformat()}"


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AutomationFailure("artifact-validation", f"invalid {path.name}") from exc
    if not isinstance(value, dict):
        raise AutomationFailure("artifact-validation", f"invalid {path.name}")
    return value


def _canonical_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    path.write_text(rendered + "\n", encoding="utf-8")


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if check and result.returncode != 0:
        raise AutomationFailure("git", f"git {args[0]} failed")
    return result


def _head(root: Path) -> str:
    return _git(root, "rev-parse", "HEAD").stdout.strip().lower()


def secret_presence(environment: Mapping[str, str]) -> dict[str, str]:
    return {
        name: "PRESENT" if bool(environment.get(name)) else "MISSING"
        for name in REQUIRED_SECRETS
    }


def _secret_values(environment: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(
        value
        for name in REQUIRED_SECRETS
        if (value := environment.get(name))
    )


def sanitize_text(text: Any, secrets: Sequence[str] = ()) -> str:
    value = "" if text is None else str(text)
    for secret in secrets:
        if secret:
            value = value.replace(secret, "[REDACTED]")
    value = re.sub(
        r"(?i)(api[_-]?key|token|secret|password|authorization|credential)"
        r"\s*[:=]\s*\S+",
        r"\1=[REDACTED]",
        value,
    )
    value = " ".join(value.replace("\x00", "").split())
    return html.escape(value, quote=True)


def _message(lines: Sequence[str]) -> str:
    rendered = "\n".join(lines)
    if len(rendered) < TELEGRAM_LIMIT:
        return rendered
    return rendered[: TELEGRAM_LIMIT - 2].rstrip() + "…"


def format_success_message(
    context: Mapping[str, Any], *, secrets: Sequence[str] = ()
) -> str:
    safe = lambda value: sanitize_text(value, secrets)
    title = (
        "اختبار AurumAI Paper Trading"
        if context.get("mode") == "dry-run"
        else "AurumAI Paper Trading — نجاح"
    )
    lines = [
        f"<b>{title}</b>",
        "PAPER TRADING فقط — لا تداول فعلي",
        f"التاريخ ليبيا: {safe(context.get('libya_time', 'غير متاح'))}",
        f"الوقت UTC: {safe(context.get('utc_time', 'غير متاح'))}",
        f"Evaluation ID: {safe(context.get('evaluation_id', 'غير متاح'))}",
        f"Runtime ID: {safe(context.get('runtime_id', 'لم يُشغّل'))}",
        f"Freshness: {safe(context.get('freshness', 'غير متاح'))}",
        f"القرار: {safe(context.get('decision', 'غير متاح'))}",
        f"الاتجاه: {safe(context.get('direction', 'غير متاح'))}",
        f"Confidence: {safe(context.get('confidence', 'غير متاح'))}",
        f"Reliability: {safe(context.get('reliability', 'غير متاح'))}",
        f"أول gate: {safe(context.get('first_gate', 'غير متاح'))}",
        f"السبب: {safe(context.get('gate_reason', 'غير متاح'))}",
        f"Paper risk/size: {safe(context.get('risk_size', 'غير متاح'))}",
        f"المراحل: {safe(context.get('stage_count', '0/0'))}",
        (
            "Predictions المكتملة/الإجمالي: "
            f"{safe(context.get('completed_predictions', 0))}/"
            f"{safe(context.get('total_predictions', 0))}"
        ),
        f"حالة العينة: {safe(context.get('sample_status', 'INSUFFICIENT_SAMPLE'))}",
        f"الحالة: {safe(context.get('eligibility', 'DRY_RUN'))}",
        f"تقييم outcomes: {safe(context.get('outcome_note', 'لم يُنفّذ'))}",
        f"GitHub Actions: {safe(context.get('run_url', 'غير متاح'))}",
    ]
    return _message(lines)


def format_failure_message(
    *,
    stage: str,
    reason: str,
    run_url: str,
    secrets: Sequence[str] = (),
    status: str = "FAILED",
) -> str:
    return _message(
        [
            f"<b>AurumAI Paper Trading — {sanitize_text(status, secrets)}</b>",
            "PAPER TRADING فقط — لا تداول فعلي",
            f"المرحلة: {sanitize_text(stage, secrets)}",
            f"السبب: {sanitize_text(reason, secrets)}",
            "لم يتم إنشاء prediction مؤهلة.",
            f"GitHub Actions: {sanitize_text(run_url, secrets)}",
        ]
    )


def send_telegram_message(
    message: str,
    *,
    token: str,
    chat_id: str,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> None:
    if not token or not chat_id:
        raise AutomationFailure("telegram", "Telegram credentials are missing")
    body = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    ).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with opener(request, timeout=20) as response:
            if getattr(response, "status", 200) >= 300:
                raise AutomationFailure("telegram", "Telegram rejected the message")
    except AutomationFailure:
        raise
    except Exception as exc:
        raise AutomationFailure("telegram", "Telegram delivery failed") from exc


def _scan_sensitive(value: Any, location: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in SENSITIVE_KEYS or any(
                normalized.endswith(f"_{name}") for name in SENSITIVE_KEYS
            ):
                if child not in (None, "", [], {}):
                    findings.append(f"{location}.{key}")
            findings.extend(_scan_sensitive(child, f"{location}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_scan_sensitive(child, f"{location}[{index}]"))
    return findings


def scan_runtime_secrets(paths: Sequence[Path], secret_values: Sequence[str]) -> None:
    findings: list[str] = []
    for path in paths:
        value = _read_object(path)
        findings.extend(f"{path.name}:{item}" for item in _scan_sensitive(value))
        raw = path.read_text(encoding="utf-8")
        if any(secret and secret in raw for secret in secret_values):
            findings.append(f"{path.name}:known-secret-value")
    if findings:
        raise AutomationFailure(
            "secret-scan", f"sensitive fields exposed in {len(findings)} location(s)"
        )


def _major_freshness(snapshot: Mapping[str, str]) -> dict[str, str]:
    aliases = {
        "FRED": ("fred", "dgs", "dfii", "t5yie", "macro"),
        "XAU/USD": ("xau", "gold"),
        "DXY": ("dxy",),
        "price": ("price", "gold", "xau"),
    }
    bad = {"stale", "fallback_stale", "unavailable", "missing", "unknown"}
    result: dict[str, str] = {}
    for source, needles in aliases.items():
        matches = [
            str(status).lower()
            for name, status in snapshot.items()
            if any(needle in str(name).lower() for needle in needles)
        ]
        if not matches:
            result[source] = "unknown"
        elif any(status in bad for status in matches):
            result[source] = next(status for status in matches if status in bad)
        elif all(status in FRESH_STATUSES for status in matches):
            result[source] = "fresh"
        else:
            result[source] = "unknown"
    return result


def evaluation_exists(ledger_dir: Path, evaluation_id: str) -> bool:
    for path in (Path(ledger_dir) / "predictions").glob("*.json"):
        try:
            if _read_object(path).get("evaluation_id") == evaluation_id:
                return True
        except AutomationFailure:
            raise AutomationFailure("duplicate-check", "invalid existing prediction")
    return False


def immutable_snapshot(ledger_dir: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for folder in ("predictions", "outcomes"):
        for path in sorted((Path(ledger_dir) / folder).glob("*.json")):
            relative = path.relative_to(ledger_dir).as_posix()
            snapshot[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def validate_append_only(ledger_dir: Path, before: Mapping[str, str]) -> None:
    after = immutable_snapshot(ledger_dir)
    for relative, digest in before.items():
        if after.get(relative) != digest:
            raise AutomationFailure("ledger-integrity", "existing ledger record changed")


def _runtime_directories(strategy_dir: Path) -> set[Path]:
    return {path.parent.resolve() for path in (strategy_dir / "outputs").rglob("summary.json")}


def _run_once(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout: int,
    environment: Mapping[str, str],
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=dict(environment),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else exc.stdout
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else exc.stderr
        return subprocess.CompletedProcess(
            list(command),
            124,
            stdout=stdout or "",
            stderr=stderr or "pipeline timeout exceeded",
        )


def _write_sanitized_log(path: Path, text: str, secrets: Sequence[str]) -> None:
    lines = [sanitize_text(line, secrets) for line in text.splitlines()]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _validate_runtime(
    run_dir: Path,
    strategy_dir: Path,
    *,
    secret_values: Sequence[str],
) -> dict[str, Any]:
    required = [
        run_dir / "stage_outputs.json",
        run_dir / "summary.json",
        run_dir / "outcome.json",
        run_dir / "stages.json",
        run_dir / "finalize.json",
    ]
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        raise AutomationFailure("artifact-validation", "required runtime artifacts missing")
    stage_outputs = _read_object(required[0])
    summary = _read_object(required[1])
    outcome = _read_object(required[2])
    try:
        stages = json.loads(required[3].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AutomationFailure("artifact-validation", "invalid stages.json") from exc
    outputs = stage_outputs.get("outputs")
    if (
        stage_outputs.get("stage_count") != 27
        or not isinstance(outputs, dict)
        or len(outputs) != 27
        or not isinstance(stages, list)
        or len(stages) != 27
        or any(
            not isinstance(item, dict) or item.get("status") != "ok"
            for item in stages
        )
    ):
        raise AutomationFailure("stage-gate", "runtime did not complete 27/27 stages")
    if summary.get("success") is not True or summary.get("errors"):
        raise AutomationFailure("runtime-gate", "runtime summary is not successful")
    runtime_id = str(summary.get("pipeline_id") or "")
    if not runtime_id or outcome.get("run_id") != runtime_id:
        raise AutomationFailure("artifact-validation", "runtime identifiers mismatch")
    decision_time = _parse_time(summary.get("timestamp"), "decision timestamp")
    if decision_time > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
        raise AutomationFailure("timestamp-gate", "decision timestamp is in the future")
    scan_runtime_secrets(required, secret_values)
    registry = strategy_dir / "runtime" / "run_registry.jsonl"
    try:
        records = [
            json.loads(line)
            for line in registry.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        raise AutomationFailure("registry-gate", "runtime registry is invalid") from exc
    if not records or records[-1].get("run_id") != runtime_id:
        raise AutomationFailure("registry-gate", "runtime registry does not match")
    registry_output = Path(str(records[-1].get("output_directory") or ""))
    registry_report = Path(str(records[-1].get("report_path") or ""))
    if registry_output.resolve() != run_dir.resolve():
        raise AutomationFailure("registry-gate", "registry output path does not match")
    if registry_report.resolve() != (run_dir / "institutional_report.md").resolve():
        raise AutomationFailure("registry-gate", "registry report path does not match")
    snapshot = _freshness_snapshot(outputs, summary)
    freshness = _major_freshness(snapshot)
    ledger_eligible = bool(snapshot) and all(
        str(status).lower() in FRESH_STATUSES for status in snapshot.values()
    )
    return {
        "runtime_id": runtime_id,
        "summary": summary,
        "outcome": outcome,
        "stage_outputs": stage_outputs,
        "freshness_snapshot": snapshot,
        "freshness": freshness,
        "freshness_eligible": all(value == "fresh" for value in freshness.values()),
        "ledger_eligible": ledger_eligible,
        "decision_time": decision_time,
    }


def _parse_time(value: Any, label: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise AutomationFailure("timestamp-gate", f"invalid {label}") from exc
    if parsed.tzinfo is None:
        raise AutomationFailure("timestamp-gate", f"timezone missing from {label}")
    return parsed.astimezone(dt.timezone.utc)


def _direction(manifest: Mapping[str, Any]) -> str:
    return str(manifest.get("direction") or "غير متاح")


def _first_gate(manifest: Mapping[str, Any]) -> tuple[str, str]:
    gate = manifest.get("first_decision_gate")
    if not isinstance(gate, dict):
        return "غير متاح", "غير متاح"
    return str(gate.get("gate") or "غير متاح"), str(
        gate.get("rejection_reason") or "غير متاح"
    )


def _copy_safe_artifacts(
    run_dir: Path,
    target: Path,
    *,
    secrets: Sequence[str],
) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for name in (
        "stage_outputs.json",
        "summary.json",
        "outcome.json",
        "stages.json",
        "finalize.json",
        "institutional_report.md",
        "institutional_report.html",
    ):
        source = run_dir / name
        if source.is_file():
            destination = target / name
            if source.suffix in {".md", ".html"}:
                raw = source.read_text(encoding="utf-8")
                for secret in secrets:
                    raw = raw.replace(secret, "[REDACTED]")
                destination.write_text(raw, encoding="utf-8")
            else:
                shutil.copy2(source, destination)


def _evaluate_due_predictions(
    ledger_dir: Path,
    prices_path: Path,
    *,
    freshness_status: str,
    as_of_utc: str,
) -> tuple[int, str]:
    if freshness_status != "fresh" or not prices_path.is_file():
        return 0, "pending; compatible fresh price source unavailable"
    try:
        with prices_path.open(encoding="utf-8-sig") as handle:
            header = handle.readline().lower()
    except OSError:
        return 0, "pending; compatible price source unavailable"
    if not ({"date", "close"} <= {item.strip() for item in header.split(",")}) and not (
        {"timestamp", "close"} <= {item.strip() for item in header.split(",")}
    ):
        return 0, "pending; price source does not match evaluator contract"
    completed = 0
    for prediction_path in sorted((ledger_dir / "predictions").glob("*.json")):
        prediction = _read_object(prediction_path)
        if (
            prediction.get("cohort_id") != COHORT_ID
            or prediction.get("baseline_commit") != STRATEGY_BASELINE
        ):
            continue
        prediction_id = str(prediction.get("prediction_id") or "")
        for horizon in prediction.get("evaluation_horizons_sessions", []):
            outcome_path = (
                ledger_dir
                / "outcomes"
                / f"{prediction_id}.h{int(horizon)}.outcome.json"
            )
            if outcome_path.exists():
                continue
            try:
                evaluate_prediction(
                    prediction_path,
                    ledger_dir / "outcomes",
                    prices_path,
                    horizon_sessions=int(horizon),
                    as_of_utc=as_of_utc,
                    freshness_status="fresh",
                )
                completed += 1
            except HorizonNotComplete:
                continue
            except PaperTradingError as exc:
                raise AutomationFailure(
                    "outcome-evaluation", "existing evaluator rejected a due record"
                ) from exc
    if completed:
        return completed, f"{completed} horizon outcome(s) appended"
    return 0, "pending; no horizon is due"


def _preflight(
    *,
    strategy_dir: Path,
    harness_dir: Path,
    ledger_dir: Path,
    ledger_repository: str,
    environment: Mapping[str, str],
) -> tuple[str, str]:
    presence = secret_presence(environment)
    missing = [name for name, status in presence.items() if status == "MISSING"]
    if missing:
        raise AutomationFailure("preflight", "required GitHub secret names are missing")
    if not ledger_repository or not (ledger_dir / ".git").exists():
        raise AutomationFailure("preflight", "private ledger checkout is unavailable")
    remote_url = _git(ledger_dir, "remote", "get-url", "origin").stdout.strip().lower()
    expected_slug = ledger_repository.lower().removesuffix(".git")
    if expected_slug not in remote_url.removesuffix(".git"):
        raise AutomationFailure("preflight", "private ledger repository mismatch")
    strategy_commit = _head(strategy_dir)
    harness_commit = _head(harness_dir)
    if strategy_commit != STRATEGY_BASELINE:
        raise AutomationFailure("preflight", "strategy baseline mismatch")
    base_config = _read_object(harness_dir / "config" / "paper_trading_baseline.json")
    if base_config.get("baseline_commit") != STRATEGY_BASELINE:
        raise AutomationFailure("preflight", "locked paper configuration mismatch")
    _load_paper_trading_cli(harness_dir)
    return strategy_commit, harness_commit


def _load_paper_trading_cli(harness_dir: Path) -> None:
    """Load the checkout CLI without relying on the caller's working directory."""
    cli = (harness_dir / "scripts" / "paper_trading.py").resolve()
    if not cli.is_file():
        raise AutomationFailure("preflight", "paper-trading CLI is missing")
    help_result = subprocess.run(
        [sys.executable, str(cli), "--help"],
        cwd=str(harness_dir),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if help_result.returncode != 0:
        error_type = "CLIProcessError"
        missing_module = None
        module_match = re.search(
            r"ModuleNotFoundError: No module named ['\"]([A-Za-z0-9_.-]+)['\"]",
            help_result.stderr,
        )
        if module_match:
            error_type = "ModuleNotFoundError"
            missing_module = module_match.group(1)
        elif "[Errno 2]" in help_result.stderr:
            error_type = "FileNotFoundError"
        raise AutomationFailure(
            "preflight",
            "paper-trading CLI failed to load",
            error_type=error_type,
            missing_module=missing_module,
        )


def _create_daily_config(
    base_path: Path,
    target: Path,
    *,
    evaluation_id: str,
    harness_commit: str,
    github_actions: Mapping[str, str],
) -> Path:
    config = _read_object(base_path)
    config["evaluation_id"] = evaluation_id
    config["cohort_id"] = COHORT_ID
    config["automation_context"] = {
        "strategy_baseline_commit": STRATEGY_BASELINE,
        "harness_commit": harness_commit,
        "github_actions": dict(github_actions),
    }
    _canonical_write(target, config)
    return target


def _commit_ledger(ledger_dir: Path, evaluation_id: str) -> None:
    branch = _git(ledger_dir, "branch", "--show-current").stdout.strip()
    if not branch:
        raise AutomationFailure("ledger-push", "ledger checkout is detached")
    _git(ledger_dir, "fetch", "origin", branch)
    local = _head(ledger_dir)
    remote = _git(ledger_dir, "rev-parse", f"origin/{branch}").stdout.strip()
    if local != remote:
        raise AutomationFailure("ledger-push", "ledger remote changed; safe stop")
    _git(ledger_dir, "config", "user.name", "github-actions[bot]")
    _git(
        ledger_dir,
        "config",
        "user.email",
        "41898282+github-actions[bot]@users.noreply.github.com",
    )
    existing = [
        name
        for name in ("predictions", "outcomes", "cohorts")
        if (ledger_dir / name).exists()
    ]
    _git(ledger_dir, "add", "--", *existing)
    changed = _git(ledger_dir, "diff", "--cached", "--name-status").stdout.splitlines()
    if not changed:
        raise AutomationFailure("ledger-push", "ledger has no new record")
    for line in changed:
        status, _, relative = line.partition("\t")
        if relative.startswith(("predictions/", "outcomes/")) and status != "A":
            raise AutomationFailure("ledger-integrity", "immutable ledger diff rejected")
        if status.startswith("D"):
            raise AutomationFailure("ledger-integrity", "ledger deletion rejected")
    _git(ledger_dir, "commit", "-m", f"paper ledger: {evaluation_id}")
    _git(ledger_dir, "push", "origin", f"HEAD:{branch}")


def _dry_context(evaluation_id: str, run_url: str, now: dt.datetime) -> dict[str, Any]:
    libya = now.astimezone(dt.timezone(dt.timedelta(hours=2)))
    return {
        "mode": "dry-run",
        "utc_time": now.isoformat(),
        "libya_time": libya.isoformat(),
        "evaluation_id": evaluation_id,
        "runtime_id": "لم يُشغّل",
        "freshness": "بيانات اصطناعية فقط",
        "decision": "NO_TRADE",
        "direction": "محايد",
        "confidence": "0.00",
        "reliability": "0.00",
        "first_gate": "dry_run_gate",
        "gate_reason": "اختبار formatter دون تشغيل pipeline",
        "risk_size": "لا يوجد",
        "stage_count": "0/27",
        "completed_predictions": 0,
        "total_predictions": 0,
        "sample_status": "INSUFFICIENT_SAMPLE",
        "eligibility": "DRY_RUN",
        "outcome_note": "لم يُنفّذ؛ بيانات formatter اصطناعية",
        "run_url": run_url,
    }


def execute_automation(
    *,
    mode: str,
    strategy_dir: Path,
    harness_dir: Path,
    ledger_dir: Path,
    output_dir: Path,
    market_date: str,
    ledger_repository: str,
    run_id: str,
    run_url: str,
    environment: Mapping[str, str],
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run_once,
    run_attempt: str | None = None,
    run_created_at_utc: str | None = None,
) -> dict[str, Any]:
    """Execute one dry or live paper run; never sends Telegram itself."""
    strategy_dir = Path(strategy_dir).resolve()
    harness_dir = Path(harness_dir).resolve()
    ledger_dir = Path(ledger_dir).resolve()
    output_dir = Path(output_dir).resolve()
    plan = mode_plan(mode)
    output_dir.mkdir(parents=True, exist_ok=True)
    secrets = _secret_values(environment)
    evaluation_id = deterministic_evaluation_id(market_date)
    _, harness_commit = _preflight(
        strategy_dir=strategy_dir,
        harness_dir=harness_dir,
        ledger_dir=ledger_dir,
        ledger_repository=ledger_repository,
        environment=environment,
    )
    if evaluation_exists(ledger_dir, evaluation_id):
        raise AutomationFailure("duplicate-check", "daily evaluation already exists")
    now = dt.datetime.now(dt.timezone.utc)
    if not plan.run_pipeline:
        context = _dry_context(evaluation_id, run_url, now)
        _canonical_write(output_dir / "result.json", context)
        (output_dir / "telegram_message.txt").write_text(
            format_success_message(context, secrets=secrets), encoding="utf-8"
        )
        return context

    if not run_attempt or not run_attempt.isdecimal() or int(run_attempt) < 1:
        raise AutomationFailure("provenance", "GitHub run attempt is missing or invalid")
    run_created = _parse_time(run_created_at_utc, "GitHub run creation timestamp")
    if run_created > now:
        raise AutomationFailure("provenance", "GitHub run creation timestamp is in the future")
    github_actions = {
        "run_id": run_id,
        "run_attempt": run_attempt,
        "run_url": run_url,
        "run_created_at_utc": run_created.isoformat(),
    }
    before_records = immutable_snapshot(ledger_dir)
    before_runs = _runtime_directories(strategy_dir)
    pipeline_environment = dict(environment)
    for name in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "PAPER_LEDGER_TOKEN"):
        pipeline_environment.pop(name, None)
    tool_environment = dict(pipeline_environment)
    tool_environment.pop("FRED_API_KEY", None)
    pipeline = runner(
        [sys.executable, "run.py"],
        cwd=strategy_dir,
        timeout=900,
        environment=pipeline_environment,
    )
    _write_sanitized_log(output_dir / "pipeline-stdout.log", pipeline.stdout, secrets)
    _write_sanitized_log(output_dir / "pipeline-stderr.log", pipeline.stderr, secrets)
    if pipeline.returncode != 0:
        raise AutomationFailure("pipeline", f"pipeline exit code {pipeline.returncode}")
    new_runs = _runtime_directories(strategy_dir) - before_runs
    if len(new_runs) != 1:
        raise AutomationFailure("runtime-discovery", "expected exactly one new runtime")
    run_dir = new_runs.pop()
    report = runner(
        [
            sys.executable,
            "scripts/generate_institutional_report.py",
            "--output-dir",
            str(run_dir),
        ],
        cwd=strategy_dir,
        timeout=180,
        environment=tool_environment,
    )
    _write_sanitized_log(output_dir / "report-stdout.log", report.stdout, secrets)
    _write_sanitized_log(output_dir / "report-stderr.log", report.stderr, secrets)
    if report.returncode != 0:
        raise AutomationFailure("report", f"report exit code {report.returncode}")
    report_path = run_dir / "institutional_report.md"
    if not report_path.is_file() or not report_path.stat().st_size:
        raise AutomationFailure("report", "institutional report is missing")

    validated = _validate_runtime(
        run_dir,
        strategy_dir,
        secret_values=secrets,
    )
    major_fresh = validated["freshness_eligible"]
    if not major_fresh and validated["ledger_eligible"]:
        raise AutomationFailure(
            "freshness-gate", "major source freshness cannot be represented safely"
        )
    _, outcome_note = _evaluate_due_predictions(
        ledger_dir,
        strategy_dir / "data" / "history" / "gold" / "gold.csv",
        freshness_status=validated["freshness"]["price"],
        as_of_utc=now.isoformat(),
    )
    daily_config = _create_daily_config(
        harness_dir / "config" / "paper_trading_baseline.json",
        output_dir / "paper-config.json",
        evaluation_id=evaluation_id,
        harness_commit=harness_commit,
        github_actions=github_actions,
    )
    predictions_before = set((ledger_dir / "predictions").glob("*.json"))
    create = runner(
        [
            sys.executable,
            str(harness_dir / "scripts" / "paper_trading.py"),
            "create",
            "--runtime-dir",
            str(run_dir),
            "--registry-dir",
            str(ledger_dir),
            "--config",
            str(daily_config),
            "--baseline-commit",
            STRATEGY_BASELINE,
        ],
        cwd=harness_dir,
        timeout=60,
        environment=tool_environment,
    )
    if create.returncode != 0:
        raise AutomationFailure("prediction", "paper-trading CLI rejected the runtime")
    new_predictions = set((ledger_dir / "predictions").glob("*.json")) - predictions_before
    if len(new_predictions) != 1:
        raise AutomationFailure("prediction", "expected exactly one new prediction")
    prediction_path = new_predictions.pop()
    prediction_path.chmod(0o444)
    manifest = _read_object(prediction_path)
    if manifest.get("evaluation_id") != evaluation_id:
        raise AutomationFailure("prediction", "evaluation identifier mismatch")
    if manifest.get("cohort_id") != COHORT_ID:
        raise AutomationFailure("prediction", "cohort identifier mismatch")
    if manifest.get("strategy_baseline_commit") != STRATEGY_BASELINE:
        raise AutomationFailure("prediction", "strategy provenance mismatch")
    if manifest.get("harness_commit") != harness_commit:
        raise AutomationFailure("prediction", "harness provenance mismatch")
    if manifest.get("github_actions") != github_actions:
        raise AutomationFailure("prediction", "GitHub run provenance mismatch")
    scan_runtime_secrets([prediction_path], secrets)
    _canonical_write(output_dir / "run-manifest.json", {
        "github_actions": github_actions,
        "evaluation_id": evaluation_id,
        "prediction_id": manifest["prediction_id"],
        "prediction_sha256": hashlib.sha256(prediction_path.read_bytes()).hexdigest(),
        "strategy_baseline_commit": STRATEGY_BASELINE,
        "harness_commit": harness_commit,
        "timing_evidence": "GitHub run metadata reference; not proof of prediction publication time",
    })

    summary_path = ledger_dir / "cohorts" / COHORT_ID / "summary.json"
    summary = runner(
        [
            sys.executable,
            str(harness_dir / "scripts" / "paper_trading.py"),
            "summarize",
            "--registry-dir",
            str(ledger_dir),
            "--cohort-id",
            COHORT_ID,
            "--output",
            str(summary_path),
        ],
        cwd=harness_dir,
        timeout=60,
        environment=tool_environment,
    )
    if summary.returncode != 0:
        raise AutomationFailure("cohort-summary", "cohort summary failed")
    cohort_summary = _read_object(summary_path)
    validate_append_only(ledger_dir, before_records)
    _commit_ledger(ledger_dir, evaluation_id)

    _copy_safe_artifacts(run_dir, output_dir / "runtime", secrets=secrets)
    shutil.copy2(prediction_path, output_dir / "prediction.json")
    shutil.copy2(summary_path, output_dir / "cohort-summary.json")
    first_gate, gate_reason = _first_gate(manifest)
    eligibility = "ELIGIBLE" if manifest.get("financially_eligible") else "INELIGIBLE"
    decision_time = validated["decision_time"]
    context = {
        "mode": "live-paper",
        "utc_time": decision_time.isoformat(),
        "libya_time": decision_time.astimezone(
            dt.timezone(dt.timedelta(hours=2))
        ).isoformat(),
        "evaluation_id": evaluation_id,
        "runtime_id": validated["runtime_id"],
        "freshness": ", ".join(
            f"{key}={value}" for key, value in validated["freshness"].items()
        ),
        "decision": manifest.get("decision"),
        "direction": _direction(manifest),
        "confidence": manifest.get("confidence"),
        "reliability": manifest.get("reliability"),
        "first_gate": first_gate,
        "gate_reason": gate_reason,
        "risk_size": manifest.get("recommended_risk_size"),
        "stage_count": "27/27",
        "completed_predictions": cohort_summary.get("completed_trades", 0),
        "total_predictions": cohort_summary.get("total_decisions", 0),
        "sample_status": (cohort_summary.get("economic_gate") or {}).get(
            "status", "INSUFFICIENT_SAMPLE"
        ),
        "eligibility": eligibility,
        "outcome_note": outcome_note,
        "run_url": run_url,
    }
    _canonical_write(output_dir / "result.json", context)
    (output_dir / "telegram_message.txt").write_text(
        format_success_message(context, secrets=secrets), encoding="utf-8"
    )
    return context


def write_failure_artifacts(
    output_dir: Path,
    failure: AutomationFailure,
    *,
    run_url: str,
    environment: Mapping[str, str],
) -> None:
    secrets = _secret_values(environment)
    output_dir.mkdir(parents=True, exist_ok=True)
    message = format_failure_message(
        stage=failure.stage,
        reason=failure.reason,
        run_url=run_url,
        secrets=secrets,
    )
    (output_dir / "telegram_message.txt").write_text(message, encoding="utf-8")
    result = {
        "status": "FAILED",
        "stage": failure.stage,
        "reason": failure.reason,
        "error_type": failure.error_type or type(failure).__name__,
    }
    if failure.error_type == "ModuleNotFoundError" and failure.missing_module:
        result["missing_module"] = failure.missing_module
    _canonical_write(output_dir / "result.json", result)

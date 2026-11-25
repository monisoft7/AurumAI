"""Seven-case structured research reader evaluation. Explicit opt-in, no trading tools."""

import argparse
import hashlib
import json
import os
import time
from collections import Counter
from pathlib import Path
import requests

from .data import write_atomic

OUT = Path(__file__).with_name("researcher_results.json")
MODELS = ("openai/gpt-oss-20b", "openai/gpt-oss-120b")
# Ground truth and prompts are fixed before the first inference. Codes are shuffled by case.
CASES = [
    (
        "failed_replication",
        "A pullback initially gained in 33 fills. On separate dates two simulators had negative mean over more than 450 fills. Interpret and identify two decisive observations.",
        ["replicated", "unsupported", "implementation_only"],
        [
            "larger_independent_sample",
            "profitable_subset",
            "two_engines_agree",
            "one_engine_only",
        ],
        "unsupported",
        ["larger_independent_sample", "two_engines_agree"],
    ),
    (
        "method",
        "A researcher chooses the best threshold on a final year and reports its score on that year. Diagnose and prescribe evidence needed.",
        ["valid", "resampling_error", "selection_bias"],
        [
            "reuse_final_year",
            "new_untouched_window",
            "freeze_threshold",
            "invert_signal",
        ],
        "selection_bias",
        ["new_untouched_window", "freeze_threshold"],
    ),
    (
        "hypothesis",
        "Historical shocks around a release are large but directional accuracy is near chance. Select a falsifiable next study and its controls.",
        ["direction_reversal", "test_volatility", "approve_direction"],
        [
            "matched_non_event_hours",
            "conditional_realized_volatility",
            "daily_revised_cpi",
            "absolute_gold_level",
        ],
        "test_volatility",
        ["matched_non_event_hours", "conditional_realized_volatility"],
    ),
    (
        "data",
        "A study asks whether unexpected inflation drives gold after the release. Which inputs define surprise at decision time?",
        ["use_first_print_surprise", "use_recent_revision", "use_calendar_only"],
        [
            "calendar_month",
            "first_published_actual",
            "latest_revised_actual",
            "timestamped_pre_release_consensus",
        ],
        "use_first_print_surprise",
        ["first_published_actual", "timestamped_pre_release_consensus"],
    ),
    (
        "critique",
        "Gold and the dollar fall/rise together at the exact same timestamp in a retrospective panel. The author claims an exploitable causal lead. Critique the evidence.",
        ["demonstrated_lead", "causal", "insufficient"],
        [
            "contemporaneous_association",
            "lagged_out_of_sample_test",
            "change_price_units",
            "same_bar_accuracy",
        ],
        "insufficient",
        ["contemporaneous_association", "lagged_out_of_sample_test"],
    ),
    (
        "duplicate",
        "Archived experiment A used the same data, mechanism, parameters and cost assumptions as a renamed request. What should the lab do?",
        ["rerun_until_positive", "retrieve_existing", "promote"],
        [
            "rename_is_novel",
            "new_preregistered_evidence",
            "identical_fingerprint",
            "drop_negative_result",
        ],
        "retrieve_existing",
        ["new_preregistered_evidence", "identical_fingerprint"],
    ),
    (
        "leakage",
        "At 08:15 a backtest joins the final CPI value by calendar date; the first release arrived at 08:30 and an annual revision came later. Diagnose both problems.",
        ["safe_join", "time_and_vintage_leak", "timezone_only"],
        [
            "date_join_before_release",
            "revised_value_unavailable",
            "future_volatility",
            "weekend_mismatch",
        ],
        "time_and_vintage_leak",
        ["date_join_before_release", "revised_value_unavailable"],
    ),
]
ENDPOINT = "https://api.groq.com/openai/v1"


def schema(actions, evidence):
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["decision", "evidence", "reason"],
        "properties": {
            "decision": {"type": "string", "enum": actions},
            "evidence": {
                "type": "array",
                "items": {"type": "string", "enum": evidence},
            },
            "reason": {"type": "string"},
        },
    }


def grade(obj, case):
    if not isinstance(obj, dict) or set(obj) != {"decision", "evidence", "reason"}:
        raise ValueError("wrong fields")
    if (
        obj["decision"] not in case[2]
        or not isinstance(obj["reason"], str)
        or not obj["reason"].strip()
    ):
        raise ValueError("invalid decision or rationale")
    evidence = obj["evidence"]
    if (
        not isinstance(evidence, list)
        or len(evidence) != 2
        or len(set(evidence)) != 2
        or any(e not in case[3] for e in evidence)
    ):
        raise ValueError("expected two different allowed facts")
    return int(obj["decision"] == case[4]) + len(set(evidence) & set(case[5]))


def run():
    results = {
        "availability": {},
        "models": {},
        "actual_incremental_usd": 0,
        "billing_basis": "owner-confirmed unbilled Groq free plan",
    }
    key = os.environ.get("GROQ_API_KEY")
    auth = {"Authorization": "Bearer " + key} if key else {}
    for name, url, headers in [
        ("Groq", ENDPOINT + "/models", auth),
        (
            "Gemini",
            "https://generativelanguage.googleapis.com/v1beta/models",
            {"x-goog-api-key": os.environ.get("GEMINI_API_KEY", "")},
        ),
        (
            "OpenRouter",
            "https://openrouter.ai/api/v1/models",
            {"Authorization": "Bearer " + os.environ.get("OPENROUTER_API_KEY", "")},
        ),
    ]:
        if (
            (name == "OpenRouter" and not os.environ.get("OPENROUTER_API_KEY"))
            or not all(headers.values())
            or not headers
        ):
            results["availability"][name] = {"status": "no configured credential"}
            continue
        try:
            r = requests.get(url, headers=headers, timeout=15)
            ids = (
                [
                    v.get("id", v.get("name"))
                    for v in r.json().get("data", r.json().get("models", []))
                ]
                if r.ok
                else []
            )
            results["availability"][name] = {"status": r.status_code, "listed": ids}
        except (requests.RequestException, ValueError) as exc:
            results["availability"][name] = {"status": type(exc).__name__}
    for model in MODELS:
        if model not in results["availability"]["Groq"].get("listed", []):
            continue
        rows = []
        for case in CASES:
            name, task, actions, evidence = case[:4]
            row = {"case": name, "attempts": 0, "score": 0, "tokens": {}, "errors": []}
            payload = {
                "model": model,
                "temperature": 0,
                "max_completion_tokens": 900,
                "reasoning_effort": "low",
                "messages": [
                    {
                        "role": "system",
                        "content": "Research methods reviewer. Choose one decision, two distinct relevant evidence codes, and explain the project's inference in one sentence.",
                    },
                    {"role": "user", "content": task},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "review",
                        "strict": True,
                        "schema": schema(actions, evidence),
                    },
                },
            }
            start = time.monotonic()
            for attempt in range(2):
                row["attempts"] += 1
                try:
                    r = requests.post(
                        ENDPOINT + "/chat/completions",
                        headers=auth,
                        json=payload,
                        timeout=35,
                    )
                    if not r.ok:
                        row["errors"].append(f"HTTP {r.status_code}")
                        if attempt == 0 and (
                            r.status_code == 429 or r.status_code >= 500
                        ):
                            delay = r.headers.get("retry-after", "8")
                            try:
                                seconds = float(delay)
                            except ValueError:
                                seconds = 8
                            if seconds <= 60:
                                time.sleep(max(1, seconds))
                                continue
                        break
                    reply = r.json()
                    usage = Counter(row["tokens"])
                    usage.update(
                        {
                            k: reply.get("usage", {}).get(k, 0)
                            for k in ("prompt_tokens", "completion_tokens")
                        }
                    )
                    row["tokens"] = dict(usage)
                    obj = json.loads(reply["choices"][0]["message"]["content"])
                    row["score"] = grade(obj, case)
                    row["answer"] = obj
                    break
                except (
                    ValueError,
                    KeyError,
                    IndexError,
                    requests.RequestException,
                ) as exc:
                    row["errors"].append(type(exc).__name__)
            row["seconds"] = round(time.monotonic() - start, 2)
            rows.append(row)
            print(model, name, row["score"], row["errors"], flush=True)
            time.sleep(2.1)
        results["models"][model] = {
            "tasks": rows,
            "points": sum(x["score"] for x in rows),
            "correct_decisions": sum(
                x.get("answer", {}).get("decision") == case[4]
                for x, case in zip(rows, CASES)
            ),
        }
    eligible = [
        m
        for m, val in results["models"].items()
        if val["points"] >= 18 and val["correct_decisions"] >= 6
    ]
    # Equal quality on the same tasks favours the cheaper model (20B is listed first).
    results["selected"] = max(
        eligible, key=lambda m: results["models"][m]["points"], default=None
    )
    write_atomic(OUT, (json.dumps(results, indent=2) + "\n").encode())


def review(db, target, post=requests.post):
    """On-demand research note, grounded in the frozen results and cached by evidence."""
    from .predictive import RESULT

    model = json.loads(OUT.read_bytes())["selected"]
    if model not in MODELS:
        raise ValueError("no qualified research reader")
    results = json.loads(RESULT.read_bytes())
    evidence = {
        "protocol": results["protocol_sha256"],
        "target": target,
        "period": "2024 development only",
        "models": {
            group: {
                k: row[k]
                for k in (
                    "rows",
                    "loss",
                    "comparisons",
                    "passes_references",
                    "passes_incremental",
                )
            }
            for group, row in results["targets"][target].items()
        },
    }
    key = hashlib.sha256(
        json.dumps([model, evidence], sort_keys=True).encode()
    ).hexdigest()
    db.execute(
        "CREATE TABLE IF NOT EXISTS predictive_reader_notes (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
    )
    with db:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute(
            "SELECT payload FROM predictive_reader_notes WHERE id=?", (key,)
        ).fetchone()
        if existing:
            return json.loads(existing[0])
        fields = (
            "interpretation",
            "alternative_explanation",
            "falsification",
            "required_data",
        )
        shape = {
            "type": "object",
            "required": list(fields),
            "additionalProperties": False,
            "properties": {k: {"type": "string"} for k in fields},
        }
        payload = {
            "model": model,
            "temperature": 0,
            "max_completion_tokens": 1200,
            "reasoning_effort": "low",
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "research_note",
                    "strict": True,
                    "schema": shape,
                },
            },
            "messages": [
                {
                    "role": "system",
                    "content": "Interpret only the supplied measured evidence. Give one competing explanation and a falsifiable independent replication. Never recommend a trade or output code.",
                },
                {"role": "user", "content": json.dumps(evidence)},
            ],
        }
        r = post(
            ENDPOINT + "/chat/completions",
            headers={"Authorization": "Bearer " + os.environ["GROQ_API_KEY"]},
            json=payload,
            timeout=35,
        )
        r.raise_for_status()
        reply = r.json()
        answer = json.loads(reply["choices"][0]["message"]["content"])
        if set(answer) != set(fields) or not all(
            isinstance(answer[k], str) and answer[k].strip() for k in fields
        ):
            raise ValueError("invalid research note")
        note = {
            "id": key,
            "type": "unverified_interpretation",
            "target": target,
            "model": model,
            "answer": answer,
            "source": results["protocol_sha256"],
            "usage": {
                k: reply.get("usage", {}).get(k, 0)
                for k in ("prompt_tokens", "completion_tokens")
            },
        }
        db.execute(
            "INSERT INTO predictive_reader_notes VALUES(?,?)", (key, json.dumps(note))
        )
        return note


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--free-evaluation", action="store_true")
    actions.add_argument("--review", metavar="TARGET")
    args = parser.parse_args()
    if args.free_evaluation:
        if OUT.exists():
            raise SystemExit("evaluation already recorded")
        run()
    else:
        from .data import CACHE
        from .lab import database

        db = database(CACHE / "memory.sqlite")
        try:
            print(json.dumps(review(db, args.review), indent=2))
        finally:
            db.close()

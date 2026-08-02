"""Conformance: every implemented workflow package declares the workflow
identifier defined by IMPLEMENTATION_WORKFLOWS.md.

The canonical index is parsed from the "Workflow Index" table of
IMPLEMENTATION_WORKFLOWS.md so the test tracks the authoritative document.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DOC = REPO_ROOT / "IMPLEMENTATION_WORKFLOWS.md"
SRC = REPO_ROOT / "src"

# Every implemented institutional workflow package and its canonical workflow
# identifier, as defined by the Workflow Index in IMPLEMENTATION_WORKFLOWS.md.
IMPLEMENTED_WORKFLOW_PACKAGES = {
    "pre_market": "W3",
    "event_triage": "W4",
    "signal_assessment": "W5",
    "evidence_collection": "W6",
    "evidence_reasoning": "W6",
    "counter_evidence": "W7",
    "thesis_construction": "W8",
    "thesis_update": "W10",
    "confidence_engine": "W9",
    "scenario_generation": "W12",
    "risk_reward_validation": "W12",
    "bias_prevention": "W13",
    "decision_engine": "W13",
    "trade_recommendation": "W14",
}

WORKFLOW_ID_RE = re.compile(r"\bW(?:1[0-7]|[1-9])\b")

# A docstring whose first line begins with one of these patterns is a
# workflow *declaration*; W-IDs appearing mid-line are cross-workflow
# references and are not declarations.
DECLARATION_RE = re.compile(r"^(?:W(?:1[0-7]|[1-9])|Workflow W(?:1[0-7]|[1-9])|Orchestrates W(?:1[0-7]|[1-9]))\b")


def _canonical_workflow_index() -> dict[str, str]:
    text = WORKFLOWS_DOC.read_text(encoding="utf-8")
    start = text.index("## Workflow Index")
    end = text.index("## Workflow Specifications", start)
    index: dict[str, str] = {}
    for line in text[start:end].splitlines():
        match = re.match(r"\|\s*(W\d+)\s*\|\s*([^|]+?)\s*\|", line)
        if match:
            index[match.group(1)] = match.group(2).strip()
    return index


def test_workflow_index_contains_all_seventeen_workflows() -> None:
    index = _canonical_workflow_index()
    assert set(index) == {f"W{n}" for n in range(1, 18)}


def test_implemented_packages_declare_canonical_workflow_id() -> None:
    index = _canonical_workflow_index()
    for package, expected_id in IMPLEMENTED_WORKFLOW_PACKAGES.items():
        assert expected_id in index, (
            f"{expected_id} is missing from the IMPLEMENTATION_WORKFLOWS.md index"
        )
        init_file = SRC / package / "__init__.py"
        assert init_file.is_file(), f"{package} package __init__.py is missing"
        docstring = init_file.read_text(encoding="utf-8")
        declared = set(WORKFLOW_ID_RE.findall(docstring))
        assert declared, f"{package} declares no workflow identifier in __init__.py"
        assert declared == {expected_id}, (
            f"{package} declares {sorted(declared)} but IMPLEMENTATION_WORKFLOWS.md "
            f"defines it as {expected_id}"
        )


def test_no_module_declares_an_off_workflow_id() -> None:
    for py_file in SRC.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        docstring_match = re.match(r'^\s*"""(.*?)"""', text, re.DOTALL)
        if not docstring_match:
            continue
        first_line = docstring_match.group(1).splitlines()[0]
        declaration = DECLARATION_RE.match(first_line)
        if declaration is None:
            continue
        declared = WORKFLOW_ID_RE.search(first_line).group(0)
        package = py_file.parent.name
        expected = IMPLEMENTED_WORKFLOW_PACKAGES.get(package)
        assert expected is not None, (
            f"{py_file.relative_to(SRC)} declares {declared} but the {package} "
            f"package is not a registered workflow package"
        )
        assert declared == expected, (
            f"{py_file.relative_to(SRC)} declares {declared}, expected {expected} "
            f"per IMPLEMENTATION_WORKFLOWS.md"
        )


def test_created_by_identifiers_conform_to_canonical_workflow_id() -> None:
    for py_file in SRC.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for match in re.finditer(r'created_by="(W(?:1[0-7]|[1-9])[^"]*)"', text):
            created_by = match.group(1)
            wid = WORKFLOW_ID_RE.match(created_by).group(0)
            package = py_file.parent.name
            expected = IMPLEMENTED_WORKFLOW_PACKAGES.get(package)
            assert expected is not None, (
                f"{py_file.relative_to(SRC)} uses created_by={created_by!r} in the "
                f"unregistered workflow package {package}"
            )
            assert wid == expected, (
                f"{py_file.relative_to(SRC)} uses created_by={created_by!r} but "
                f"{package} maps to {expected} per IMPLEMENTATION_WORKFLOWS.md"
            )

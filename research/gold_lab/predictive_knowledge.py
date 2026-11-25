"""Materialize the bounded research findings in the existing archive and graph types."""

import argparse
import hashlib
import json

from .data import CACHE
from .lab import database
from .predictive import RESULT
from .predictive_data import HERE, PRIVATE
from .researcher import OUT
from knowledge.graph.graph import KnowledgeGraph
from knowledge.graph.node import GraphNode
from knowledge.graph.relation import GraphRelation
from knowledge.graph.repository import GraphRepository


def records(result, language, phase2):
    issued = "2023 calibration; 2024 expanding quarterly development evaluation"
    sources = [
        "predictive_results.json",
        "predictive_protocol.json",
        "predictive_data.json",
    ]
    literature = [
        (
            "real_rates",
            "Long-horizon gold valuations can covary with real rates.",
            "Chicago Fed Letter 464",
            "https://www.chicagofed.org/publications/chicago-fed-letter/2021/464",
            "long-horizon macro valuation",
            "No timestamped intraday rate series in this round",
        ),
        (
            "news_surprise",
            "Scheduled macro surprises may alter precious-metal futures around publication.",
            "Christie-David, Chaudhry and Koch (2000)",
            "https://www.sciencedirect.com/science/article/pii/S0148619500000291",
            "intraday commodity futures around original announcements",
            "An occurrence flag omits consensus and sign",
        ),
        (
            "volatility_memory",
            "Risk can persist across multiple past volatility horizons.",
            "Corsi (2009)",
            "https://doi.org/10.1093/jjfinec/nbp001",
            "multi-horizon realized volatility research",
            "A variable barrier shares its scale with the predictors",
        ),
    ]
    for tag, statement, author, url, scope, limit in literature:
        yield {
            "id": "source/" + tag,
            "type": "literature_hypothesis",
            "tags": ["literature", tag],
            "statement": statement,
            "conditions": scope,
            "validity": "source study population; transfer to spot gold unconfirmed",
            "supporting": [author],
            "opposing": [limit],
            "uncertainty": "external validity unquantified",
            "experiment_ids": [],
            "source": [url],
        }
    for target, models in result["targets"].items():
        for group, model in models.items():
            admitted = (
                model["passes_references"] and model["passes_incremental"] is not False
            )
            tags = ["gold", target, group, "quarters_2024"]
            if group != "gold":
                tags.extend(["cross_asset", "dollar"])
            if group == "event":
                tags.append("post_cpi_feature")
            if target.startswith("up_"):
                tags.append("direction")
            elif target in ("absolute_return_bps", "realized_vol_bps", "large_move"):
                tags.append("risk")
            else:
                tags.append("barrier")
            contrasts = model["comparisons"]
            good = [
                k
                for k, v in contrasts.items()
                if v["lower_corrected"] > 0
                and all(f["gains"][k] > 0 for f in model["folds"])
            ]
            yield {
                "id": f"phase3/{target}/{group}",
                "type": "descriptive_result",
                "tags": tags,
                "statement": "Development forecast passes registered comparisons"
                if admitted
                else "Development forecast fails at least one registered comparison",
                "validity": issued,
                "conditions": "weekday 07:00-21:00 UTC; exact matched completed quotes",
                "regime_evidence": model["conditions"],
                "supporting": good,
                "opposing": [k for k in contrasts if k not in good]
                + ["no independent prospective replication"],
                "uncertainty": {
                    k: v["ci95"] + [v["lower_corrected"]] for k, v in contrasts.items()
                },
                "experiment_ids": [
                    result["protocol_sha256"][:16] + "/" + target + "/" + group
                ],
                "source": sources,
                "sample": model["rows"],
            }
    for e in phase2["experiments"]:
        yield {
            "id": "phase2/" + e["id"],
            "type": "descriptive_result",
            "tags": ["gold", e["family"], "prior_rejection"],
            "statement": e["conclusion"],
            "validity": e["windows"],
            "conditions": e["hypothesis"],
            "supporting": ["reported validation and stress tests"],
            "opposing": ["single historical feed"],
            "uncertainty": e["validation"]["lower_daily_r"],
            "experiment_ids": [e["id"]],
            "source": ["results.json"],
        }
    for case in language["models"].get(language["selected"], {}).get("tasks", []):
        if "answer" not in case:
            continue
        yield {
            "id": "reader/" + case["case"],
            "type": "unverified_interpretation",
            "tags": ["language", case["case"]],
            "statement": case["answer"]["reason"],
            "validity": "one seven-case evaluation",
            "conditions": "constrained research-methods task",
            "supporting": ["structured model answer"],
            "opposing": ["language output is not a market observation"],
            "uncertainty": {"rubric_points": case["score"], "maximum": 3},
            "experiment_ids": [language["selected"] + "/" + case["case"]],
            "source": ["researcher_results.json"],
        }


def build(db):
    result = json.loads(RESULT.read_bytes())
    language = json.loads(OUT.read_bytes())
    phase2 = json.loads((HERE / "results.json").read_bytes())
    db.execute(
        "CREATE TABLE IF NOT EXISTS predictive_knowledge (id TEXT, fingerprint TEXT, payload TEXT, PRIMARY KEY(id,fingerprint))"
    )
    graph = KnowledgeGraph()
    with db:
        for row in records(result, language, phase2):
            payload = json.dumps(row, sort_keys=True, allow_nan=False)
            fingerprint = hashlib.sha256(payload.encode()).hexdigest()
            db.execute(
                "INSERT OR IGNORE INTO predictive_knowledge VALUES(?,?,?)",
                (row["id"], fingerprint, payload),
            )
    for (payload,) in db.execute(
        "SELECT payload FROM predictive_knowledge WHERE rowid IN "
        "(SELECT max(rowid) FROM predictive_knowledge GROUP BY id) ORDER BY id"
    ):
        row = json.loads(payload)
        nodeid = (
            "lesson:"
            + row["id"]
            + ":"
            + hashlib.sha256(payload.encode()).hexdigest()[:12]
        )
        graph.add_node(GraphNode(nodeid, "Lesson", row))
        for kind, values in (
            ("condition", row["tags"]),
            ("experiment", row["experiment_ids"]),
            ("source", row["source"]),
        ):
            for value in values:
                key = kind + ":" + value
                graph.add_node(GraphNode(key, kind, {"name": value}))
                graph.add_relation(GraphRelation(nodeid, key, "has_" + kind))
    return graph


def retrieve(graph, tags, regime=None):
    if not tags:
        return []
    nodes = graph.get_neighbors("condition:" + tags[0], "has_condition")
    found = []
    for n in nodes:
        if not all(t in n.properties["tags"] for t in tags):
            continue
        row = dict(n.properties)
        if regime is not None:
            if regime not in row.get("regime_evidence", {}):
                continue
            row["matched_regime"] = {regime: row["regime_evidence"][regime]}
        found.append(row)
    return found


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("tags", nargs="*")
    parser.add_argument(
        "--regime",
        choices=[
            "post_cpi_hour",
            "recent_vol_above_4h_rate",
            "recent_vol_below_or_equal",
        ],
    )
    args = parser.parse_args()
    db = database(CACHE / "memory.sqlite")
    try:
        g = build(db)
        PRIVATE.mkdir(parents=True, exist_ok=True)
        GraphRepository().save(g, PRIVATE / "knowledge_graph.json")
        if args.tags:
            print(json.dumps(retrieve(g, args.tags, args.regime), indent=2))
        else:
            print(
                db.execute(
                    "SELECT count(DISTINCT id) FROM predictive_knowledge"
                ).fetchone()[0],
                "knowledge records",
            )
    finally:
        db.close()

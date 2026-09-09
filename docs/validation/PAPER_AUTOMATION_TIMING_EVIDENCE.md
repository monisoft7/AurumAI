# Paper automation timing evidence

The strategy baseline and both workflow schedules are unchanged. This repair
normalizes checkout paths before subprocess use and requires
`decision_timestamp <= created_at_utc < entry_time < exit_time <= evaluated_at_utc`
for completed outcomes, including historical outcome integrity checks. Late or
missing creation timestamps invalidate completed historical observations and
force NO_GO; they are never repaired by moving the entry to a later session.

For live-paper, the workflow reads its run creation time from the GitHub Actions
API using read-only Actions permission. The run ID, attempt number, run URL and
run creation timestamp are copied into the prediction manifest. A separate
`run-manifest.json` artifact binds the same reference and baseline/harness SHAs
to the prediction ID and SHA-256. The attempt number distinguishes reruns;
GitHub's run creation timestamp refers to the original run, not the rerun start.

These values let a reviewer cross-check the referenced run against GitHub and
verify which prediction bytes the uploaded artifact describes. Run creation is
not prediction publication: it may precede the prediction by minutes or days.
The local creation timestamp, copied API fields, and hash are not a signed
external timestamp or proof that the prediction was saved before entry. A
stronger guarantee needs an independently retained receipt binding the exact
prediction hash to a server-observed publication time before entry. No such
receipt or independent attestation is claimed here. Artifact upload or ledger
publication can also fail; run success and publication must be checked separately.

Dry-run skips Telegram in both the workflow and the sender CLI. Live-paper uses
an always condition for success/failure notifications and can format a failure
message when no summary exists (provided the harness and Python are available).
Notification failure remains nonfatal. No workflow is enabled by these edits.

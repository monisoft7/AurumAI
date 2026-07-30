# Governance

**File**: `11_GOVERNANCE.md`
**Owner**: Founder / CTO
**Authority**: Governing authority for all AOS processes and lifecycle. Subordinate only to `00_PROJECT_CONSTITUTION.md` on matters of identity and immutable principle.
**Review Cycle**: Quarterly, or when a governance failure is identified
**Modification**: See Section 5 (Change Control)

---

## 1. Purpose

This document defines how the AOS governs itself. It establishes the authority hierarchy, document and decision lifecycles, conflict resolution, change control, onboarding, review checkpoints, documentation dependencies, versioning, and a mandatory governance checklist. It ensures that the AOS remains self-consistent, auditable, and resilient across years of evolution and across any number of human or AI contributors.

No document in the AOS may contradict this document on matters of process. If a document describes a process that conflicts with this document, this document prevails.

## 2. What Belongs Here

- Authority hierarchy of all AOS documents
- Lifecycle definitions for documents and decisions
- Conflict resolution rules
- Change control rules and thresholds
- Mandatory onboarding sequence
- Mandatory review checkpoints before new work
- Documentation dependency map
- Versioning policy
- Governance checklist for AI contributors

## 3. What Is Forbidden

- Project identity or values (belong in `00_PROJECT_CONSTITUTION.md`)
- Strategic direction (belongs in `01_PROJECT_NORTH_STAR.md`)
- Architecture principles or constraints (belong in `03_ARCHITECTURE_AUTHORITY.md`)
- Engineering practices (belong in `06_ENGINEERING_RULES.md`)
- Implementation details or code
- Specific decisions (belong in `05_DECISIONS.md`)

---

## 4. Authority Hierarchy

### 4.1 Tier Definitions

All AOS documents are organized into tiers. Higher tiers prevail over lower tiers. Within the same tier, lower-numbered documents prevail.

| Tier | Documents | Scope |
|------|-----------|-------|
| 0 | `00_PROJECT_CONSTITUTION.md` | Immutable identity, values, supreme authority |
| 1 | `11_GOVERNANCE.md` | Process authority, lifecycle, change control |
| 2 | `03_ARCHITECTURE_AUTHORITY.md` | Technical principle authority |
| 3 | `06_ENGINEERING_RULES.md` | Execution authority |
| 4 | `01_PROJECT_NORTH_STAR.md`, `02_PROJECT_STATE.md`, `04_ROADMAP.md`, `05_DECISIONS.md`, `07_GLOSSARY.md`, `08_ONBOARDING.md`, `09_CONTEXT.md`, `10_NEXT_ACTION.md` | Domain-specific authority within document scope |

### 4.2 Conflict Between Tiers

When two documents disagree:
1. Higher tier prevails regardless of content
2. Within same tier, lower numeric prefix prevails
3. Within same tier and same prefix, the more specific document prevails over the more general
4. If ambiguity remains, the conflict is escalated to the Founder for resolution
5. The resolution is recorded in `05_DECISIONS.md`

### 4.3 Example Conflict Resolutions

- If `06_ENGINEERING_RULES.md` contradicts `03_ARCHITECTURE_AUTHORITY.md`: Architecture prevails (Tier 2 vs Tier 3)
- If `04_ROADMAP.md` contradicts `02_PROJECT_STATE.md`: No conflict possible — they describe different domains. If factual inconsistency, state document prevails (observed reality over plan)
- If `01_PROJECT_NORTH_STAR.md` contradicts `00_PROJECT_CONSTITUTION.md`: Constitution prevails (Tier 0 vs Tier 4)

### 4.4 Scope Boundaries

A document may only exercise authority within the scope defined in its "What Belongs Here" section. A document that makes a claim outside its scope has no authority for that claim. Scope disputes are resolved by the same tier hierarchy.

---

## 5. Document Lifecycle

### 5.1 States

Every AOS document passes through the following states. Each state defines who may modify the document and what actions are permitted.

```
Draft → Review → Approved → Active → Frozen → Deprecated → Archived
```

### 5.2 State Definitions

| State | Definition | Who May Modify | Transition Trigger |
|-------|------------|----------------|-------------------|
| **Draft** | Document is being created. Not yet authoritative. | Author only | Author submits for review |
| **Review** | Document is under review by designated reviewers. | No one (comments only) | Reviewer completes review or review period expires |
| **Approved** | Document is approved but not yet in effect. | Owner only (for corrections) | Approval authority signs off |
| **Active** | Document is in effect and authoritative. | Per change control rules (Section 6) | Approval notification issued |
| **Frozen** | Document is locked. No changes permitted except for critical corrections. | Owner only, with Founder approval | Time-based freeze or pre-implementation freeze |
| **Deprecated** | Document is superseded. Still readable for history but not authoritative. | No one | Replacement document enters Active state |
| **Archived** | Document is historical only. Removed from active AOS directory. | No one | Deprecation period expires (minimum 90 days) |

### 5.3 State Transitions

1. **Draft → Review**: Author submits draft with a review request. Reviewers are assigned based on document scope.
2. **Review → Approved**: All reviewers approve, or the review period (default 7 days) expires with no objections.
3. **Approved → Active**: The document owner publishes the approval notification. The document is now binding.
4. **Active → Frozen**: A freeze may be declared by the Founder or by a 2/3 vote of core contributors. Freeze is used before major milestones or when stability is required.
5. **Active/Freeze → Deprecated**: A replacement document enters Active state, or the Founder declares the document no longer needed.
6. **Deprecated → Archived**: A document moves to archived state after 90 days in deprecated state. Archived documents are moved to `AOS/_archived/`.

### 5.4 Emergency Override

In case of an identified error that could cause harm, the Founder may move a document directly from Active to Frozen with immediate effect, bypassing normal transition rules. The rationale must be recorded in `05_DECISIONS.md` within 24 hours.

---

## 6. Decision Lifecycle

### 6.1 States

Every decision in `05_DECISIONS.md` follows this lifecycle:

```
Proposed → Reviewed → Accepted → Implemented → Validated → Frozen → Superseded
```

### 6.2 State Definitions

| State | Definition | Requirements |
|-------|------------|-------------|
| **Proposed** | Decision is drafted but not yet evaluated | Must follow decision template from `05_DECISIONS.md` |
| **Reviewed** | Decision has been reviewed by at least one competent reviewer | Review comments documented |
| **Accepted** | Decision is approved and binding | Approval authority signs off |
| **Implemented** | The decision has been executed | Evidence of implementation attached |
| **Validated** | The decision produced the expected outcome | Validation evidence attached |
| **Frozen** | Decision is final and will not be revisited | No further action expected |
| **Superseded** | Decision has been replaced by a newer decision | Reference to superseding decision |

### 6.3 Minimum Review Thresholds

| Decision Type | Required Reviewers | Approver |
|---------------|-------------------|----------|
| Architecture decision | ARB (minimum 2) | Architecture Lead |
| Strategic decision | All core contributors | Founder |
| Process decision | Core contributor + 1 reviewer | Governance Owner |
| Tactical decision | 1 reviewer | Technical Lead |
| Knowledge base addition | 1 domain reviewer | Knowledge Engineer |

### 6.4 Decision Freeze

A decision in Frozen state may only be revisited if:
1. New evidence emerges that was not available at the time of the decision
2. The assumptions underlying the decision have been invalidated
3. The Founder authorizes the review

In all cases, the new deliberation begins as a new Proposed decision. The original decision remains Frozen for historical reference.

---

## 7. Conflict Resolution (Detailed)

### 7.1 Document Conflicts

When two AOS documents conflict:

1. **Identify tiers**: Apply the hierarchy from Section 4.1
2. **Higher tier prevails**: If tiers differ, the higher tier document wins
3. **Same tier, lower number prevails**: If tiers match, lower prefix wins
4. **Same tier, same number**: The document with the more specific scope wins
5. **Scope violation**: If a document makes a claim outside its defined scope, that claim has no authority. The conflict is resolved by ignoring the out-of-scope claim.
6. **Tie**: If all rules produce a tie, escalate to the Founder. The resolution is recorded in `05_DECISIONS.md`.

### 7.2 Document vs Decision Conflict

When a document and a logged decision conflict:
- The document prevails (documents are authoritative, decisions are records)
- The conflicting decision must be reviewed and either reconciled or marked as Superseded

### 7.3 Practice vs Document Conflict

When an established practice conflicts with a document:
- The document prevails (per the constitution, no unwritten rule exists)
- The practice must be ceased or the document must be amended

### 7.4 Conflict Prevention

Before any document is approved, a conflict scan must be performed against all Active documents. Conflicts must be resolved before the document can enter Active state. This is the responsibility of the document author.

---

## 8. Change Control

### 8.1 Who May Propose Changes

Any contributor may propose a change to any AOS document. Proposals must be:
- In writing (pull request or issue)
- Accompanied by rationale
- Tagged with the document's tier

### 8.2 Change Thresholds by Tier

| Tier | Example | Review Required | Approval Required | Authorized Approvers |
|------|---------|-----------------|-------------------|---------------------|
| 0 | Constitution | All core contributors | Founder + 2/3 core | Founder |
| 1 | Governance | All core contributors | Founder | Founder |
| 2 | Architecture | ARB (min 2) | Architecture Lead | Architecture Lead |
| 3 | Engineering Rules | Engineering team (min 2) | Engineering Lead | Engineering Lead |
| 4 | All others | 1 domain reviewer | Document Owner | Document Owner |

### 8.3 What May Never Be Changed Without Constitutional Review

The following principles from `00_PROJECT_CONSTITUTION.md` may never be changed without a full constitutional amendment:

- Section 5.1 (Clarity Over Cleverness)
- Section 5.3 (Authority Through Documents)
- Section 5.5 (Defensive by Default)
- Section 5.6 (Separation of Concerns)
- The existence of the AOS itself

Any attempt to modify these principles follows the amendment process in Constitution Section 9, plus an additional 14-day review period.

### 8.4 Emergency Changes

In emergencies (identified error, security issue, or compliance risk):
1. The Founder may directly modify any document
2. The document must be marked with `EMERGENCY MODIFICATION` and the date
3. Within 7 days, a standard change process must be completed to confirm or revert the change
4. The emergency must be logged in `05_DECISIONS.md`

### 8.5 Change Log Requirements

Every modification to an AOS document must be recorded in the document's change log with:
- Date of change
- Brief description
- Author of change
- Reference to the relevant decision in `05_DECISIONS.md` if applicable

---

## 9. Mandatory Onboarding Sequence

### 9.1 Required Reading Order

Every new contributor — human or AI — must complete the following sequence before making any contribution:

**Phase 1: Foundation (required, must complete in order)**
1. `00_PROJECT_CONSTITUTION.md` — Understand the supreme governing principles
2. `11_GOVERNANCE.md` — Understand how the AOS governs itself
3. `07_GLOSSARY.md` — Learn the project vocabulary

**Phase 2: Context (required, may read in any order)**
4. `01_PROJECT_NORTH_STAR.md` — Understand the mission and vision
5. `09_CONTEXT.md` — Understand the external environment
6. `02_PROJECT_STATE.md` — Understand current project reality

**Phase 3: Rules (required, may read in any order)**
7. `03_ARCHITECTURE_AUTHORITY.md` — Understand design constraints
8. `06_ENGINEERING_RULES.md` — Understand execution standards

**Phase 4: Operations (required before contributing)**
9. `10_NEXT_ACTION.md` — Understand immediate priorities
10. `04_ROADMAP.md` — Understand the strategic plan
11. `05_DECISIONS.md` — Understand past decisions
12. `08_ONBOARDING.md` — Understand setup and contribution process

### 9.2 Verification

After completing the reading sequence, the contributor must:
1. Acknowledge in writing that they have read all documents
2. Confirm they understand the governance rules
3. Complete the Governance Checklist (Section 13)

### 9.3 AI-Specific Onboarding

AI contributors must additionally:
1. Read `08_ONBOARDING.md` Section 4 (Reading Order) to confirm document access
2. Execute the Governance Checklist (Section 13) as their first action
3. Verify that `02_PROJECT_STATE.md` and `10_NEXT_ACTION.md` are current
4. Never assume context from prior sessions not recorded in this AOS

---

## 10. Mandatory Review Checkpoints

Before any new work begins — including a new session, a new task, or a new decision — the following checkpoints must be completed:

### 10.1 Pre-Work Checklist

- [ ] **State Review**: `02_PROJECT_STATE.md` has been read and the current state is understood
- [ ] **Next Action Review**: `10_NEXT_ACTION.md` has been read and the immediate priority is confirmed
- [ ] **Decision Scan**: `05_DECISIONS.md` has been scanned for decisions relevant to the proposed work
- [ ] **Document Lifecycle Check**: All documents relevant to the proposed work are in Active state (not Frozen, Deprecated, or Archived)
- [ ] **Conflict Check**: No unresolved conflicts exist between documents relevant to the proposed work
- [ ] **Governance Checklist**: The Governance Checklist (Section 13) has been completed
- [ ] **North Star Alignment**: The proposed work is consistent with `01_PROJECT_NORTH_STAR.md`

### 10.2 When Checkpoints Are Required

| Scenario | Checkpoints Required |
|----------|---------------------|
| New session (human or AI) | All |
| New task within same session | State Review, Next Action Review, Governance Checklist |
| New decision | All + Decision Scan mandatory |
| New document or major revision | All + Conflict Check mandatory |

### 10.3 Checkpoint Failure

If any checkpoint fails:
- The work must not begin until the failure is resolved
- The failure must be documented in `10_NEXT_ACTION.md`
- If the failure indicates a governance gap, `11_GOVERNANCE.md` must be reviewed

---

## 11. Documentation Dependencies

### 11.1 Dependency Map

Each document depends on the documents listed below. A dependent document must be reviewed when its dependency changes.

| Document | Depends On | Nature of Dependency |
|----------|------------|---------------------|
| `00_CONSTITUTION` | None (supreme) | — |
| `11_GOVERNANCE` | `00_CONSTITUTION` | Derives process authority from constitution |
| `01_NORTH_STAR` | `00_CONSTITUTION` | Must align with identity and values |
| `02_PROJECT_STATE` | `00_CONSTITUTION`, `01_NORTH_STAR` | Measures progress toward North Star |
| `03_ARCHITECTURE` | `00_CONSTITUTION`, `01_NORTH_STAR`, `11_GOVERNANCE` | Design principles derive from mission and process |
| `04_ROADMAP` | `01_NORTH_STAR`, `02_PROJECT_STATE`, `11_GOVERNANCE` | Plans must align with mission and current state |
| `05_DECISIONS` | `11_GOVERNANCE` | Decision lifecycle governed by this document |
| `06_ENGINEERING_RULES` | `00_CONSTITUTION`, `03_ARCHITECTURE` | Rules must align with architecture |
| `07_GLOSSARY` | All documents | Terms used across all documents |
| `08_ONBOARDING` | All documents | Reading order references all documents |
| `09_CONTEXT` | `00_CONSTITUTION`, `01_NORTH_STAR` | Context informs mission and decisions |
| `10_NEXT_ACTION` | `02_PROJECT_STATE`, `04_ROADMAP` | Next action depends on state and plan |

### 11.2 Dependency Rules

1. When a document is modified, all documents that depend on it must be reviewed for consistency
2. The dependency review is the responsibility of the modifying author
3. If a dependency review reveals a needed change, that change follows the normal change control process
4. Documents with no dependents (leaf nodes) may be modified without downstream impact

### 11.3 Circular Dependency Prevention

No circular dependencies are permitted. If a circular dependency is discovered:
1. The cycle must be broken by removing one dependency
2. The document with the lower tier retains the dependency
3. The resolution is recorded in `05_DECISIONS.md`

---

## 12. Versioning Policy

### 12.1 Document Versioning

Every AOS document carries a version number in the format `MAJOR.MINOR-PATCH`.

| Component | Criteria | Example |
|-----------|----------|---------|
| MAJOR | Structural reorganization, principle change, or scope change | 1.0 → 2.0 |
| MINOR | New sections, new rules, significant clarification | 1.0 → 1.1 |
| PATCH | Typo, formatting, minor clarification, change log entry | 1.0 → 1.0-1 |

### 12.2 Version Location

The version number appears at the top of each document, below the title, in the format:

```
**Version**: MAJOR.MINOR-PATCH (YYYY-MM-DD)
```

### 12.3 AOS-Level Versioning

The AOS as a whole carries a version number that is the maximum of all individual document MAJOR versions.

Example: If `00_CONSTITUTION` is at 1.2 and `03_ARCHITECTURE` is at 2.1, the AOS version is 2.

### 12.4 Breaking vs Non-Breaking Changes

| Change Type | Version Bump | Notification |
|-------------|-------------|--------------|
| New document added | New MINOR version | All contributors notified |
| Document deprecated | MAJOR bump on deprecating document | All contributors notified |
| Document archived | MAJOR version on AOS | All contributors notified |
| Principle change | MAJOR version on affected document | Constitutional review required |
| New section | MINOR version | Document owner notified |
| Clarification, typo | PATCH | No notification required |

### 12.5 Change Log

Every document maintains a change log in its final section. Each entry includes:
- Date of change
- Version after change
- Description of change
- Author

---

## 13. Governance Checklist

This checklist must be completed by any AI contributor before making recommendations, executing tasks, or proposing decisions. It ensures that the AI has sufficient context to operate within the AOS framework.

### 13.1 Context Verification

- [ ] Have I read `00_PROJECT_CONSTITUTION.md` and understood the supreme principles?
- [ ] Have I read `11_GOVERNANCE.md` and understood the governance rules?
- [ ] Have I read `07_GLOSSARY.md` and confirmed I understand the project vocabulary?
- [ ] Have I read `02_PROJECT_STATE.md` and understood the current project state?
- [ ] Have I read `10_NEXT_ACTION.md` and understood the immediate priority?

### 13.2 Scope Verification

- [ ] Is the task I am about to perform within my defined authority?
- [ ] Am I making decisions that should be logged in `05_DECISIONS.md`?
- [ ] Am I staying within my document scope boundaries (no architecture advice if I am not architecture-authorized)?

### 13.3 Consistency Verification

- [ ] Is my proposed action consistent with `00_PROJECT_CONSTITUTION.md`?
- [ ] Is my proposed action consistent with `01_PROJECT_NORTH_STAR.md`?
- [ ] Is my proposed action consistent with `03_ARCHITECTURE_AUTHORITY.md` (if applicable)?
- [ ] Is my proposed action consistent with `06_ENGINEERING_RULES.md` (if applicable)?
- [ ] Have I checked `05_DECISIONS.md` for relevant precedent decisions?

### 13.4 Lifecycle Verification

- [ ] Are all documents relevant to my task in Active state?
- [ ] If I am proposing a change, am I following the correct change control process?
- [ ] If I am proposing a decision, am I following the correct decision lifecycle?

### 13.5 Dependency Verification

- [ ] Have I identified all documents that depend on the documents I am modifying?
- [ ] Have I reviewed those dependent documents for consistency?

### 13.6 Final Confirmation

- [ ] I confirm that I have completed this checklist.
- [ ] I confirm that I am operating within the AOS governance framework.
- [ ] I confirm that if I am unsure about any governance rule, I will ask rather than assume.

---

## 14. Relationship to External Documents

### 14.1 External Standards

This project may adopt external standards (ISO standards, RFCs, industry conventions). When adopted:
1. The adoption must be recorded in `05_DECISIONS.md`
2. The external standard is subordinate to all AOS documents
3. Where the external standard conflicts with an AOS document, the AOS document prevails
4. The external standard should be referenced in `07_GLOSSARY.md`

### 14.2 Non-AOS Project Documents

Documents outside the AOS (such as domain knowledge bases, methodology documents, and technical specifications) are governed by the AOS but do not govern the AOS. They follow their own lifecycles as defined in their respective documents, within the constraints of the AOS.

---

## 15. Change Log

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2026-07-29 | 1.0 | Initial governance document | Founder |
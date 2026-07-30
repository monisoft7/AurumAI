# Decisions

**File**: `05_DECISIONS.md`
**Owner**: Engineering Team (collective)
**Update Frequency**: Whenever a decision of significance is made
**Modification**: Any contributor may add a decision. Retroactive modification of a logged decision is forbidden; corrections are new entries.

---

## 1. Purpose

This document is the permanent, immutable log of every significant decision made during the project's life. It answers "why did we do it this way?" and prevents the loss of context that occurs when decisions are made verbally, in chat threads, or in meetings. Together with `03_ARCHITECTURE_AUTHORITY.md`, it forms the complete record of the project's intellectual history.

## 2. What Belongs Here

- Architecture decisions and their rationale
- Strategic pivots and their triggers
- Technology selections with alternatives considered
- Methodology changes with justification
- Any decision that, if forgotten, would cause future confusion or rework
- Decisions to NOT do something (equally important)

## 3. What Is Forbidden

- Speculative or hypothetical discussions
- Personal opinions or preferences not grounded in evidence
- Implementation details that belong in code or `06_ENGINEERING_RULES.md`
- Information that belongs in other AOS documents

## 4. Decision Template

Every decision entry must follow this structure:

```
### D-YYYYMMDD-NNN: Title

**Status**: [Proposed | Accepted | Deprecated | Rejected]
**Author**: [Name]
**Date**: [YYYY-MM-DD]
**Reviewed By**: [Names]

#### Context
What prompted this decision? What problem does it solve?

#### Options Considered
1. Option A — pros, cons
2. Option B — pros, cons
3. Option C — pros, cons

#### Decision
What was chosen and why.

#### Consequences
What does this decision enable? What does it foreclose?

#### References
- Related AOS documents
- Related decisions
- External sources
```

## 5. Decision Lifecycle

1. **Proposed** — Decision is drafted but not yet adopted
2. **Accepted** — Decision is adopted and binding
3. **Deprecated** — Decision is superseded but still recorded for history
4. **Rejected** — Decision was considered and explicitly not adopted

## 6. Current Decisions

### D-20260729-001: Project Reset to Knowledge Engineering

**Status**: Accepted
**Author**: Founder
**Date**: 2026-07-29
**Reviewed By**: N/A (founder decision)

#### Context
The project was originally structured as a software implementation project. After review, the priority shifted to establishing the knowledge foundations before any code is written.

#### Options Considered
1. Continue software implementation — risk of building without adequate domain knowledge
2. Pause and build knowledge base first — ensures the system has something to reason about
3. Parallel work — splits attention and risks coherence

#### Decision
Pause all software implementation. Focus exclusively on knowledge engineering until the domain knowledge base and methodology are complete.

#### Consequences
- Delays software implementation but ensures it is built on solid foundations
- Knowledge base becomes the authoritative source for all future implementation
- AOS is established to govern the reset

#### References
- `00_PROJECT_CONSTITUTION.md`
- `01_PROJECT_NORTH_STAR.md`
- `09_CONTEXT.md`

### D-20260729-002: AOS Document Structure

**Status**: Accepted
**Author**: Founder
**Date**: 2026-07-29
**Reviewed By**: N/A (founder decision)

#### Context
The project needed a structured way to preserve context across sessions, agents, and contributors.

#### Options Considered
1. Single monolithic document — simple but hard to navigate and maintain
2. Directory of specialized documents — more complex but each document has clear ownership
3. Wiki or database — too heavy for the current phase

#### Decision
Use a directory of 10 specialized Markdown documents with a numbered prefix convention. Each document has a clear purpose, owner, and modification rules.

#### Consequences
- Clear separation of concerns
- Easy for newcomers to find relevant information
- Scales naturally as the project grows

#### References
- `00_PROJECT_CONSTITUTION.md`
- `08_ONBOARDING.md`

## 7. Decision Index

| ID | Title | Status | Date |
|----|-------|--------|------|
| D-20260729-001 | Project Reset to Knowledge Engineering | Accepted | 2026-07-29 |
| D-20260729-002 | AOS Document Structure | Accepted | 2026-07-29 |

## 8. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-07-29 | Initial decision log | Founder |
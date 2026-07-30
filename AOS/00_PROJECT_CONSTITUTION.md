# Project Constitution

**File**: `00_PROJECT_CONSTITUTION.md`
**Owner**: Founder / CTO (inalienable)
**Authority**: Supreme. No other document may contradict this one.
**Amendment**: Requires 2/3 of active core contributors plus Founder approval. Amendments must be logged in `05_DECISIONS.md`.

---

## 1. Purpose

This document is the highest authority of the project. It defines the identity, values, governance model, and inviolable principles that guide every decision, architectural choice, and contribution. All other documents in the AOS derive their authority from this constitution.

## 2. What Belongs Here

- Core identity and purpose of the project
- Immutable principles and values
- Governance structure and decision-making authority
- Rights and responsibilities of contributors
- Amendment and succession rules
- Relationship between AOS documents

## 3. What Is Forbidden

- Implementation details, code, or technology choices
- Tactical plans, timelines, or roadmaps
- Project-specific business logic
- Any content that belongs in another AOS document
- Personal opinions or preferences

## 4. Project Identity

This project exists to build a system that achieves a clearly defined mission (see `01_PROJECT_NORTH_STAR.md`). The project operates as an engineering endeavor first — rigor, clarity, and maintainability take precedence over speed.

## 5. Immutable Principles

### 5.1 Clarity Over Cleverness
Every artifact — code, document, decision — must be understandable by a competent engineer without external context. If it cannot be explained simply, it is wrong.

### 5.2 Evidence Over Opinion
Decisions must be grounded in evidence. When evidence is incomplete, name the uncertainty explicitly. Document the rationale in `05_DECISIONS.md`.

### 5.3 Authority Through Documents
The AOS is the single source of truth. No unwritten rule exists. No oral tradition is binding. If it is not documented, it does not govern.

### 5.4 Minimal Viable Governance
Add process only when the cost of its absence exceeds the cost of its presence. Prefer lightweight conventions over heavyweight bureaucracy.

### 5.5 Defensive by Default
Assume every future reader has zero context. Assume every future AI has never seen this project before. Design all artifacts to survive context loss.

### 5.6 Separation of Concerns
Each AOS document owns a distinct domain. No document may duplicate or override the purpose of another. Cross-references are encouraged; duplication is forbidden.

## 6. Governance

### 6.1 Roles

| Role | Authority | Appointed By |
|------|-----------|-------------|
| Founder / CTO | Final authority on all matters | N/A (original) |
| Core Contributor | Vote on amendments, own subsystems | Founder |
| Contributor | Submit changes per engineering rules | Self (with approval) |

### 6.2 Decision Hierarchy

1. Constitution (this document) — supreme
2. Architecture Authority (`03_ARCHITECTURE_AUTHORITY.md`) — binding on all technical decisions
3. Engineering Rules (`06_ENGINEERING_RULES.md`) — binding on all implementation
4. All other AOS documents — binding within their scope
5. Decisions (`05_DECISIONS.md`) — binding record of past decisions
6. External standards (RFCs, ISO standards, industry conventions) — advisory unless explicitly adopted

### 6.3 Conflict Resolution

When two AOS documents conflict, the document with the lower-numbered prefix prevails. When a document and a decision conflict, the document prevails. When a decision and unwritten practice conflict, the decision prevails.

## 7. Rights and Responsibilities

Every contributor has the right to:
- Access any AOS document
- Propose amendments per the amendment process
- Be informed of decisions that affect their work

Every contributor has the responsibility to:
- Read the relevant AOS documents before contributing
- Update `02_PROJECT_STATE.md` when their work changes project state
- Log decisions in `05_DECISIONS.md`
- Keep the glossary (`07_GLOSSARY.md`) accurate

## 8. AOS Document Map

```
00_CONSTITUTION        ── governs all
01_NORTH_STAR          ── defines direction
02_PROJECT_STATE       ── describes current reality
03_ARCHITECTURE        ── constrains design
04_ROADMAP             ── plans the journey
05_DECISIONS           ── records rationale
06_ENGINEERING_RULES   ── sets standards
07_GLOSSARY            ── defines terms
08_ONBOARDING          ── guides newcomers
09_CONTEXT             ── explains the landscape
10_NEXT_ACTION         ── drives immediate steps
```

## 9. Amendment Process

1. Propose the amendment with rationale in `05_DECISIONS.md`
2. Notify all core contributors
3. Wait 7 days for discussion (emergency amendments may waive this)
4. Vote: 2/3 of core contributors plus Founder approval
5. Update this document and record the amendment in the change log below

## 10. Change Log

| Date | Amendment | Author |
|------|-----------|--------|
| 2026-07-29 | Initial constitution | Founder |
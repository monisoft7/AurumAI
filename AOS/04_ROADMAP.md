# Roadmap

**File**: `04_ROADMAP.md`
**Owner**: Founder / CTO (strategic), Technical Lead (tactical)
**Review Cycle**: Quarterly strategic review; monthly tactical check
**Modification**: Strategic changes require Founder approval. Tactical changes may be made by Technical Lead and logged in `05_DECISIONS.md`.

---

## 1. Purpose

This document defines the planned work, phases, milestones, and priorities for the project. It translates the strategic objectives from `01_PROJECT_NORTH_STAR.md` into actionable phases and connects them to the current state described in `02_PROJECT_STATE.md`. It does not prescribe how work is done (that belongs in `06_ENGINEERING_RULES.md`) — it prescribes what work is done and in what order.

## 2. What Belongs Here

- High-level phases and their objectives
- Milestones with success criteria
- Priority framework for sequencing work
- Dependencies between work items
- Release criteria and versioning philosophy
- Risk-adjusted timeline (ranges, not dates)

## 3. What Is Forbidden

- Daily or weekly task assignments (belong in `10_NEXT_ACTION.md`)
- Implementation details or technical specifications
- Individual assignments or performance evaluation
- Detailed engineering process (belongs in `06_ENGINEERING_RULES.md`)
- Fixed dates — timelines are ranges

## 4. Priority Framework

All work is prioritized by:
1. **Foundation** — Work that unblocks everything else
2. **Core** — Work that directly delivers North Star objectives
3. **Enhancement** — Work that improves quality, speed, or experience
4. **Exploration** — Work that investigates future possibilities

Within each tier, work is ordered by dependency: if A blocks B, A comes first regardless of tier.

## 5. Phases

### Phase 0: Foundation (Current)
**Objective**: Establish the project's operating system and domain knowledge foundations.
**Success Criteria**:
- AOS is complete and self-consistent
- Domain knowledge base meets minimum volume target
- Methodology documents are complete

### Phase 1: Core Architecture
**Objective**: Design and validate the core architecture.
**Success Criteria**:
- Architecture is documented and reviewed
- Core inference engine design is complete
- Audit layer design is complete
- Domain plug-in interface is specified

### Phase 2: Implementation
**Objective**: Build the first working system.
**Success Criteria**:
- Knowledge base is integrated into the system
- At least one full reasoning path works end-to-end
- Audit trail is generated for every decision

### Phase 3: Validation and Iteration
**Objective**: Validate against domain experts and real-world scenarios.
**Success Criteria**:
- System outputs are reviewed by domain experts
- Methodology is refined based on validation
- Knowledge gaps are identified and filled

### Phase 4: Expansion
**Objective**: Add additional domains and capabilities.
**Success Criteria**:
- Second domain knowledge base is created
- Plug-in architecture is validated
- Cross-domain reasoning works

## 6. Milestones

| Milestone | Phase | Success Criteria |
|-----------|-------|-----------------|
| AOS Complete | 0 | All 10 documents are internally consistent, cross-referencing, and pass review |
| Knowledge Base Target | 0 | 300+ validated knowledge records |
| Architecture Review | 1 | Architecture document passes ARB review |
| First End-to-End Decision | 2 | System produces a fully auditable decision from a query |
| Domain Expert Validation | 3 | At least 3 domain experts confirm system outputs are sound |
| Second Domain Added | 4 | Complete knowledge base for a second domain |

## 7. Dependency Map

```
Phase 0 (Foundation)
  └──> Phase 1 (Architecture)
         └──> Phase 2 (Implementation)
                └──> Phase 3 (Validation)
                       └──> Phase 4 (Expansion)
```

Phase 0 and Phase 1 may overlap partially. Phases 2-4 are strictly sequential.

## 8. Versioning

This project uses semantic milestones, not semantic versions, until a working system exists. Once the system is operational, releases follow MAJOR.MINOR.PATCH:
- MAJOR: Architecture change or breaking capability change
- MINOR: New capability or methodology addition
- PATCH: Bug fix, knowledge base addition, documentation update

## 9. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-07-29 | Initial roadmap | Founder |
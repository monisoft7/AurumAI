# Project North Star

**File**: `01_PROJECT_NORTH_STAR.md`
**Owner**: Founder / CTO
**Review Cycle**: Annually, or when market conditions fundamentally shift
**Modification**: Requires consensus among core contributors. All changes must be logged in `05_DECISIONS.md`.

---

## 1. Purpose

This document defines the long-term vision, mission, and strategic objectives of the project. It answers "why does this project exist?" and "what does success look like?" Every decision in `05_DECISIONS.md`, every milestone in `04_ROADMAP.md`, and every architectural choice in `03_ARCHITECTURE_AUTHORITY.md` must be traceable to this North Star.

## 2. What Belongs Here

- Vision statement (10+ year aspiration)
- Mission statement (what we do and for whom)
- Core strategic objectives (3-5 high-level goals)
- Definition of success and key results
- Non-goals (explicit statements of what we will not pursue)
- Values that guide strategic trade-offs

## 3. What Is Forbidden

- Implementation plans, timelines, or milestones
- Technical architecture decisions
- Specific technologies or tools
- Competitive analysis (belongs in `09_CONTEXT.md`)
- Operational metrics or project state (belongs in `02_PROJECT_STATE.md`)

## 4. Vision

To become the definitive institutional-grade reasoning system in its domain — trusted by decision-makers who require precision, transparency, and rigor above all else.

## 5. Mission

Build a system that ingests structured and unstructured information, applies institutional-quality reasoning frameworks, and produces decisions that are auditable, repeatable, and explainable. The system must outperform ad-hoc human judgment in consistency and transparency.

## 6. Strategic Objectives

### 6.1 Epistemic Rigor
Every output must explicitly state its confidence, evidence, assumptions, and failure conditions. The system must be able to say "I don't know" and explain why.

### 6.2 Institutional Transparency
Every decision path must be fully auditable. A reviewer must be able to trace from raw input to final output and understand every transformation along the way.

### 6.3 Domain Authority
The system must encode and maintain the full depth of institutional knowledge in its domain. The knowledge base (`Institutional_Gold_Knowledge_Base.md`) is the canonical source and must be continuously expanded and validated.

### 6.4 Adaptability
The architecture must allow new domains, new data sources, and new reasoning frameworks to be added without restructuring the core system.

## 7. Non-Goals

- Consumer-facing applications or retail users
- Real-time trading or execution
- Replacing human judgment entirely — the system is an advisor, not an autonomous agent
- General-purpose AI — the system is domain-specific by design

## 8. Definition of Success

The project is successful when:

1. A domain expert can query the system and receive a fully auditable decision with evidence chain
2. A new engineer can understand the full system by reading the AOS and domain documents
3. The system surfaces its own uncertainty before being asked
4. Decisions are consistent across different users and contexts (same inputs produce same outputs)
5. External auditors can validate the reasoning without access to the original authors

## 9. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-07-29 | Initial North Star | Founder |
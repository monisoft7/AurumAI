# Context

**File**: `09_CONTEXT.md`
**Owner**: Founder / CTO
**Review Cycle**: Updated when significant external events affect the project, or quarterly
**Modification**: Founder approves. Core contributors may propose updates.

---

## 1. Purpose

This document captures the external context in which the project operates. It answers "why does this project exist in this specific form?" and "what external forces shape its priorities?" It bridges the internal project documents (the rest of the AOS) with the external world. Understanding this context is essential before making any strategic or architectural decision.

## 2. What Belongs Here

- The problem the project was created to solve
- Market and industry landscape
- Competitive landscape and alternatives
- Key external constraints (regulatory, technological, organizational)
- Key assumptions about the external environment
- Risks and opportunities from external changes
- Historical context that shaped current direction

## 3. What Is Forbidden

- Internal project state (belongs in `02_PROJECT_STATE.md`)
- Strategic direction (belongs in `01_PROJECT_NORTH_STAR.md`)
- Implementation details or plans
- Speculative future scenarios without evidence

## 4. Background and Problem Statement

The project was initiated to address a specific gap: institutional-quality domain reasoning that is transparent, auditable, and consistent. Existing approaches rely on either:
- Black-box AI systems that produce outputs without auditable reasoning paths
- Manual analysis that is inconsistent across practitioners and impossible to scale
- Static rule-based systems that cannot adapt to new information or domains

The project aims to fill this gap by combining structured knowledge engineering with transparent reasoning processes.

## 5. Landscape

### 5.1 Adjacent Approaches
- **Traditional Expert Systems**: High transparency, low adaptability, high maintenance cost
- **Machine Learning Systems**: High adaptability, low transparency, high data dependency
- **Human Expert Networks**: High quality, low consistency, impossible to scale
- **Hybrid Approaches**: Emerging field, no dominant solution

### 5.2 Target Users
Decision-makers who require:
- Auditable reasoning chains for compliance or governance
- Consistent application of domain knowledge across cases
- Ability to challenge and understand every step of a decision
- Integration of diverse data sources with clear provenance

## 6. External Constraints

### 6.1 Data Constraints
- Domain data sources are heterogeneous, often proprietary, and may have licensing restrictions
- Data quality varies significantly across sources
- Some data is available only in unstructured formats

### 6.2 Knowledge Constraints
- Domain expertise is scarce and expensive
- Expert knowledge is often tacit and must be extracted through careful engineering
- Domain knowledge evolves — the system must accommodate updates

### 6.3 Operational Constraints
- Users expect decisions in interactive timeframes
- Audit trails must be exportable and machine-readable
- The system must operate within existing institutional workflows

## 7. Key Assumptions

1. **Domain knowledge can be systematically encoded.** We assume that expert knowledge in the target domain can be captured in a structured, machine-readable format. If this assumption fails, the project cannot succeed.
2. **Transparency is valuable enough to trade off raw accuracy.** We assume users value the ability to audit decisions even if it means occasionally lower predictive accuracy.
3. **The system will coexist with human experts, not replace them.** We assume the system augments rather than automates.
4. **Multi-domain expansion is feasible.** We assume the knowledge engineering process generalizes beyond the initial domain.

## 8. Competitive Context

The project does not aim to compete with general-purpose AI systems. It occupies a specific niche:
- High-stakes decisions where reasoning transparency is mandatory
- Domains with established but fragmented institutional knowledge
- Environments where "because the model said so" is not an acceptable answer

## 9. Historical Context Leading to Current Direction

The project originally began with a software-first approach. After initial review, it became clear that the knowledge foundations were insufficient to guide a coherent architecture. The decision to reset to knowledge engineering (recorded in `05_DECISIONS.md`) was based on the principle that the system's value derives from what it knows, not how it is built.

## 10. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-07-29 | Initial context document | Founder |
# Architecture Authority

**File**: `03_ARCHITECTURE_AUTHORITY.md`
**Owner**: Architecture Team Lead
**Review Cycle**: Quarterly, or when a new category of capability is added
**Modification**: Architecture Review Board (ARB) approval required. ARB consists of the Owner and at least one core contributor. All decisions logged in `05_DECISIONS.md`.

---

## 1. Purpose

This document governs all architectural decisions in the project. It defines the principles, constraints, patterns, and boundaries that every implementation must respect. Its authority is second only to `00_PROJECT_CONSTITUTION.md`. Any architecture decision not consistent with this document must be rejected or this document must be amended first.

## 2. What Belongs Here

- Architecture principles (high-level design rules)
- System boundaries and domain definitions
- Allowed and forbidden architectural patterns
- Quality attributes and their priority order
- Data flow and state management philosophy
- Integration patterns and protocol constraints
- Security and compliance principles
- Evolution and deprecation policies

## 3. What Is Forbidden

- Implementation details, code snippets, or technology-specific instructions
- Specific libraries, frameworks, or tools
- Business logic or domain rules
- Project management content (belongs in `04_ROADMAP.md`)
- Operational procedures (belongs in `06_ENGINEERING_RULES.md`)

## 4. Architecture Principles

### 4.1 Separation of Knowledge from Execution
Domain knowledge (facts, relationships, mechanisms) must be stored in declarative, inspectable documents — never embedded in code. Execution logic (inference, transformation, routing) must be stored in code — never embedded in documents. This is the single most important architectural rule.

### 4.2 Explicit Reasoning Paths
Every decision the system produces must have a fully traceable reasoning path. The architecture must support auditing as a first-class concern, not an afterthought.

### 4.3 Plug-in Domain Architecture
The system must support adding new domains without modifying the core inference engine. Each domain provides its own knowledge base, methodology, and validation rules. The core system orchestrates.

### 4.4 Confidence as a First-Class Citizen
Every output must carry a confidence score, and every confidence score must be traceable to the evidence that produced it. The architecture must represent uncertainty, not hide it.

### 4.5 Stateless Inference, Stateful Knowledge
The inference engine should be stateless — given the same knowledge and inputs, it produces the same output. State belongs in the knowledge base and in explicitly managed context stores.

### 4.6 Human-in-the-Loop for Novel Decisions
Decisions that fall outside the known knowledge base must be flagged for human review. The system must not silently extrapolate beyond its training or knowledge boundaries.

## 5. System Boundaries

### 5.1 Identified Domains (Not Exhaustive)
- Knowledge Engineering: Creating and maintaining domain knowledge bases
- Reasoning Engine: Applying knowledge to inputs to produce decisions
- Audit Layer: Recording and exposing reasoning paths
- Interface Layer: Accepting queries and presenting results

### 5.2 Cross-Cutting Concerns
- Transparency: Every component must expose its internal state for auditing
- Validation: Every component must validate its inputs and outputs against known schemas
- Telemetry: Every component must emit telemetry for state tracking (`02_PROJECT_STATE.md`)

## 6. Quality Attribute Priority

1. **Correctness** — The system must be right more often than a domain expert
2. **Transparency** — The system must be fully auditable
3. **Maintainability** — A new contributor must understand any component within one session
4. **Extensibility** — Adding a new domain must not require changes to existing domain logic
5. **Performance** — Must be fast enough for interactive use; batch processing is acceptable for heavy computations

## 7. Evolution Policy

Architecture may evolve. When it does:
1. The change must be proposed and approved via the ARB
2. The old architecture must be deprecated with a clear migration path
3. `02_PROJECT_STATE.md` must be updated to reflect the transition
4. All affected AOS documents must be updated

## 8. Technology Philosophy

- Prefer broad, stable standards over trendy frameworks
- Prefer explicit configuration over convention
- Prefer simple, readable implementations over optimized, opaque ones
- Any technology choice must be justified in `05_DECISIONS.md` with at least three alternatives considered

## 9. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-07-29 | Initial architecture authority | Founder |
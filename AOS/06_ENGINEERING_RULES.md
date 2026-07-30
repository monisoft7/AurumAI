# Engineering Rules

**File**: `06_ENGINEERING_RULES.md`
**Owner**: Engineering Lead
**Review Cycle**: Quarterly, or when a pattern of rule violations emerges
**Modification**: Engineering team consensus required. Substantive changes must be logged in `05_DECISIONS.md`.

---

## 1. Purpose

This document defines the engineering standards, practices, and processes that every contributor must follow. It ensures consistency, quality, and maintainability across all artifacts. It is the operational complement to `03_ARCHITECTURE_AUTHORITY.md` — architecture says WHAT and WHY, this document says HOW.

## 2. What Belongs Here

- Code review requirements and process
- Testing standards and coverage expectations
- Documentation requirements for all artifacts
- Naming conventions and style guides
- CI/CD process rules
- Version control conventions
- Quality gates and acceptance criteria
- Security and compliance practices

## 3. What Is Forbidden

- Architecture decisions (belong in `03_ARCHITECTURE_AUTHORITY.md`)
- Strategic or business decisions
- Project management content (belongs in `04_ROADMAP.md` and `10_NEXT_ACTION.md`)
- Personal preferences not backed by engineering rationale

## 4. Universal Rules (All Artifacts)

### 4.1 Every Artifact Has an Owner
Every file, document, and component must have a clearly defined owner responsible for its accuracy and maintenance.

### 4.2 Every Artifact Has a Purpose
Every artifact must begin with a clear statement of what it is for and what it is not for.

### 4.3 Review Before Merge
No artifact may be merged without review by at least one other contributor. The reviewer must be competent to evaluate the artifact.

### 4.4 Changes Are Auditable
Every change must be traceable to a rationale. If the change implements a decision, reference the decision ID from `05_DECISIONS.md`.

## 5. Document Rules

### 5.1 AOS Documents
- Must follow the structure defined in their own sections (Purpose, What Belongs, What Is Forbidden, etc.)
- Must cross-reference other AOS documents where relevant
- Must be internally self-consistent
- Must avoid duplication with other documents

### 5.2 Domain Documents
- Must follow the template defined in the relevant methodology document
- Must be validated against the knowledge base for factual accuracy
- Must include evidence references and confidence assessments

## 6. Code Rules (When Implementation Begins)

### 6.1 Readability
Code must be readable by a competent engineer in the relevant language. Cleverness is discouraged. If a comment is needed to explain what the code does, the code should be restructured instead.

### 6.2 Testing
- Every function must have unit tests for its core behavior
- Every integration point must have integration tests
- Every reasoning path must have an end-to-end test
- Tests must be deterministic
- Tests must run before every merge

### 6.3 Error Handling
Errors must never be silent. Every error must be logged, and every logged error must be actionable or acknowledged.

## 7. Version Control Rules

- Branch names: `type/short-description` (e.g., `feat/add-inflation-kr`, `fix/typo-methodology`)
- Commit messages: imperative mood, capitalized, 50-char summary with body if needed
- No direct commits to main branch
- Pull requests must reference the relevant decision or issue

## 8. Quality Gates

Before any artifact is considered "done":
1. All automated checks pass
2. At least one other contributor has reviewed it
3. The artifact's owner has signed off
4. Relevant AOS documents have been checked for consistency
5. `02_PROJECT_STATE.md` has been updated if project state changed

## 9. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-07-29 | Initial engineering rules | Founder |
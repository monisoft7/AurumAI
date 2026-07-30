# Glossary

**File**: `07_GLOSSARY.md`
**Owner**: Entire team (collective maintenance)
**Update Frequency**: As needed — whenever a new term is introduced or an existing definition is refined
**Modification**: Any contributor may add or update terms. Changes should be announced to the team and cross-referenced in `05_DECISIONS.md` if the definition is consequential.

---

## 1. Purpose

This document is the authoritative dictionary for all terms used across the project. It ensures that every contributor, human or AI, shares the same vocabulary. When a term has multiple interpretations, this document resolves which interpretation is canonical for this project.

## 2. What Belongs Here

- Project-specific terms and their precise definitions
- Domain terminology used in knowledge bases
- Acronyms and abbreviations
- Terms that are frequently misunderstood or ambiguous
- Terms imported from external sources with notes on how this project uses them

## 3. What Is Forbidden

- Implementation details or code references
- Terms that are universally understood without ambiguity (e.g., "file", "function")
- Personal or colloquial definitions
- Duplication of content from other AOS documents

## 4. Terminology

### 4.1 Project Terms

| Term | Definition |
|------|------------|
| AOS | AurumAI Operating System — the directory of governance documents that define how the project operates |
| Core Contributor | A team member with vote authority on AOS amendments and subsystem ownership |
| Decision | A logged choice with rationale, alternatives, and consequences, recorded in `05_DECISIONS.md` |
| Domain | A distinct field of knowledge with its own methodology, knowledge base, and reasoning patterns |
| Knowledge Base | A structured collection of domain facts, mechanisms, and relationships |
| Knowledge Record (KR) | A single entry in a knowledge base with standardized fields |
| Methodology | A documented reasoning framework for producing decisions within a domain |
| North Star | The long-term vision and strategic objectives defined in `01_PROJECT_NORTH_STAR.md` |

### 4.2 Architecture Terms

| Term | Definition |
|------|------------|
| ARB | Architecture Review Board — the body that approves architecture changes |
| Audit Layer | The system component that records and exposes every reasoning path |
| Inference Engine | The system component that applies knowledge to inputs to produce decisions |
| Plug-in Domain | A self-contained domain module that can be added without core changes |
| Reasoning Path | The complete chain from input to decision, including every intermediate step |

### 4.3 Quality Terms

| Term | Definition |
|------|------------|
| Confidence | A quantitative or qualitative assessment of certainty, traceable to evidence |
| Evidence | Verifiable data or source material that supports a claim or decision |
| Failure Condition | A known scenario in which a mechanism or decision would be invalid |
| Precondition | A condition that must be true for a mechanism or reasoning step to apply |

### 4.4 Acronyms

| Acronym | Full Form |
|---------|-----------|
| AOS | AurumAI Operating System |
| ARB | Architecture Review Board |
| KR | Knowledge Record |
| ADR | Architecture Decision Record |

## 5. Term Lifecycle

1. **Proposed** — Term is suggested but not yet adopted
2. **Active** — Term is in use and binding
3. **Deprecated** — Term is superseded; its definition notes what replaced it
4. **Retired** — Term is no longer in use; definition preserved for historical reference

## 6. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-07-29 | Initial glossary | Founder |
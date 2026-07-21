# AurumAI Documentation Index

> Single source of truth for every project topic. All other documentation files
> are references or redirects to the canonical sources listed here.

---

## Documentation Authority

All documentation is governed by the following hierarchy:

```
┌──────────────────────────────────────────────────────────┐
│              PROJECT_NORTH_STAR.md (root)                 │
│           Highest engineering authority                   │
└───────────────────────────┬──────────────────────────────┘
                            │ governs
┌───────────────────────────┴──────────────────────────────┐
│           docs/PROJECT_CONSTITUTION.md                    │
│           Constitutional rules and governance             │
└───────────────────────────┬──────────────────────────────┘
                            │ governs
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
┌───────────────────┐ ┌───────────┐ ┌──────────────┐
│  CURRENT_STATE.md  │ │ROADMAP.md │ │PROJECT_STATUS│
│    (root)          │ │ (root)    │ │   (root)     │
│ Canonical snapshot │ │Phases     │ │Version, Items│
│                    │ │Gates      │ │Completed, Next│
└───────────────────┘ └───────────┘ └──────────────┘
          │                 │               │
          ▼                 ▼               ▼
┌──────────────────────────────────────────────────────────┐
│              ARCHITECTURE DOCUMENTS                       │
│  docs/architecture/knowledge_engine.md                    │
│  docs/adr/ADR-0004-canonical-inference-path.md            │
└──────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────┐
│              HISTORICAL DOCUMENTS                         │
│  archive/           (sprint reports, review artifacts)    │
│  PROJECT_IDENTITY   (CTO decision record, historical)     │
│  docs/adr/          (point-in-time architecture decisions)│
└──────────────────────────────────────────────────────────┘
```

---

## Core Documentation Map

| Document | Authority | Location |
|----------|-----------|----------|
| PROJECT_NORTH_STAR.md | **Highest** | `PROJECT_NORTH_STAR.md` |
| PROJECT_CONSTITUTION.md | Constitutional | `docs/PROJECT_CONSTITUTION.md` |
| CURRENT_STATE.md | Canonical snapshot | `CURRENT_STATE.md` |
| ROADMAP.md | Phased plan | `ROADMAP.md` |
| PROJECT_STATUS.md | Version & progress | `PROJECT_STATUS.md` |
| PROJECT_IDENTITY.md | Historical (CTO record) | `PROJECT_IDENTITY.md` |

---

## Topic Index

### Identity & Vision
| Topic | Canonical Source | Also Referenced In |
|-------|-----------------|-------------------|
| Project Identity | [`PROJECT_IDENTITY.md`](../PROJECT_IDENTITY.md) | `docs/01_Project_Vision.md` (redirect) |
| Mission | `PROJECT_NORTH_STAR.md` §1, `PROJECT_IDENTITY.md` | Constitution §2 |
| Golden Rule / Open Source First | `PROJECT_IDENTITY.md` | Constitution §4.7 |
| AI Agent Roles | Constitution §7 | `docs/08_AI_Agents.md` (redirect) |
| Non-Negotiable Rules | Constitution §5 | `PROJECT_IDENTITY.md`, `docs/04_Coding_Rules.md` (redirect) |

### Constitution & Governance
| Topic | Canonical Source | Also Referenced In |
|-------|-----------------|-------------------|
| Engineering Authority | [`PROJECT_NORTH_STAR.md`](../PROJECT_NORTH_STAR.md) | Highest authority |
| Constitution | [`docs/PROJECT_CONSTITUTION.md`](PROJECT_CONSTITUTION.md) | Rules and governance |
| Coding Standards | Constitution §6 | `docs/04_Coding_Rules.md` (redirect) |
| Development Workflow | Constitution §15 | — |
| Amendment Log | Constitution (bottom) | — |

### Roadmap & Status
| Topic | Canonical Source | Also Referenced In |
|-------|-----------------|-------------------|
| Current State | [`CURRENT_STATE.md`](../CURRENT_STATE.md) | Canonical snapshot |
| Roadmap (phases, gates) | [`ROADMAP.md`](../ROADMAP.md) | `docs/02_Roadmap.md` (redirect) |
| Project Status | [`PROJECT_STATUS.md`](../PROJECT_STATUS.md) | `docs/09_Progress.md` (redirect) |
| ADR-0004 Stabilization Gates | ROADMAP.md Phase 12, ADR-0004 | PROJECT_STATUS.md |

### Architecture
| Topic | Canonical Source | Also Referenced In |
|-------|-----------------|-------------------|
| Architecture Principles (7 layers) | Constitution §9 | `PROJECT_IDENTITY.md` |
| Knowledge Engine Flow | [`docs/architecture/knowledge_engine.md`](architecture/knowledge_engine.md) | ADR-0004 |
| Feature Extraction Layer | Constitution §16 | — |
| ADR-0004: Canonical Inference Path | [`docs/adr/ADR-0004-canonical-inference-path.md`](adr/ADR-0004-canonical-inference-path.md) | All architecture docs |

### Open Source & Research
| Topic | Canonical Source | Also Referenced In |
|-------|-----------------|-------------------|
| Approved Open Source Stack | [`docs/OpenSource_Approved.md`](OpenSource_Approved.md) | Constitution §11 |
| Research Principles | Constitution §11 | — |
| Research Candidates | `research/` directory | Constitution §12 |

### Project Memory (Context for AI Agents)
| Topic | Canonical Source | Also Referenced In |
|-------|-----------------|-------------------|
| Working Memory | [`MEMORY.md`](../MEMORY.md) | — |
| README | [`README.md`](../README.md) | Entry point |

### Archive (Historical)
| Topic | Location | Notes |
|-------|----------|-------|
| Previous Sprint Reports | `archive/` | ADR-0004 closure, FCI research, validation, etc. |
| Previous Sprint Scripts | `archive/scripts/` | Historical bootstrap scripts |

---

## Cross-Reference Summary

| Document | References |
|----------|-----------|
| NORTH_STAR | Highest authority; governs all |
| Constitution | Governed by NORTH_STAR; references PROJECT_IDENTITY, ROADMAP, ADR-0004 |
| CURRENT_STATE | References NORTH_STAR, Constitution, ROADMAP |
| PROJECT_IDENTITY | Defers to NORTH_STAR and Constitution; references ADR-0004 |
| ROADMAP | References ADR-0004 (Phase 12 gates); governed by Constitution + NORTH_STAR |
| PROJECT_STATUS | References ADR-0004 (deferred gates) |
| ADR-0004 | References Constitution, PROJECT_IDENTITY, ROADMAP, PROJECT_STATUS, architecture doc |
| Architecture (knowledge_engine) | References ADR-0004, Constitution |
| OpenSource_Approved | References Constitution §11 |
| MEMORY | References ROADMAP, PROJECT_STATUS, NORTH_STAR |
| README | References NORTH_STAR, Constitution, PROJECT_IDENTITY |

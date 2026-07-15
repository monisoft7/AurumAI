# Knowledge Graph v0.1

Status: Approved

## Nodes

- Event
- Economic Indicator
- Asset
- Lesson
- Evidence
- Source

## Relations

EVENT -> LESSON

LESSON -> GOLD

LESSON -> CPI

EVENT -> EVIDENCE

EVIDENCE -> SOURCE

## Properties

- confidence
- timestamp
- occurrences
- average_return
- volatility

## Backend

Current:
- NetworkX

Future:
- Neo4j

Decision:

NetworkX until graph size requires migration.
# Architecture Decision Records (ADRs)

This directory contains records of architectural decisions made in the Zeeguu API project.

## What is an ADR?

An Architecture Decision Record (ADR) captures an important architectural decision made along with its context and consequences.

## Format

Each ADR is a markdown file with a simple structure:
- **Title**: Short, descriptive
- **Status**: Proposed, Accepted, Deprecated, Superseded
- **Context**: What problem are we solving?
- **Decision**: What did we decide?
- **Consequences**: What are the trade-offs and implications?

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [0001](0001-multi-provider-tts.md) | Multi-provider Text-to-Speech architecture | Accepted | 2025-10-28 |
| [0002](0002-docker-layer-caching-in-ci.md) | Docker layer caching in GitHub Actions | Accepted | 2025-10-28 |
| [0003](0003-buildkit-cache-mounts.md) | BuildKit cache mounts for package managers | Accepted | 2025-10-28 |

## Creating a New ADR

1. Copy `template.md` to `XXXX-short-title.md` (increment number)
2. Fill in the template
3. Add entry to this README
4. Commit with the code changes it relates to

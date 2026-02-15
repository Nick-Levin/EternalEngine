# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records (ADRs) that document significant architectural decisions made during the development of The Eternal Engine.

## What is an ADR?

An Architecture Decision Record (ADR) captures an important architectural decision made along with its context and consequences. ADRs help future developers understand:
- Why certain decisions were made
- What alternatives were considered
- What trade-offs were accepted

## Index of Decisions

| ADR | Title | Date | Status |
|-----|-------|------|--------|
| [001](001-pybit-over-ccxt.md) | Using Pybit Over CCXT | 2026-02-13 | ✅ Accepted |
| [002](002-three-phase-core-hodl.md) | 3-Phase CORE-HODL Strategy | 2026-02-13 | ✅ Accepted |
| [003](003-position-sync-strategy.md) | Position Synchronization | 2026-02-14 | ✅ Accepted |
| [004](004-top10-coin-selection.md) | TOP 10 Coin Selection | 2026-02-13 | ✅ Accepted |

## Format

Each ADR follows this structure:
- **Status:** Proposed / Accepted / Deprecated / Superseded
- **Context:** What is the issue that we're seeing?
- **Decision:** What is the change that we're proposing or have agreed to implement?
- **Consequences:** What becomes easier or more difficult to do because of this change?

## Related Documentation

- [DEVLOG.md](../../DEVLOG.md) - Chronological development diary
- [Lessons Learned](../lessons-learned.md) - Problems and solutions
- [AGENTS.md](../../AGENTS.md) - Coding standards and agent guidelines
- [ARCHITECTURE.md](../../ARCHITECTURE.md) - System architecture overview

---

*Last Updated: 2026-02-14*

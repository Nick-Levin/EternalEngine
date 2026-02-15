# ADR 002: 3-Phase CORE-HODL Strategy

**Status:** Accepted  
**Date:** 2026-02-13  
**Deciders:** Development Team  
**Context:** Capital deployment and portfolio management strategy

---

## Context and Problem Statement

The CORE-HODL engine needs to handle different portfolio states:
1. **New portfolio** - No existing positions, need to deploy capital
2. **Drifted portfolio** - Existing positions but wrong ratios
3. **Steady-state portfolio** - Just need regular DCA maintenance

A single strategy couldn't handle all these scenarios optimally.

## Decision Drivers

- Must reach 60% allocation target efficiently
- Must maintain 67% BTC / 33% ETH ratio
- Must handle large capital deployments without market impact
- Must work without selling (accumulation philosophy)

## Considered Options

### Option 1: Simple DCA (Fixed Amount)
**Approach:** Buy fixed USD amount every week regardless of portfolio state.

**Pros:** Simple, predictable  
**Cons:** Slow to reach target, doesn't handle drift

### Option 2: Target-Based (Always Calculate Gap)
**Approach:** Always calculate gap to target and buy that amount.

**Pros:** Always moving toward target  
**Cons:** Large purchases on restart, no concept of "done"

### Option 3: 3-Phase Adaptive Strategy (Selected)
**Approach:** State machine with DEPLOYING → REBALANCING → MAINTAINING

**Pros:**
- Handles all portfolio states
- Time-bound deployment (12 weeks max)
- Rebalances without selling
- Clear transitions

**Cons:** More complex to implement

## Decision

**Chosen Option: Option 3 (3-Phase Strategy)**

### Phase 1: DEPLOYING (Weeks 1-12)
- Deploy capital to reach 60% target
- Weekly purchases proportional to gap
- Freeze target at start (don't chase moving target)

### Phase 2: REBALANCING (Weeks 13-16)
- Adjust to 67% BTC / 33% ETH ratio
- Buy more of underweight, less of overweight
- No selling required

### Phase 3: MAINTAINING (Ongoing)
- Standard DCA at base amount
- Weekly purchases regardless of price

## State Machine

```
┌─────────────┐     target reached      ┌─────────────┐
│  DEPLOYING  │ ──────────────────────→ │ REBALANCING │
│  (12 weeks) │                         │  (4 weeks)  │
└─────────────┘                         └─────────────┘
                                               │
                                               │ ratio OK
                                               ▼
                                        ┌─────────────┐
                                        │ MAINTAINING │
                                        │  (ongoing)  │
                                        └─────────────┘
```

## Key Implementation Details

### Frozen Deployment Capital
```python
# Freeze at start - don't chase moving target
self._deployment_start_value = portfolio_value
self._target_value = portfolio_value * Decimal("0.60")
```

### Weekly Target Calculation
```python
if gap < 500: weeks = 1
elif gap < 50000: weeks = 4
else: weeks = 12

weekly_target = gap / weeks
```

### Rebalancing Without Selling
```python
# Week 1: Overallocated @ 75%, Underallocated @ 125%
# Week 2: Overallocated @ 50%, Underallocated @ 150%
# Week 3: Overallocated @ 25%, Underallocated @ 175%
# Week 4: Overallocated @ 0%, Underallocated @ 200%
```

## Consequences

### Positive
- Clear behavior for each portfolio state
- Time-bound deployment (predictable)
- Rebalances without selling (tax efficient)
- Handles restarts gracefully

### Negative
- More complex than simple DCA
- State transitions must be tested thoroughly
- Rebalancing takes 4 weeks (gradual)

## References
- [DEVLOG.md](../../DEVLOG.md) - 3-Phase CORE-HODL Strategy section
- [AGENTS.md](../../AGENTS.md) - Strategy specifications
- `src/strategies/dca_strategy.py` - Implementation

# Decision Engine Explanation

## Pipeline

```
demand sensing → forecast → inventory position → FEFO/expiry → dynamic ROP
→ stockout + expiry risk → root cause → network search → transfer feasibility
→ TRANSFER / REPLENISH / MONITOR → quantity, timing, priority, explanation
```

All of this lives in `backend/app/services/decision.py: evaluate()`.

## Dynamic ROP

```
Reorder Point = (sensed avg daily demand × lead time)
              + (z-score × demand std-dev × sqrt(lead time))
```

The z-score is chosen by SKU criticality (Critical → 2.05 ≈ 98% service level,
down to Low → 0.84 ≈ 80%). This means the same shortfall in stock produces a
different urgency for a Critical insulin SKU than for a Low-criticality
multivitamin — by design.

## Risk scoring

**Stockout risk** (0-100) rises as current stock falls below ROP, and rises
further once days-of-supply falls below the replenishment lead time (i.e. the
DC literally cannot restock in time even if it ordered today). It is scaled by
a criticality weight.

**Expiry risk** (0-100) is the fraction of current stock that FEFO projects
will expire unconsumed, based on the forward sensed-demand projection — not
historical demand (see `inventory.py` module docstring for why that
distinction matters).

## Root cause

`root_cause.py` inspects the same numbers already computed (sensing
components, days-of-supply vs. lead time, expiry risk, network state, and a
pre-flu-period trend check for chronic understock) and returns a **ranked**
list of contributing causes with a plain-English explanation for each — not
just a single guessed label.

## Network search and transfer feasibility

Triggered only when stockout risk crosses the action threshold (20/100) and
there's a genuine shortfall against ROP. For every *other* DC:

1. Compute that DC's own inventory position and its own ROP for the same SKU.
2. **Usable excess** = that DC's stock above 110% of its own ROP (it can't
   donate what it needs for itself).
3. Of that excess, only batches whose expiry is comfortably later than
   (transfer lead time + 14 days of consumption buffer) count as
   **expiry-safe transferable** quantity.
4. Feasibility requires: transferable qty > 0, transfer lead time ≤ 4 days
   (an operational threshold), and the destination has enough capacity
   headroom.

If any candidate is feasible, the highest-transferable-quantity feasible
source is chosen and the decision is **TRANSFER**. If none is feasible, the
specific reason each candidate failed is recorded (`reason_if_infeasible`) and
surfaced in both the API payload and the explanation text — this is what lets
the system explain *why* it fell back to REPLENISH instead of silently
picking one.

## Final decision rule

```
if stockout_risk < 20 AND expiry_risk < 20:
    MONITOR
elif a feasible transfer source exists:
    TRANSFER (quantity = min(shortfall, transferable), timing = transfer lead time)
elif shortfall > 0 or stockout_risk >= 20:
    REPLENISH (quantity = shortfall, timing = supplier lead time)
else:
    MONITOR (with an expiry-risk-specific explanation)
```

## Cost of inaction and priority

`cost.py` computes stockout cost (shortfall × margin × stockout probability ×
weighting) and expiry cost (expected loss × unit cost) and sums them. Priority
combines the risk score, a criticality weight, and the cost estimate into a
single score, which is bucketed into Critical / High / Medium / Low with a
matching review cadence (24h / 48h / 96h / 168h) and escalation text.

## Replenishment frequency (P1-R21)

The engine uses a continuous-review (reorder-point) policy rather than a fixed
periodic ordering schedule, so "replenishment frequency" is expressed as an
**implied cycle length**: `rop.py: compute_replenishment_frequency()` divides
the recommended quantity (for TRANSFER/REPLENISH) — or the stock currently
held above the reorder point (for MONITOR) — by the sensed daily demand rate,
giving `replenishment_cycle_days` and `estimated_replenishments_per_year`.
This is purely additive reporting on top of numbers the engine already
computes; it does not affect the reorder point, the recommended quantity, or
the TRANSFER/REPLENISH/MONITOR decision itself (verified in `test_24`, which
also re-confirms the three example scenarios still resolve to their expected
actions after this field was added).

## What is *not* in the decision engine

- No per-SKU or per-DC lookup table of outcomes.
- No machine-learned classifier — every branch above is a documented,
  inspectable rule operating on numbers computed earlier in the same pipeline.
- No silent fallback to REPLENISH without first genuinely searching the
  network (this is enforced by `test_06_transfer_infeasible_replenishes`,
  which checks that the network actually was searched and rejected candidates
  before the REPLENISH decision was made).

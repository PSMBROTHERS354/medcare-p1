# Architecture Alternatives

For each major decision, this document records the alternative considered and
why the chosen approach fit P1 better.

## Forecasting: Holt-Winters vs. Deep Learning

**Chosen: Holt-Winters (exponential smoothing with trend + weekly seasonality).**

| | Holt-Winters | Deep learning (e.g. LSTM/Transformer) |
|---|---|---|
| Data volume needed | Works well with ~180 days per series (what this project has) | Typically needs much longer history / more series to generalize |
| Explainability | Trend + seasonal + level components are directly inspectable | Effectively a black box without extra tooling |
| Fit time | Milliseconds to low-hundreds of ms per series | Would require training infrastructure, GPUs, and time this hackathon doesn't call for |
| Fit for demo | Judge can see *why* the forecast moved (sensing multiplier is a transparent, auditable number) | Harder to justify "why did the model predict this" live in a demo |

Given the master requirement that the decision engine be "explainable
deterministic decisioning" rather than a black box, and the data volume
available, Holt-Winters was the appropriate choice. Deep learning was
deliberately not added "merely to look advanced."

## Database: SQLite vs. PostgreSQL

**Chosen: SQLite.**

SQLite requires no separate server process, ships as a single file
(`medcare.db`), and is trivial to regenerate deterministically via
`data_gen.py`. For a single-instance hackathon deployment with ~5,500 demand
rows and ~140 batch rows, SQLite's concurrency limitations are not a real
constraint. PostgreSQL would be the natural next step for a genuinely
multi-writer production deployment (e.g. real-time inventory updates from
multiple warehouse systems), but that is out of scope for P1 as specified.

## API framework: FastAPI vs. Flask

**Chosen: FastAPI.**

FastAPI's Pydantic-based request validation (used directly in the
`WhatIfRequest` model) gave the input-validation requirement "for free" with
clear 422 responses, and its automatic OpenAPI docs (`/docs`) double as living
API documentation during development. Flask would have required manually
wiring a validation library (e.g. marshmallow) to reach the same guarantees.

## Decision engine: explainable deterministic decisioning vs. black-box ML

**Chosen: explainable deterministic decisioning (rule-based orchestration over
computed risk/cost/network numbers).**

The master requirement explicitly calls for an explainable system where a
judge can trace WHY a recommendation was reached without understanding every
internal formula. A black-box classifier (e.g. a trained model predicting
TRANSFER/REPLENISH/MONITOR) would have required labeled historical outcomes
that don't exist for this synthetic scenario, and would have undermined the
root-cause and network-alternatives explanation screens, which depend on
being able to point to specific computed numbers (ROP, expiry loss, transfer
lead time) as the reason for the decision.

## Forecast serving: offline persisted cache vs. re-fitting every request

**Chosen: offline persisted cache, warmed at startup, with live compute
reserved for what-if scenarios.**

See `ARCHITECTURE.md` → Performance approach for the measured before/after
(14s → ~400ms on bulk endpoints). Re-fitting on every request was simpler to
implement first but failed the "UI must feel responsive" requirement outright;
this was caught and fixed during development, not assumed away.

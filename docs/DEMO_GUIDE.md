# Demo Guide

## Setup (before the judge session)

```bash
# Terminal 1
cd backend
pip install -r requirements.txt
python3 app/data_gen.py
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Confirm `http://localhost:8000/api/health` shows
`forecast_cache_size: 30` before starting — that confirms the cache warmed
successfully and the demo will feel responsive.

## The one-story walkthrough (≈6 minutes)

**1. Open Command Center.**
"During a flu-season demand surge, critical SKUs can become unavailable in
Tier-2 DCs while Metro DCs sit on excess near-expiry stock." Point at the
network health score, the risk map (note the DC states are computed, not
decorative), and the critical action queue — click the top item.

**2. Land on SKU/DC Intelligence for MED-001 @ Hyderabad Tier-2 DC.**
Walk through:
- Baseline vs. sensed forecast chart — the sensed line sits above baseline
  because of the active flu signal (point at the sensing-signal line: "flu
  +60%...").
- Dynamic ROP and stockout risk — both elevated.
- Root cause panel — "Demand surge (flu signal)" ranked first.
- Network alternatives — Chennai Metro DC shown feasible, with expiry-safe
  transferable quantity and a short transfer lead time.
- Recommendation explanation footer — WHAT/HOW MUCH/WHERE/WHEN/WHY/REVIEW/
  ESCALATION all populated: TRANSFER, quantity, Chennai → Hyderabad, timing,
  explanation, review cadence, escalation.

**3. Switch to MED-003 @ Patna Tier-2 DC (also in the attention queue).**
Same shortage shape, but Patna's transfer lead times are all >4 days — show
the network alternatives list marked infeasible with a stated reason, and the
decision falls back to REPLENISH instead. This demonstrates the system
searches the network *before* recommending supplier replenishment, and
explains why it didn't transfer.

**4. Open Decision Studio.**
Pick a healthy SKU/DC (e.g. MED-004 @ Mumbai Metro). Toggle flu on, push the
demand slider up, and click Run Simulation. Show the before/after comparison
and the "What Changed" diff — forecast, ROP, risk, and action all
genuinely recalculate (no fixed before/after values).

**5. Open Monitoring.**
Show the action distribution and priority breakdown across the full network,
and the action history table — this is the same computed data from Command
Center's queue, aggregated for a network-wide view.

## Fallback scenarios if something doesn't load

- If `/api/health` doesn't show `forecast_cache_size: 30`, the cache is still
  warming — wait a few seconds and refresh; startup takes ~5-8s for the full
  30-combination Holt-Winters warm-up.
- `GET /api/scenarios` lists the exact engineered SKU/DC pairs and their
  expected behavior — useful as a cheat sheet if picking demo items live.

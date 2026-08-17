import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Loading, ErrorBlock, ActionBadge, RiskBadge, SectionCard } from '../components/Widgets';
import './DecisionStudio.css';

export default function DecisionStudio() {
  const [skus, setSkus] = useState([]);
  const [dcs, setDcs] = useState([]);
  const [sku, setSku] = useState('MED-004');
  const [dc, setDc] = useState('DC-METRO-MUM');

  const [demandChange, setDemandChange] = useState(0);
  const [fluActive, setFluActive] = useState(false);
  const [leadTimeDelta, setLeadTimeDelta] = useState(0);
  const [costWeight, setCostWeight] = useState(1.0);

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([api.skus(), api.dcs()]).then(([s, d]) => { setSkus(s); setDcs(d); });
  }, []);

  function runSimulation() {
    setLoading(true); setError(null);
    api.whatIf({
      sku_id: sku, dc_id: dc,
      demand_change_pct: demandChange,
      flu_active: fluActive,
      lead_time_delta: leadTimeDelta,
      cost_weight_stockout: costWeight,
    }).then((r) => { setResult(r); setLoading(false); }).catch((e) => { setError(e.message); setLoading(false); });
  }

  useEffect(() => { runSimulation(); }, [sku, dc]);

  const changed = (key) => result && result.before[key] !== result.after[key];

  return (
    <div className="page fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Decision Studio</h1>
          <div className="page-subtitle">What happens if conditions change?</div>
        </div>
      </div>

      <div className="ds-grid">
        <SectionCard title="Scenario Controls" className="ds-controls">
          <div className="control-block">
            <label className="control-label">SKU</label>
            <select value={sku} onChange={(e) => setSku(e.target.value)}>
              {skus.map((s) => <option key={s.sku_id} value={s.sku_id}>{s.sku_id} — {s.name}</option>)}
            </select>
          </div>
          <div className="control-block">
            <label className="control-label">Distribution Center</label>
            <select value={dc} onChange={(e) => setDc(e.target.value)}>
              {dcs.map((d) => <option key={d.dc_id} value={d.dc_id}>{d.name}</option>)}
            </select>
          </div>

          <div className="control-block">
            <label className="control-label">Demand change <span className="control-value">{demandChange > 0 ? '+' : ''}{demandChange}%</span></label>
            <input type="range" min="-50" max="150" step="5" value={demandChange} onChange={(e) => setDemandChange(Number(e.target.value))} />
          </div>

          <div className="control-block toggle-block">
            <label className="control-label">Flu scenario (+60% signal)</label>
            <button className={`toggle ${fluActive ? 'on' : ''}`} onClick={() => setFluActive(!fluActive)}>
              <span className="toggle-knob" />
            </button>
          </div>

          <div className="control-block">
            <label className="control-label">Lead-time change <span className="control-value">{leadTimeDelta > 0 ? '+' : ''}{leadTimeDelta}d</span></label>
            <input type="range" min="-5" max="15" step="1" value={leadTimeDelta} onChange={(e) => setLeadTimeDelta(Number(e.target.value))} />
          </div>

          <div className="control-block">
            <label className="control-label">Cost weighting (stockout emphasis) <span className="control-value">{costWeight.toFixed(1)}×</span></label>
            <input type="range" min="0.5" max="3" step="0.1" value={costWeight} onChange={(e) => setCostWeight(Number(e.target.value))} />
          </div>

          <button className="btn-primary run-btn" onClick={runSimulation} disabled={loading}>
            {loading ? 'Recalculating…' : 'Run Simulation'}
          </button>
          {result && <div className="compute-time">computed in {result.compute_time_ms}ms</div>}
        </SectionCard>

        <div className="ds-results">
          {error && <ErrorBlock message={error} onRetry={runSimulation} />}
          {!result && !error && <Loading label="Running baseline simulation…" />}
          {result && (
            <div className="compare-grid">
              <SectionCard title="Before" className="compare-card">
                <CompareBody data={result.before} />
              </SectionCard>
              <SectionCard title="After" className="compare-card compare-after">
                <CompareBody data={result.after} highlight />
              </SectionCard>
            </div>
          )}

          {result && (
            <SectionCard title="What Changed" className="ds-diff-card">
              <div className="diff-rows">
                <DiffRow label="Sensed Forecast (avg/day)" before={result.before.sensed_avg_daily_forecast} after={result.after.sensed_avg_daily_forecast} changed={changed('sensed_avg_daily_forecast')} />
                <DiffRow label="Reorder Point" before={result.before.reorder_point} after={result.after.reorder_point} changed={changed('reorder_point')} />
                <DiffRow label="Stockout Risk" before={result.before.stockout_risk_score} after={result.after.stockout_risk_score} changed={changed('stockout_risk_score')} />
                <DiffRow label="Action" before={result.before.action} after={result.after.action} changed={changed('action')} isText />
                <DiffRow label="Quantity" before={result.before.quantity} after={result.after.quantity} changed={changed('quantity')} />
                <DiffRow label="Cost of Inaction" before={`₹${result.before.total_cost_of_inaction.toLocaleString()}`} after={`₹${result.after.total_cost_of_inaction.toLocaleString()}`} changed={changed('total_cost_of_inaction')} isText />
              </div>
            </SectionCard>
          )}
        </div>
      </div>
    </div>
  );
}

function CompareBody({ data, highlight }) {
  return (
    <div className="compare-body">
      <div className="compare-row"><span>Forecast</span><b>{data.sensed_avg_daily_forecast}/day</b></div>
      <div className="compare-row"><span>ROP</span><b>{data.reorder_point}</b></div>
      <div className="compare-row"><span>Stockout Risk</span><b><RiskBadge level={data.stockout_risk_level} /></b></div>
      <div className="compare-row"><span>Action</span><b><ActionBadge action={data.action} /></b></div>
      <div className="compare-row"><span>Quantity</span><b>{data.quantity} units</b></div>
      <div className="compare-row"><span>Source</span><b>{data.source_dc_name || '—'}</b></div>
      <div className="compare-row"><span>Priority</span><b><RiskBadge level={data.priority} /></b></div>
      <div className="compare-row"><span>Cost of Inaction</span><b>₹{data.total_cost_of_inaction.toLocaleString()}</b></div>
    </div>
  );
}

function DiffRow({ label, before, after, changed, isText }) {
  return (
    <div className={`diff-row ${changed ? 'diff-changed' : ''}`}>
      <span className="diff-label">{label}</span>
      <span className="diff-before">{before}</span>
      <span className="diff-arrow">→</span>
      <span className="diff-after">{after}</span>
    </div>
  );
}

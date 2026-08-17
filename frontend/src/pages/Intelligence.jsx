import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { api } from '../api/client';
import { Loading, ErrorBlock, RiskBadge, ActionBadge, SectionCard, StatCard } from '../components/Widgets';
import './Intelligence.css';

export default function Intelligence() {
  const [params, setParams] = useSearchParams();
  const [skus, setSkus] = useState([]);
  const [dcs, setDcs] = useState([]);
  const [sku, setSku] = useState(params.get('sku') || 'MED-001');
  const [dc, setDc] = useState(params.get('dc') || 'DC-TIER2-HYD');
  const [rec, setRec] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([api.skus(), api.dcs()]).then(([s, d]) => { setSkus(s); setDcs(d); });
  }, []);

  function load(s, d) {
    setError(null); setRec(null);
    api.recommendation(s, d).then(setRec).catch((e) => setError(e.message));
  }

  useEffect(() => { load(sku, dc); setParams({ sku, dc }); }, [sku, dc]);

  const chartData = rec ? rec.forecast.forecast_dates.map((date, i) => ({
    date: date.slice(5),
    Baseline: rec.forecast.baseline_forecast[i],
    Sensed: rec.forecast.sensed_forecast[i],
  })) : [];

  return (
    <div className="page fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">SKU / DC Intelligence</h1>
          <div className="page-subtitle">Why is this SKU at risk?</div>
        </div>
        <div className="selector-row">
          <select value={sku} onChange={(e) => setSku(e.target.value)}>
            {skus.map((s) => <option key={s.sku_id} value={s.sku_id}>{s.sku_id} — {s.name}</option>)}
          </select>
          <select value={dc} onChange={(e) => setDc(e.target.value)}>
            {dcs.map((d) => <option key={d.dc_id} value={d.dc_id}>{d.name}</option>)}
          </select>
        </div>
      </div>

      {error && <ErrorBlock message={error} onRetry={() => load(sku, dc)} />}
      {!rec && !error && <Loading label="Evaluating SKU × DC position…" />}

      {rec && (
        <>
          <div className="intel-headline card">
            <div className="intel-headline-left">
              <div className="intel-sku-name">{rec.sku.name} <span className="intel-sku-id">({rec.sku.sku_id})</span></div>
              <div className="intel-dc-name">{rec.dc.name} · {rec.dc.type}</div>
            </div>
            <div className="intel-headline-right">
              <ActionBadge action={rec.decision.action} />
              <RiskBadge level={rec.priority.priority} />
            </div>
          </div>

          <div className="stat-grid" style={{ marginTop: 16 }}>
            <StatCard label="Current Stock" value={rec.inventory.current_stock.toLocaleString()} sub={`${rec.inventory.days_of_supply ?? '—'} days of supply`} />
            <StatCard label="Sensed Forecast (avg/day)" value={rec.forecast.sensed_avg_daily} sub={`baseline ${rec.forecast.baseline_avg_daily}`} />
            <StatCard label="Dynamic ROP" value={rec.rop.reorder_point} sub={`lead time ${rec.rop.lead_time_days}d`} />
            <StatCard label="Stockout Risk" value={rec.risk.stockout_risk_score} sub={rec.risk.stockout_risk_level} tone={rec.risk.stockout_risk_score >= 45 ? 'critical' : rec.risk.stockout_risk_score >= 20 ? 'warning' : 'good'} />
            <StatCard label="Expiry Risk" value={rec.risk.expiry_risk_score} sub={rec.risk.expiry_risk_level} tone={rec.risk.expiry_risk_score >= 45 ? 'critical' : rec.risk.expiry_risk_score >= 20 ? 'warning' : 'good'} />
          </div>

          <div className="intel-grid">
            <SectionCard title="Baseline vs Sensed Forecast" subtitle={`Holt-Winters · holdout MAPE (sensed) ${rec.forecast.evaluation.sensed_metrics.mape ?? '—'}%`}>
              <ResponsiveContainer width="100%" height={230}>
                <LineChart data={chartData} margin={{ left: -18, right: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--card-border)" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line type="monotone" dataKey="Baseline" stroke="var(--text-muted)" strokeWidth={2} dot={false} strokeDasharray="4 3" />
                  <Line type="monotone" dataKey="Sensed" stroke="var(--teal-600)" strokeWidth={2.4} dot={false} />
                </LineChart>
              </ResponsiveContainer>
              <div className="sensing-explanation">
                <span className="se-label">Sensing signal:</span>
                {' '}flu +{Math.round((rec.forecast.sensing_explanation.flu_component || 0) * 100)}% ·
                {' '}promo +{Math.round((rec.forecast.sensing_explanation.promo_component || 0) * 100)}% ·
                {' '}distributor momentum {Math.round((rec.forecast.sensing_explanation.distributor_momentum_component || 0) * 100)}%
              </div>
            </SectionCard>

            <SectionCard title="Root Cause" subtitle="Ranked contributing factors">
              <div className="cause-list">
                {rec.root_causes.map((c, i) => (
                  <div key={i} className="cause-item">
                    <div className="cause-title">{c.cause}</div>
                    <div className="cause-detail">{c.detail}</div>
                  </div>
                ))}
              </div>
            </SectionCard>
          </div>

          <div className="intel-grid">
            <SectionCard title="Batch / Expiry Detail" subtitle={`FEFO-projected expiry loss: ${rec.fefo.expected_expiry_loss_units} units`}>
              <table className="simple-table">
                <thead><tr><th>Batch</th><th>Qty</th><th>Expiry</th><th>Days to Expiry</th><th>Projected Loss</th></tr></thead>
                <tbody>
                  {rec.fefo.fefo_allocation.map((b) => (
                    <tr key={b.batch_id} className={b.projected_expiry_loss > 0 ? 'row-risk' : ''}>
                      <td className="mono">{b.batch_id}</td>
                      <td>{b.qty}</td>
                      <td>{b.expiry_date}</td>
                      <td>{b.days_to_expiry}</td>
                      <td>{b.projected_expiry_loss > 0 ? b.projected_expiry_loss : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </SectionCard>

            <SectionCard title="Network Alternatives" subtitle="Sister DCs evaluated for transfer feasibility">
              {rec.network_alternatives.length === 0 && <div className="empty-note">No network search triggered — risk within normal range.</div>}
              <div className="network-alt-list">
                {rec.network_alternatives.map((c) => (
                  <div key={c.source_dc_id} className={`network-alt-item ${c.feasible ? 'feasible' : 'infeasible'}`}>
                    <div className="na-top">
                      <span className="na-name">{c.source_dc_name}</span>
                      <span className={`na-tag ${c.feasible ? 'tag-feasible' : 'tag-infeasible'}`}>{c.feasible ? 'Feasible' : 'Infeasible'}</span>
                    </div>
                    <div className="na-detail">
                      excess {c.usable_excess_units}u · transferable {c.expiry_safe_transferable_units}u · lead time {c.transfer_lead_time_days ?? '—'}d
                    </div>
                    {!c.feasible && <div className="na-reason">{c.reason_if_infeasible}</div>}
                  </div>
                ))}
              </div>
            </SectionCard>
          </div>

          <SectionCard title="Recommendation Explanation" className="explain-card">
            <div className="explain-grid">
              <div><span className="ex-label">WHAT</span><div className="ex-value"><ActionBadge action={rec.decision.action} /></div></div>
              <div><span className="ex-label">HOW MUCH</span><div className="ex-value">{rec.decision.quantity} units</div></div>
              <div><span className="ex-label">WHERE</span><div className="ex-value">{rec.decision.source_dc_name ? `${rec.decision.source_dc_name} → ${rec.dc.name}` : rec.dc.name}</div></div>
              <div><span className="ex-label">WHEN</span><div className="ex-value">{rec.decision.timing_days != null ? `within ${rec.decision.timing_days} day(s)` : '—'}</div></div>
              <div><span className="ex-label">FREQUENCY</span><div className="ex-value">{rec.decision.replenishment_cycle_days != null ? `~every ${rec.decision.replenishment_cycle_days}d (${rec.decision.estimated_replenishments_per_year}/yr)` : '—'}</div></div>
              <div><span className="ex-label">REVIEW</span><div className="ex-value">every {rec.priority.review_cadence_hours}h</div></div>
              <div><span className="ex-label">ESCALATION</span><div className="ex-value">{rec.priority.escalation}</div></div>
            </div>
            <div className="ex-why"><span className="ex-label">WHY</span> {rec.decision.explanation}</div>
          </SectionCard>
        </>
      )}
    </div>
  );
}

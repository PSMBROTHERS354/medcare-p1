import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { Loading, ErrorBlock, StatCard, SectionCard, RiskBadge, ActionBadge } from '../components/Widgets';
import NetworkRiskMap from '../components/NetworkRiskMap';

export default function CommandCenter() {
  const [health, setHealth] = useState(null);
  const [queue, setQueue] = useState(null);
  const [networkMap, setNetworkMap] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  function load() {
    setError(null);
    setHealth(null); setQueue(null); setNetworkMap(null); setMetrics(null);
    Promise.all([api.networkHealth(), api.attentionQueue(8), api.networkMap(), api.monitoringMetrics()])
      .then(([h, q, m, mt]) => { setHealth(h); setQueue(q); setNetworkMap(m); setMetrics(mt); })
      .catch((e) => setError(e.message));
  }

  useEffect(load, []);

  if (error) return <div className="page"><ErrorBlock message={error} onRetry={load} /></div>;
  if (!health || !queue || !networkMap || !metrics) return <div className="page"><Loading label="Loading network overview…" /></div>;

  return (
    <div className="page fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Command Center</h1>
          <div className="page-subtitle">What needs attention across the MedCare Pharma network right now</div>
        </div>
      </div>

      <div className="stat-grid">
        <StatCard
          label="Network Health Score"
          value={`${health.network_health_score}/100`}
          sub={`${health.critical_priority_count} critical priority item(s)`}
          tone={health.network_health_score >= 80 ? 'good' : health.network_health_score >= 60 ? 'warning' : 'critical'}
        />
        <StatCard label="Avg. Stockout Risk" value={`${health.avg_stockout_risk}`} sub="0–100 scale, across all SKU × DC" tone={health.avg_stockout_risk >= 45 ? 'critical' : health.avg_stockout_risk >= 20 ? 'warning' : 'good'} />
        <StatCard label="Avg. Expiry Risk" value={`${health.avg_expiry_risk}`} sub="0–100 scale, FEFO-projected" tone={health.avg_expiry_risk >= 45 ? 'critical' : health.avg_expiry_risk >= 20 ? 'warning' : 'good'} />
        <StatCard label="Forecast Accuracy (sensed)" value={metrics.avg_sensed_mape_pct != null ? `${metrics.avg_sensed_mape_pct}% MAPE` : '—'} sub={`avg MAE ${metrics.avg_sensed_mae}`} />
        <StatCard label="Cost of Inaction Exposure" value={`₹${health.total_cost_of_inaction_exposure.toLocaleString()}`} sub="if no action taken this cycle" tone="warning" />
      </div>

      <div className="cc-grid">
        <SectionCard title="Supply Network Risk Map" subtitle="DC state and feasible transfer relationships, computed from live backend data" className="cc-map-card">
          <NetworkRiskMap data={networkMap} />
        </SectionCard>

        <SectionCard title="Critical Action Queue" subtitle="Top SKU × DC items by priority score" className="cc-queue-card">
          <div className="queue-list scrollbar-thin">
            {queue.length === 0 && <div className="empty-note">No items currently require action.</div>}
            {queue.map((item) => (
              <button
                key={`${item.sku_id}-${item.dc_id}`}
                className="queue-item"
                onClick={() => navigate(`/intelligence?sku=${item.sku_id}&dc=${item.dc_id}`)}
              >
                <div className="queue-item-top">
                  <span className="queue-item-name">{item.sku_name}</span>
                  <ActionBadge action={item.action} />
                </div>
                <div className="queue-item-dc">{item.dc_name}</div>
                <div className="queue-item-bottom">
                  <RiskBadge level={item.priority} />
                  <span className="queue-item-score">risk {item.combined_risk_score}</span>
                </div>
              </button>
            ))}
          </div>
        </SectionCard>
      </div>

      <div className="cc-grid-lower">
        <SectionCard title="Action Distribution" subtitle={`${health.combos_evaluated} SKU × DC combinations evaluated`}>
          <div className="dist-bars">
            {Object.entries(health.action_distribution).map(([action, count]) => (
              <div key={action} className="dist-row">
                <span className="dist-label">{action}</span>
                <div className="dist-track">
                  <div
                    className={`dist-fill dist-${action.toLowerCase()}`}
                    style={{ width: `${(count / health.combos_evaluated) * 100}%` }}
                  />
                </div>
                <span className="dist-count">{count}</span>
              </div>
            ))}
          </div>
        </SectionCard>

        <SectionCard title="Top SKUs Requiring Attention" subtitle="Ranked by priority score">
          <table className="simple-table">
            <thead><tr><th>SKU</th><th>DC</th><th>Action</th><th>Priority</th></tr></thead>
            <tbody>
              {queue.slice(0, 6).map((item) => (
                <tr key={`${item.sku_id}-${item.dc_id}-t`} onClick={() => navigate(`/intelligence?sku=${item.sku_id}&dc=${item.dc_id}`)}>
                  <td>{item.sku_id}</td>
                  <td>{item.dc_name}</td>
                  <td><ActionBadge action={item.action} /></td>
                  <td><RiskBadge level={item.priority} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </SectionCard>
      </div>
    </div>
  );
}

import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { api } from '../api/client';
import { Loading, ErrorBlock, StatCard, SectionCard, ActionBadge } from '../components/Widgets';
import './Monitoring.css';

const ACTION_COLORS = { TRANSFER: '#2563a8', REPLENISH: '#b8720a', MONITOR: '#1c7a4d' };

export default function Monitoring() {
  const [health, setHealth] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [queue, setQueue] = useState(null);
  const [history, setHistory] = useState(null);
  const [error, setError] = useState(null);

  function load() {
    setError(null);
    Promise.all([api.networkHealth(), api.monitoringMetrics(), api.attentionQueue(20), api.monitoringHistory()])
      .then(([h, m, q, hi]) => { setHealth(h); setMetrics(m); setQueue(q); setHistory(hi); })
      .catch((e) => setError(e.message));
  }

  useEffect(load, []);

  if (error) return <div className="page"><ErrorBlock message={error} onRetry={load} /></div>;
  if (!health || !metrics || !queue || !history) return <div className="page"><Loading label="Loading network monitoring data…" /></div>;

  const pieData = Object.entries(health.action_distribution).map(([name, value]) => ({ name, value }));
  const priorityCounts = queue.reduce((acc, i) => { acc[i.priority] = (acc[i.priority] || 0) + 1; return acc; }, {});
  const priorityData = ['Critical', 'High', 'Medium', 'Low'].map((p) => ({ priority: p, count: priorityCounts[p] || 0 }));

  return (
    <div className="page fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Monitoring</h1>
          <div className="page-subtitle">Is the network improving?</div>
        </div>
      </div>

      <div className="stat-grid">
        <StatCard label="Network Health Score" value={`${health.network_health_score}/100`} tone={health.network_health_score >= 80 ? 'good' : health.network_health_score >= 60 ? 'warning' : 'critical'} />
        <StatCard label="Stockout Exposure (avg)" value={health.avg_stockout_risk} tone={health.avg_stockout_risk >= 45 ? 'critical' : 'good'} />
        <StatCard label="Expiry Exposure (avg)" value={health.avg_expiry_risk} tone={health.avg_expiry_risk >= 45 ? 'critical' : 'good'} />
        <StatCard label="Forecast MAPE (sensed, avg)" value={metrics.avg_sensed_mape_pct != null ? `${metrics.avg_sensed_mape_pct}%` : '—'} />
        <StatCard label="Items Needing Review" value={queue.length} sub="across all SKU × DC" />
      </div>

      <div className="mon-grid">
        <SectionCard title="Action Distribution" subtitle="Across all evaluated SKU × DC combinations">
          <ResponsiveContainer width="100%" height={230}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={78} label>
                {pieData.map((entry) => <Cell key={entry.name} fill={ACTION_COLORS[entry.name]} />)}
              </Pie>
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
        </SectionCard>

        <SectionCard title="Priority Breakdown" subtitle="Items on the attention queue by priority level">
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={priorityData} margin={{ left: -18 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--card-border)" />
              <XAxis dataKey="priority" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {priorityData.map((entry) => (
                  <Cell key={entry.priority} fill={{ Critical: '#b3261e', High: '#b8720a', Medium: '#2563a8', Low: '#1c7a4d' }[entry.priority]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </SectionCard>
      </div>

      <SectionCard title="Action History" subtitle="Full attention queue, all current recommendations" className="mon-history-card">
        <table className="simple-table">
          <thead><tr><th>SKU</th><th>DC</th><th>Action</th><th>Priority</th><th>Risk Score</th><th>Review Cadence</th></tr></thead>
          <tbody>
            {queue.map((item) => (
              <tr key={`${item.sku_id}-${item.dc_id}`}>
                <td>{item.sku_id}</td>
                <td>{item.dc_name}</td>
                <td><ActionBadge action={item.action} /></td>
                <td>{item.priority}</td>
                <td>{item.combined_risk_score}</td>
                <td>{item.priority_score}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </SectionCard>

      <div className="mon-note">
        Monitoring history accumulates as this application is used across sessions; trend snapshots reflect actual computed network state at each run, not simulated data.
      </div>
    </div>
  );
}

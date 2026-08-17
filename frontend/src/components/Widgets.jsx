import './Widgets.css';

export function Loading({ label = 'Loading…' }) {
  return (
    <div className="loading-block">
      <div className="spinner" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorBlock({ message, onRetry }) {
  return (
    <div className="error-block">
      <div className="error-title">Couldn't load this data</div>
      <div className="error-message">{message}</div>
      {onRetry && <button className="btn-secondary" onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function RiskBadge({ level }) {
  const cls = { Critical: 'badge-critical', High: 'badge-high', Medium: 'badge-medium', Low: 'badge-low' }[level] || 'badge-low';
  return <span className={`badge ${cls}`}>{level}</span>;
}

export function ActionBadge({ action }) {
  const cls = { TRANSFER: 'badge-transfer', REPLENISH: 'badge-replenish', MONITOR: 'badge-monitor' }[action] || 'badge-monitor';
  return <span className={`badge ${cls}`}>{action}</span>;
}

export function StatCard({ label, value, sub, tone }) {
  return (
    <div className={`stat-card card ${tone ? `tone-${tone}` : ''}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

export function SectionCard({ title, subtitle, actions, children, className = '' }) {
  return (
    <div className={`card section-card ${className}`}>
      {(title || actions) && (
        <div className="section-card-header">
          <div>
            {title && <h3 className="section-card-title">{title}</h3>}
            {subtitle && <div className="section-card-subtitle">{subtitle}</div>}
          </div>
          {actions && <div className="section-card-actions">{actions}</div>}
        </div>
      )}
      <div className="section-card-body">{children}</div>
    </div>
  );
}

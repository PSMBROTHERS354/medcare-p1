import './NetworkRiskMap.css';

// Fixed layout positions per DC id (city-approximate relative layout, not literal geo-coords)
const POSITIONS = {
  'DC-METRO-MUM': { x: 120, y: 200 },
  'DC-METRO-CHN': { x: 340, y: 330 },
  'DC-TIER2-HYD': { x: 300, y: 220 },
  'DC-TIER2-LKO': { x: 260, y: 70 },
  'DC-TIER2-PAT': { x: 440, y: 90 },
};

const STATE_COLOR = {
  Healthy: 'var(--green-600)',
  Excess: 'var(--blue-600)',
  Shortage: 'var(--red-600)',
};

export default function NetworkRiskMap({ data }) {
  const { nodes, edges } = data;

  return (
    <div className="risk-map-wrap">
      <svg viewBox="0 0 520 400" className="risk-map-svg">
        {edges.map((e, i) => {
          const s = POSITIONS[e.source];
          const t = POSITIONS[e.target];
          if (!s || !t) return null;
          const midX = (s.x + t.x) / 2;
          const midY = (s.y + t.y) / 2 - 18;
          return (
            <g key={i}>
              <path
                d={`M ${s.x} ${s.y} Q ${midX} ${midY} ${t.x} ${t.y}`}
                className="risk-map-edge"
                markerEnd="url(#arrow)"
              />
              <text x={midX} y={midY - 4} className="risk-map-edge-label">
                {e.sku_id} · {e.quantity}u · {e.timing_days}d
              </text>
            </g>
          );
        })}

        <defs>
          <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L6,3 L0,6 Z" fill="var(--teal-600)" />
          </marker>
        </defs>

        {nodes.map((n) => {
          const pos = POSITIONS[n.dc_id];
          if (!pos) return null;
          const color = STATE_COLOR[n.state] || 'var(--text-muted)';
          const r = n.type === 'Metro' ? 22 : 17;
          return (
            <g key={n.dc_id} transform={`translate(${pos.x},${pos.y})`} className="risk-map-node">
              <circle r={r} fill={color} fillOpacity="0.14" stroke={color} strokeWidth="2" />
              <circle r={4} fill={color} />
              <text y={r + 16} className="risk-map-node-label">{n.city}</text>
              <text y={r + 30} className="risk-map-node-sub">{n.state}</text>
            </g>
          );
        })}
      </svg>

      <div className="risk-map-legend">
        <span><i style={{ background: 'var(--green-600)' }} /> Healthy</span>
        <span><i style={{ background: 'var(--blue-600)' }} /> Excess</span>
        <span><i style={{ background: 'var(--red-600)' }} /> Shortage</span>
        <span className="legend-sep" />
        <span><i className="legend-line" /> Feasible transfer (from backend)</span>
      </div>
    </div>
  );
}

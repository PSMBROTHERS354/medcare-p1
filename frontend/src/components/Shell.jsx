import { NavLink, Outlet } from 'react-router-dom';
import './Shell.css';

const NAV_ITEMS = [
  { to: '/', label: 'Command Center', icon: CommandIcon },
  { to: '/intelligence', label: 'SKU / DC Intelligence', icon: IntelIcon },
  { to: '/decision-studio', label: 'Decision Studio', icon: StudioIcon },
  { to: '/monitoring', label: 'Monitoring', icon: MonitorIcon },
];

export default function Shell() {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-mark">MC</div>
          <div className="brand-text">
            <div className="brand-name">MedCare Pharma</div>
            <div className="brand-sub">Demand Sensing &amp; Replenishment</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="footer-tag">P1 &middot; Demand Planning &amp; Replenishment</div>
          <div className="footer-scope">E1 not in scope</div>
        </div>
      </aside>

      <main className="workspace">
        <Outlet />
      </main>
    </div>
  );
}

function iconProps() {
  return { width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round' };
}

function CommandIcon() {
  return (<svg {...iconProps()}><rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" /><rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="16" width="7" height="5" rx="1.5" /></svg>);
}
function IntelIcon() {
  return (<svg {...iconProps()}><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg>);
}
function StudioIcon() {
  return (<svg {...iconProps()}><path d="M4 21v-6M4 11V3M12 21v-9M12 8V3M20 21v-4M20 13V3" /><path d="M2 15h4M8 6h8M18 17h4" /></svg>);
}
function MonitorIcon() {
  return (<svg {...iconProps()}><rect x="2" y="4" width="20" height="13" rx="2" /><path d="M8 21h8M12 17v4" /></svg>);
}

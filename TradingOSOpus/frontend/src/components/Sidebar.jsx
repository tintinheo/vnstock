import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, ScanSearch, Target, Briefcase,
  BarChart3, Bell, Settings, TrendingUp
} from 'lucide-react';

const links = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/scanner', icon: ScanSearch, label: 'Scanner' },
  { to: '/decision', icon: Target, label: 'Decision' },
  { to: '/portfolio', icon: Briefcase, label: 'Portfolio' },
  { to: '/backtest', icon: BarChart3, label: 'Backtest' },
  { to: '/signals', icon: Bell, label: 'Signals' },
  { to: '/settings', icon: Settings, label: 'Settings' },
];

export default function Sidebar() {
  return (
    <aside className="w-16 lg:w-56 bg-surface-800 border-r border-surface-700 flex flex-col py-4 shrink-0">
      <div className="flex items-center justify-center lg:justify-start lg:px-4 mb-8">
        <TrendingUp className="w-8 h-8 text-brand-500" />
        <span className="hidden lg:block ml-2 text-lg font-bold text-brand-500">VN Trading</span>
      </div>
      <nav className="flex-1 space-y-1 px-2">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors
               ${isActive ? 'bg-brand-600/20 text-brand-500' : 'text-gray-400 hover:text-gray-100 hover:bg-surface-700'}`
            }>
            <Icon className="w-5 h-5 shrink-0" />
            <span className="hidden lg:block">{label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="hidden lg:block px-4 py-3 mx-2 bg-surface-700/50 rounded-lg text-xs text-gray-500 text-center">
        v3.1 • AI Engine
      </div>
    </aside>
  );
}
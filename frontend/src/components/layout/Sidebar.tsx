import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  AlertOctagon,
  GitFork,
  Activity,
  BrainCircuit,
  Boxes,
  CheckSquare,
  Settings,
  LogOut,
  RefreshCw,
  Building2,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { MockIndicator } from '../common/MockIndicator';

const navItems = [
  { name: 'Overview', to: '/', icon: LayoutDashboard },
  { name: 'Incidents', to: '/incidents', icon: AlertOctagon },
  { name: 'Workflows', to: '/workflows', icon: GitFork },
  { name: 'Recovery Activity', to: '/recovery-activity', icon: Activity },
  { name: 'AI Insights', to: '/ai-insights', icon: BrainCircuit },
  { name: 'Integrations', to: '/integrations', icon: Boxes },
  { name: 'Approvals', to: '/approvals', icon: CheckSquare },
  { name: 'Settings', to: '/settings', icon: Settings },
];

export const Sidebar: React.FC = () => {
  const { tenant, logout } = useAuth();

  return (
    <aside className="w-64 bg-sidebar border-r border-border flex flex-col h-screen fixed inset-y-0 left-0 z-30 select-none">
      {/* Brand Header */}
      <div className="h-16 px-6 flex items-center justify-between border-b border-border/80">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-primary-violet to-primary-pink flex items-center justify-center shadow-glow-purple">
            <RefreshCw className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="font-bold tracking-tight text-text-primary text-base flex items-center gap-1.5">
              REBOOT<span className="text-primary-violet">X</span>
            </div>
            <div className="text-[10px] text-text-secondary uppercase tracking-widest font-medium">
              Autonomous Recovery
            </div>
          </div>
        </div>
      </div>

      {/* Nav List */}
      <div className="flex-1 px-3 py-5 space-y-1 overflow-y-auto">
        <div className="px-3 mb-2 text-[10px] uppercase tracking-wider font-semibold text-text-secondary/70">
          Platform
        </div>
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-medium transition-all duration-200 ${
                isActive
                  ? 'bg-primary-violet/15 text-primary-violet border border-primary-violet/30 shadow-sm'
                  : 'text-text-secondary hover:text-text-primary hover:bg-elevated/60'
              }`
            }
          >
            <item.icon className="w-4 h-4 shrink-0" />
            <span>{item.name}</span>
          </NavLink>
        ))}
      </div>

      {/* Footer Info */}
      <div className="p-4 border-t border-border space-y-3 bg-[#0B0B0F]/90">
        <MockIndicator compact />

        {/* Tenant Profile */}
        <div className="flex items-center justify-between p-2 rounded-xl bg-card border border-border/60">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-7 h-7 rounded-lg bg-elevated border border-border flex items-center justify-center shrink-0">
              <Building2 className="w-3.5 h-3.5 text-primary-violet" />
            </div>
            <div className="truncate">
              <div className="text-xs font-medium text-text-primary truncate">
                {tenant?.tenant_name || 'Tenant'}
              </div>
              <div className="text-[10px] text-text-secondary font-mono truncate">
                {tenant?.tenant_id ? `${tenant.tenant_id.slice(0, 8)}...` : ''}
              </div>
            </div>
          </div>
          <button
            onClick={logout}
            title="Disconnect workspace"
            className="p-1.5 rounded-lg text-text-secondary hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </aside>
  );
};


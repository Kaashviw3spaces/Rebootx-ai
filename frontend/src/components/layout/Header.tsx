import React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { RefreshCw, Server } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface HeaderProps {
  title: string;
  subtitle?: string;
}

export const Header: React.FC<HeaderProps> = ({ title, subtitle }) => {
  const queryClient = useQueryClient();
  const { tenant } = useAuth();
  const [isRefreshing, setIsRefreshing] = React.useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await queryClient.refetchQueries();
    setTimeout(() => setIsRefreshing(false), 500);
  };

  return (
    <header className="h-16 px-8 border-b border-border bg-background/80 backdrop-blur-md sticky top-0 z-20 flex items-center justify-between">
      <div>
        <h1 className="text-lg font-semibold text-text-primary tracking-tight">{title}</h1>
        {subtitle && <p className="text-xs text-text-secondary">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-3">
        {/* API Health Pill */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-400 font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>FastAPI Live</span>
        </div>

        {/* AI Mode Pill */}
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-elevated border border-border text-xs text-text-secondary">
          <Server className="w-3.5 h-3.5 text-primary-violet" />
          <span>AI: <strong className="text-text-primary font-medium">{tenant?.ai_provider || 'mock'}</strong></span>
        </div>

        {/* Refresh Action */}
        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-card hover:bg-elevated border border-border text-xs text-text-primary font-medium transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 text-primary-violet ${isRefreshing ? 'animate-spin' : ''}`} />
          <span className="hidden sm:inline">Refresh</span>
        </button>
      </div>
    </header>
  );
};

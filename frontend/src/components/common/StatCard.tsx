import React, { ReactNode } from 'react';

interface StatCardProps {
  title: string;
  value: string | number;
  description: string;
  icon: ReactNode;
  accentColor?: 'violet' | 'green' | 'amber' | 'pink';
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  description,
  icon,
  accentColor = 'violet',
}) => {
  const iconBgs = {
    violet: 'bg-primary-violet/10 text-primary-violet border-primary-violet/20',
    green: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    amber: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    pink: 'bg-primary-pink/10 text-primary-pink border-primary-pink/20',
  };

  return (
    <div className="relative group overflow-hidden rounded-2xl bg-card border border-border p-6 shadow-card hover:border-zinc-700 transition-all duration-300">
      {/* Subtle top-edge gradient */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary-violet/30 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-medium text-text-secondary tracking-wide uppercase text-[11px]">
          {title}
        </span>
        <div className={`p-2.5 rounded-xl border ${iconBgs[accentColor]} transition-transform duration-300 group-hover:scale-105`}>
          {icon}
        </div>
      </div>

      <div className="space-y-1">
        <div className="text-3xl font-bold tracking-tight text-text-primary">
          {value}
        </div>
        <p className="text-xs text-text-secondary">
          {description}
        </p>
      </div>
    </div>
  );
};


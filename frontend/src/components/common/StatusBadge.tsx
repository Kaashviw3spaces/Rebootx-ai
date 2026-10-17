import React from 'react';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'md' }) => {
  const normalized = status.toUpperCase();
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs';

  let colorClasses = 'bg-zinc-800/80 text-zinc-300 border-zinc-700';

  switch (normalized) {
    case 'RECOVERED':
      colorClasses = 'bg-emerald-950/40 text-emerald-400 border-emerald-800/50';
      break;
    case 'NEEDS_ATTENTION':
    case 'FAILED':
      colorClasses = 'bg-rose-950/40 text-rose-400 border-rose-800/50';
      break;
    case 'EXECUTING':
      colorClasses = 'bg-purple-950/40 text-purple-400 border-purple-800/50 animate-pulse';
      break;
    case 'DIAGNOSING':
    case 'VALIDATING':
    case 'PLANNED':
      colorClasses = 'bg-amber-950/40 text-amber-400 border-amber-800/50';
      break;
    case 'RECEIVED':
      colorClasses = 'bg-blue-950/40 text-blue-400 border-blue-800/50';
      break;
    default:
      break;
  }

  return (
    <span
      className={`inline-flex items-center font-medium rounded-full border ${sizeClasses} ${colorClasses}`}
    >
      <span className="w-1.5 h-1.5 rounded-full mr-1.5 bg-current opacity-70"></span>
      {normalized}
    </span>
  );
};


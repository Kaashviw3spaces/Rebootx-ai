import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { ShieldAlert } from 'lucide-react';

export const MockIndicator: React.FC<{ compact?: boolean; mode?: string }> = ({ compact = false, mode }) => {
  const { tenant } = useAuth();
  if ((mode || tenant?.recovery_mode) === 'real_n8n') return (
    <div className="px-3 py-1.5 rounded-lg bg-primary-violet/10 border border-primary-violet/30 text-xs text-primary-violet">
      {compact ? 'Real n8n Mode' : 'Real n8n recovery enabled. Success requires verified external execution evidence.'}
    </div>
  );
  if (compact) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-500/10 text-amber-300 border border-amber-500/30">
        <ShieldAlert className="w-3 h-3 text-amber-400" />
        Mock-Only Mode
      </span>
    );
  }

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300/90">
      <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
      <span>
        <strong className="font-semibold text-amber-300">Mock Recovery Mode Active:</strong> Orchestration and diagnosis are live; external adapter actions and verifications are simulated.
      </span>
    </div>
  );
};


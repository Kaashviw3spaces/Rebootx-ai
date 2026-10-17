import React from 'react';
import { Link } from 'react-router-dom';
import { Activity, ArrowUpRight, CheckCircle2, AlertTriangle, Clock } from 'lucide-react';
import { IncidentItem } from '../../api/types';
import { StatusBadge } from '../common/StatusBadge';

interface RecoveryActivityFeedProps {
  incidents: IncidentItem[];
}

export const RecoveryActivityFeed: React.FC<RecoveryActivityFeedProps> = ({ incidents }) => {
  if (incidents.length === 0) {
    return (
      <div className="py-8 text-center text-xs text-text-secondary">
        No recent recovery activity recorded.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {incidents.slice(0, 5).map((inc) => {
        const isRecovered = inc.status === 'RECOVERED';
        const isEscalated = inc.status === 'NEEDS_ATTENTION';

        return (
          <div
            key={inc.id}
            className="flex items-center justify-between p-3.5 rounded-xl bg-elevated/40 border border-border/70 hover:border-zinc-700 transition-colors"
          >
            <div className="flex items-center gap-3 min-w-0">
              <div
                className={`p-2 rounded-lg border shrink-0 ${
                  isRecovered
                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                    : isEscalated
                    ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                    : 'bg-primary-violet/10 text-primary-violet border-primary-violet/20'
                }`}
              >
                {isRecovered ? (
                  <CheckCircle2 className="w-4 h-4" />
                ) : isEscalated ? (
                  <AlertTriangle className="w-4 h-4" />
                ) : (
                  <Activity className="w-4 h-4 animate-spin" />
                )}
              </div>

              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-xs font-semibold text-text-primary truncate">
                    {inc.workflow_external_id}
                  </span>
                  <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20 font-mono">
                    MOCK
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[11px] text-text-secondary">
                  <span className="truncate">{inc.failed_step}</span>
                  <span>•</span>
                  <span className="flex items-center gap-1 font-mono text-[10px]">
                    <Clock className="w-3 h-3 text-text-muted" />
                    {new Date(inc.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3 shrink-0">
              <StatusBadge status={inc.status} size="sm" />
              <Link
                to={`/incidents/${inc.id}`}
                className="p-1 rounded-lg text-text-secondary hover:text-text-primary hover:bg-elevated transition-colors"
                title="View incident"
              >
                <ArrowUpRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        );
      })}
    </div>
  );
};


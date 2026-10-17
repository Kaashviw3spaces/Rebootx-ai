import React from 'react';
import { CheckCircle2, AlertTriangle, Clock, ShieldCheck, Play, ArrowRightCircle } from 'lucide-react';
import { TimelineResponse } from '../../api/types';

interface TimelineViewProps {
  timeline: TimelineResponse[];
}

export const TimelineView: React.FC<TimelineViewProps> = ({ timeline }) => {
  if (timeline.length === 0) {
    return (
      <div className="py-8 text-center text-xs text-text-secondary">
        No audit logs recorded for this incident yet.
      </div>
    );
  }

  const getStepIcon = (eventType: string) => {
    switch (eventType) {
      case 'INCIDENT_RECEIVED':
        return <ShieldCheck className="w-4 h-4 text-blue-400" />;
      case 'RECOVERY_ACCEPTED':
      case 'RECOVERY_VALIDATING':
        return <Play className="w-4 h-4 text-amber-400" />;
      case 'RECOVERY_DIAGNOSING':
        return <ArrowRightCircle className="w-4 h-4 text-primary-violet" />;
      case 'RECOVERY_RECOVERED':
        return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
      case 'RECOVERY_ESCALATED':
        return <AlertTriangle className="w-4 h-4 text-rose-400" />;
      default:
        return <Clock className="w-4 h-4 text-text-secondary" />;
    }
  };

  return (
    <div className="relative pl-6 space-y-6 before:absolute before:inset-y-2 before:left-[11px] before:w-0.5 before:bg-border/80">
      {timeline.map((entry, idx) => (
        <div key={entry.id || idx} className="relative group">
          {/* Node Icon */}
          <div className="absolute -left-6 top-1 w-6 h-6 rounded-full bg-card border-2 border-border flex items-center justify-center group-hover:border-primary-violet transition-colors">
            {getStepIcon(entry.event_type)}
          </div>

          {/* Node Content */}
          <div className="p-4 rounded-xl bg-elevated/40 border border-border/80 hover:border-zinc-700 transition-colors">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-1.5">
              <span className="text-xs font-semibold text-text-primary font-mono">
                {entry.event_type}
              </span>
              <span className="text-[11px] text-text-secondary font-mono">
                {new Date(entry.occurred_at).toLocaleString()}
              </span>
            </div>

            <div className="text-xs text-text-secondary flex items-center gap-2 mb-2">
              <span>Actor: <strong className="text-text-primary font-medium">{entry.actor}</strong></span>
            </div>

            {/* Redacted details snippet */}
            {entry.redacted_details && Object.keys(entry.redacted_details).length > 0 && (
              <pre className="text-[11px] font-mono p-2.5 rounded-lg bg-[#09090D] border border-border/50 text-text-secondary overflow-x-auto">
                {JSON.stringify(entry.redacted_details, null, 2)}
              </pre>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};


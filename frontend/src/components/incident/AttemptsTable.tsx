import React from 'react';
import { AttemptResponse } from '../../api/types';
import { StatusBadge } from '../common/StatusBadge';

interface AttemptsTableProps {
  attempts: AttemptResponse[];
}

export const AttemptsTable: React.FC<AttemptsTableProps> = ({ attempts }) => {
  if (attempts.length === 0) {
    return (
      <div className="py-8 text-center text-xs text-text-secondary">
        No recovery attempts executed for this incident.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left border-collapse text-xs">
        <thead>
          <tr className="border-b border-border text-text-secondary uppercase text-[10px] tracking-wider font-semibold">
            <th className="py-3 px-3">#</th>
            <th className="py-3 px-3">Action</th>
            <th className="py-3 px-3">Mode</th>
            <th className="py-3 px-3">Outcome</th>
            <th className="py-3 px-3">Reference / Key</th>
            <th className="py-3 px-3">Started</th>
            <th className="py-3 px-3">Duration</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border/40">
          {attempts.map((att, idx) => {
            const start = new Date(att.started_at).getTime();
            const end = att.ended_at ? new Date(att.ended_at).getTime() : start;
            const durationMs = end - start;

            return (
              <tr key={att.id} className="hover:bg-elevated/40 transition-colors">
                <td className="py-3 px-3 font-mono font-medium text-text-secondary">
                  {idx + 1}
                </td>
                <td className="py-3 px-3 font-mono font-medium text-text-primary">
                  {att.action}
                </td>
                <td className="py-3 px-3">
                  <span className="text-[10px] px-2 py-0.5 rounded-full font-mono bg-amber-500/10 text-amber-300 border border-amber-500/30">
                    MOCK-ONLY
                  </span>
                </td>
                <td className="py-3 px-3">
                  <StatusBadge status={att.outcome || 'IN_PROGRESS'} size="sm" />
                </td>
                <td className="py-3 px-3 font-mono text-[11px] text-text-secondary">
                  {att.external_reference || 'N/A'}
                </td>
                <td className="py-3 px-3 text-text-secondary font-mono text-[11px]">
                  {new Date(att.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </td>
                <td className="py-3 px-3 text-text-secondary font-mono text-[11px]">
                  {durationMs > 0 ? `${durationMs}ms` : '<1ms'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};


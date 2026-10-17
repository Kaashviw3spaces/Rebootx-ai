import { recoveryLabel } from '../common/recoveryLabel';
import React from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { IncidentItem } from '../../api/types';
import { StatusBadge } from '../common/StatusBadge';

interface RecentIncidentsTableProps {
  incidents: IncidentItem[];
}

export const RecentIncidentsTable: React.FC<RecentIncidentsTableProps> = ({ incidents }) => {
  if (incidents.length === 0) {
    return (
      <div className="py-8 text-center text-xs text-text-secondary">
        No recent failure events ingested yet.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left border-collapse text-xs">
        <thead>
          <tr className="border-b border-border/80 text-text-secondary uppercase text-[10px] tracking-wider font-semibold">
            <th className="py-3 px-3">Workflow</th>
            <th className="py-3 px-3">Failed Step</th>
            <th className="py-3 px-3">Category</th>
            <th className="py-3 px-3">Status</th>
            <th className="py-3 px-3">Created</th>
            <th className="py-3 px-3 text-right">Details</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border/40">
          {incidents.slice(0, 5).map((inc) => (
            <tr
              key={inc.id}
              className="hover:bg-elevated/40 transition-colors group cursor-pointer"
            >
              <td className="py-3 px-3 font-medium text-text-primary">
                {inc.workflow_external_id}
              </td>
              <td className="py-3 px-3 text-text-secondary font-mono text-[11px]">
                {inc.failed_step}
              </td>
              <td className="py-3 px-3">
                <span className="font-mono text-[11px] text-primary-violet bg-primary-violet/10 px-2 py-0.5 rounded border border-primary-violet/20">
                  {inc.failure_type}
                </span>
              </td>
              <td className="py-3 px-3">
                <StatusBadge status={inc.status} size="sm" />
                <div className="text-[10px] text-text-secondary mt-1">{recoveryLabel(inc.recovery_mode, inc.verification_outcome)}</div>
              </td>
              <td className="py-3 px-3 text-text-secondary font-mono text-[11px]">
                {new Date(inc.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </td>
              <td className="py-3 px-3 text-right">
                <Link
                  to={`/incidents/${inc.id}`}
                  className="inline-flex items-center gap-1 text-primary-violet hover:text-primary-pink transition-colors font-medium text-[11px]"
                >
                  Inspect
                  <ChevronRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};


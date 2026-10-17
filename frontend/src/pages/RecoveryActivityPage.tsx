import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Activity, ShieldAlert, ArrowUpRight } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { Header } from '../components/layout/Header';
import { StatusBadge } from '../components/common/StatusBadge';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';

export const RecoveryActivityPage: React.FC = () => {
  const { token } = useAuth();

  const { data: incidentsData, isLoading } = useQuery({
    queryKey: ['recoveryActivityList', token],
    queryFn: () => api.getIncidents(token!, { limit: 50 }),
    enabled: !!token,
    refetchInterval: 7000,
  });

  const incidents = incidentsData?.items || [];

  return (
    <div className="space-y-8">
      <Header
        title="Recovery Activity Stream"
        subtitle="Live audit trail of Temporal recovery workflow execution, adapter calls, and verification."
      />

      <div className="px-8 space-y-6 max-w-7xl mx-auto">
        {/* Banner */}
        <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300 flex items-start gap-3">
          <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-semibold block text-amber-200">
              Recovery Action Classification Notice
            </span>
            <p className="text-amber-300/80 leading-relaxed">
              Every recovery action executed below is categorized strictly as <strong>MOCK_RECOVERY</strong>. External notification adapters run in simulated validation mode; no live third-party mutation has occurred.
            </p>
          </div>
        </div>

        {/* Activity Table Card */}
        <div className="rounded-2xl bg-card border border-border p-6 shadow-card">
          {isLoading ? (
            <LoadingSkeleton rows={6} height="h-14" />
          ) : incidents.length === 0 ? (
            <EmptyState
              title="No Recovery Activity"
              description="No automated recovery actions have been triggered yet."
              icon={<Activity className="w-8 h-8 text-primary-violet" />}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-border/80 text-text-secondary uppercase text-[10px] tracking-wider font-semibold">
                    <th className="py-3 px-3">Workflow</th>
                    <th className="py-3 px-3">Failed Step</th>
                    <th className="py-3 px-3">Execution Classification</th>
                    <th className="py-3 px-3">Outcome</th>
                    <th className="py-3 px-3">Verification</th>
                    <th className="py-3 px-3">Timestamp</th>
                    <th className="py-3 px-3 text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {incidents.map((inc) => (
                    <tr key={inc.id} className="hover:bg-elevated/40 transition-colors">
                      <td className="py-3.5 px-3 font-semibold text-text-primary">
                        {inc.workflow_external_id}
                      </td>
                      <td className="py-3.5 px-3 font-mono text-[11px] text-text-secondary">
                        {inc.failed_step}
                      </td>
                      <td className="py-3.5 px-3">
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-mono font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/30">
                          MOCK_RECOVERY
                        </span>
                      </td>
                      <td className="py-3.5 px-3">
                        <StatusBadge status={inc.status} size="sm" />
                      </td>
                      <td className="py-3.5 px-3 font-mono text-[11px]">
                        {inc.verification_outcome ? (
                          <span className="text-emerald-400 font-semibold">{inc.verification_outcome}</span>
                        ) : inc.recovery_reason ? (
                          <span className="text-rose-400 font-semibold">{inc.recovery_reason}</span>
                        ) : (
                          <span className="text-zinc-500 italic">Pending</span>
                        )}
                      </td>
                      <td className="py-3.5 px-3 font-mono text-text-secondary text-[11px]">
                        {new Date(inc.created_at).toLocaleString()}
                      </td>
                      <td className="py-3.5 px-3 text-right">
                        <Link
                          to={`/incidents/${inc.id}`}
                          className="inline-flex items-center gap-1 text-primary-violet hover:text-primary-pink transition-colors font-medium text-xs"
                        >
                          Inspect
                          <ArrowUpRight className="w-3.5 h-3.5" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { CheckSquare, ArrowUpRight, Lock } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { Header } from '../components/layout/Header';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';

export const ApprovalsPage: React.FC = () => {
  const { token } = useAuth();

  const { data: approvals = [], isLoading } = useQuery({
    queryKey: ['approvalsList', token],
    queryFn: () => api.getApprovals(token!),
    enabled: !!token,
    refetchInterval: 7000,
  });

  return (
    <div className="space-y-8">
      <Header
        title="Human Authorization Queue"
        subtitle="Escalated incidents where AI safety policy flagged high impact or ambiguity."
      />

      <div className="px-8 space-y-6 max-w-7xl mx-auto">
        {/* Read-Only Banner */}
        <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300 flex items-start gap-3">
          <Lock className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-semibold block text-amber-200">
              Read-Only Human Review Queue (MVP)
            </span>
            <p className="text-amber-300/80 leading-relaxed">
              Approval and rejection actions are intentionally read-only in this checkpoint. In accordance with REBOOTX safety policy, external mutation buttons remain disabled until production write adapters and cryptographic authorization tokens are provisioned.
            </p>
          </div>
        </div>

        {/* Approvals Table Card */}
        <div className="rounded-2xl bg-card border border-border p-6 shadow-card">
          {isLoading ? (
            <LoadingSkeleton rows={4} height="h-16" />
          ) : approvals.length === 0 ? (
            <EmptyState
              title="No Pending Approvals"
              description="All automated recoveries have completed within deterministic safety parameters. No incidents require human intervention."
              icon={<CheckSquare className="w-8 h-8 text-emerald-400" />}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-border/80 text-text-secondary uppercase text-[10px] tracking-wider font-semibold">
                    <th className="py-3 px-3">Workflow</th>
                    <th className="py-3 px-3">Failed Step</th>
                    <th className="py-3 px-3">Escalation Reason</th>
                    <th className="py-3 px-3">Recommended Next Step</th>
                    <th className="py-3 px-3">Safety Gate</th>
                    <th className="py-3 px-3">Created</th>
                    <th className="py-3 px-3 text-right">Review</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {approvals.map((appr) => (
                    <tr key={appr.incident_id} className="hover:bg-elevated/40 transition-colors">
                      <td className="py-3.5 px-3 font-semibold text-text-primary">
                        {appr.workflow_external_id}
                      </td>
                      <td className="py-3.5 px-3 font-mono text-[11px] text-text-secondary">
                        {appr.failed_step}
                      </td>
                      <td className="py-3.5 px-3 font-mono text-rose-400 font-semibold text-[11px]">
                        {appr.escalation_reason || 'AI_HUMAN_APPROVAL_REQUIRED'}
                      </td>
                      <td className="py-3.5 px-3 font-mono text-emerald-400 text-[11px]">
                        {appr.recommended_action || 'MANUAL_INTERVENTION'}
                      </td>
                      <td className="py-3.5 px-3">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-rose-500/10 text-rose-300 border border-rose-500/30">
                          POLICY_REJECTED
                        </span>
                      </td>
                      <td className="py-3.5 px-3 font-mono text-text-secondary text-[11px]">
                        {new Date(appr.created_at).toLocaleString()}
                      </td>
                      <td className="py-3.5 px-3 text-right">
                        <Link
                          to={`/incidents/${appr.incident_id}`}
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

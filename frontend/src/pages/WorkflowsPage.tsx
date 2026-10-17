import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { GitFork, Boxes, CheckCircle2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { Header } from '../components/layout/Header';
import { StatusBadge } from '../components/common/StatusBadge';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';

export const WorkflowsPage: React.FC = () => {
  const { token } = useAuth();

  const { data: workflows = [], isLoading } = useQuery({
    queryKey: ['workflowsList', token],
    queryFn: () => api.getWorkflows(token!),
    enabled: !!token,
  });

  return (
    <div className="space-y-8">
      <Header
        title="Connected Workflows"
        subtitle="Automation workflows registered with REBOOTX failure detection and recovery."
      />

      <div className="px-8 space-y-6 max-w-7xl mx-auto">
        <div className="rounded-2xl bg-card border border-border p-6 shadow-card">
          {isLoading ? (
            <LoadingSkeleton rows={4} height="h-14" />
          ) : workflows.length === 0 ? (
            <EmptyState
              title="No Workflows Registered"
              description="Register workflows via backend/scripts/provision.py or the n8n integration."
              icon={<GitFork className="w-8 h-8 text-primary-violet" />}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-border/80 text-text-secondary uppercase text-[10px] tracking-wider font-semibold">
                    <th className="py-3 px-3">External Workflow ID</th>
                    <th className="py-3 px-3">Integration</th>
                    <th className="py-3 px-3">Kind / Template</th>
                    <th className="py-3 px-3">Status</th>
                    <th className="py-3 px-3">Total Incidents</th>
                    <th className="py-3 px-3">Latest Event</th>
                    <th className="py-3 px-3">Latest Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {workflows.map((wf) => (
                    <tr key={wf.id} className="hover:bg-elevated/40 transition-colors">
                      <td className="py-3.5 px-3 font-semibold text-text-primary font-mono">
                        {wf.external_id}
                      </td>
                      <td className="py-3.5 px-3">
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-mono bg-primary-violet/10 text-primary-violet border border-primary-violet/20">
                          <Boxes className="w-3 h-3" />
                          {wf.integration_kind}
                        </span>
                      </td>
                      <td className="py-3.5 px-3 font-mono text-text-secondary text-[11px]">
                        {wf.kind}
                      </td>
                      <td className="py-3.5 px-3">
                        <span className="inline-flex items-center gap-1 text-emerald-400 font-medium">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          Active
                        </span>
                      </td>
                      <td className="py-3.5 px-3 font-mono text-text-primary">
                        {wf.incident_count}
                      </td>
                      <td className="py-3.5 px-3 font-mono text-text-secondary text-[11px]">
                        {wf.last_incident_at ? new Date(wf.last_incident_at).toLocaleString() : 'None'}
                      </td>
                      <td className="py-3.5 px-3">
                        {wf.latest_incident_status ? (
                          <StatusBadge status={wf.latest_incident_status} size="sm" />
                        ) : (
                          <span className="text-text-muted italic">Clean</span>
                        )}
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

import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeft,
  Copy,
  Check,
  Clock,
  Activity,
  Workflow,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { Header } from '../components/layout/Header';
import { StatusBadge } from '../components/common/StatusBadge';
import { MockIndicator } from '../components/common/MockIndicator';
import { DiagnosisPanel } from '../components/incident/DiagnosisPanel';
import { TimelineView } from '../components/incident/TimelineView';
import { AttemptsTable } from '../components/incident/AttemptsTable';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { recoveryLabel } from '../components/common/recoveryLabel';

export const IncidentDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const [copied, setCopied] = React.useState(false);

  // Poll incident detail
  const { data: incident, isLoading: isIncLoading } = useQuery({
    queryKey: ['incidentDetail', token, id],
    queryFn: () => api.getIncident(token!, id!),
    enabled: !!token && !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      // Stop polling once in a terminal state
      if (status === 'RECOVERED' || status === 'NEEDS_ATTENTION') return false;
      return 5000;
    },
  });

  // Poll recovery status & diagnosis
  const { data: recovery } = useQuery({
    queryKey: ['incidentRecovery', token, id],
    queryFn: () => api.getRecovery(token!, id!),
    enabled: !!token && !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'RECOVERED' || status === 'NEEDS_ATTENTION') return false;
      return 5000;
    },
  });

  // Query recovery attempts
  const { data: attempts = [] } = useQuery({
    queryKey: ['incidentAttempts', token, id],
    refetchInterval: 5000,
    queryFn: () => api.getAttempts(token!, id!),
    enabled: !!token && !!id,
  });

  // Query timeline
  const { data: timeline = [] } = useQuery({
    queryKey: ['incidentTimeline', token, id],
    refetchInterval: 5000,
    queryFn: () => api.getTimeline(token!, id!),
    enabled: !!token && !!id,
  });

  const handleCopyId = () => {
    if (id) {
      navigator.clipboard.writeText(id);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (isIncLoading) {
    return (
      <div className="p-8 space-y-6 max-w-7xl mx-auto">
        <LoadingSkeleton rows={6} height="h-20" />
      </div>
    );
  }

  if (!incident) {
    return (
      <div className="p-8 max-w-7xl mx-auto text-center space-y-4">
        <h2 className="text-lg font-semibold text-text-primary">Incident Not Found</h2>
        <p className="text-xs text-text-secondary">
          The requested incident does not exist in your tenant workspace.
        </p>
        <Link
          to="/incidents"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary-violet text-white text-xs font-semibold"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Incidents
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <Header
        title={`Incident: ${incident.id.slice(0, 8)}...`}
        subtitle="Signature deep-dive view: Diagnosis, policy gate, orchestration timeline, and recovery attempts."
      />

      <div className="px-8 space-y-8 max-w-7xl mx-auto">
        {/* Back Link & Quick Actions */}
        <div className="flex items-center justify-between">
          <Link
            to="/incidents"
            className="inline-flex items-center gap-1.5 text-xs text-text-secondary hover:text-text-primary transition-colors font-medium"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>All Incidents</span>
          </Link>
          <MockIndicator mode={recovery?.mode || incident.recovery_mode} />
        </div>

        {/* Top Header Card */}
        <div className="rounded-2xl bg-card border border-border p-6 shadow-card space-y-6">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-6 border-b border-border/80">
            <div className="space-y-1.5">
              <div className="flex items-center gap-3">
                <span className="text-lg font-bold text-text-primary tracking-tight font-mono">
                  {incident.id}
                </span>
                <button
                  onClick={handleCopyId}
                  className="p-1.5 rounded-lg bg-elevated hover:bg-zinc-800 border border-border text-text-secondary transition-colors"
                  title="Copy incident UUID"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
                <StatusBadge status={incident.status} />
              </div>
              <div className="flex items-center gap-3 text-xs text-text-secondary">
                <span className="flex items-center gap-1 font-mono">
                  <Workflow className="w-3.5 h-3.5 text-primary-violet" />
                  Workflow: <strong className="text-text-primary">{incident.operation_id}</strong>
                </span>
                <span>•</span>
                <span className="flex items-center gap-1 font-mono">
                  <Clock className="w-3.5 h-3.5 text-text-muted" />
                  {new Date(incident.created_at).toLocaleString()}
                </span>
              </div>
            </div>

            {/* Verification Outcome & Temporal ID */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
              {incident.verification_outcome && (
                <div className="px-3 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-400 font-mono font-medium">
                  Outcome: {incident.verification_outcome}
                </div>
              )}
              {incident.recovery_reason && (
                <div className="px-3 py-1.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-400 font-mono font-medium">
                  Escalation: {incident.recovery_reason}
                </div>
              )}
            </div>
          </div>

          {/* Metadata Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
            <div className="p-3.5 rounded-xl bg-elevated/40 border border-border">
              <span className="text-[10px] uppercase font-semibold text-text-secondary tracking-wider block mb-1">
                Failed Step
              </span>
              <span className="font-mono text-text-primary font-medium">{incident.failed_step}</span>
            </div>
            <div className="p-3.5 rounded-xl bg-elevated/40 border border-border">
              <span className="text-[10px] uppercase font-semibold text-text-secondary tracking-wider block mb-1">
                Source Execution ID
              </span>
              <span className="font-mono text-text-primary font-medium truncate block">
                {incident.source_execution_id}
              </span>
            </div>
            <div className="p-3.5 rounded-xl bg-elevated/40 border border-border">
              <span className="text-[10px] uppercase font-semibold text-text-secondary tracking-wider block mb-1">
                Failure Category
              </span>
              <span className="font-mono text-primary-violet font-medium">{incident.failure_type}</span>
            </div>
            <div className="p-3.5 rounded-xl bg-elevated/40 border border-border">
              <span className="text-[10px] uppercase font-semibold text-text-secondary tracking-wider block mb-1">
                Temporal Workflow
              </span>
              <span className="font-mono text-text-primary font-medium truncate block" title={recovery?.temporal_workflow_id || ''}>
                {recovery?.temporal_workflow_id ? 'rebootx:recovery:v1' : 'None'}
              </span>
            </div>
          </div>
        </div>

        <div className="rounded-2xl bg-card border border-border p-6 text-xs space-y-3">
          <h3 className="font-semibold text-text-primary">Recovery Evidence</h3>
          <p>Provider: n8n ? Mode: {recovery?.mode === 'real_n8n' ? 'Real' : 'Mock'}</p>
          <p>{recoveryLabel(recovery?.mode || incident.recovery_mode, recovery?.verification_outcome || null)}</p>
          <p>Verification: {recovery?.verification_outcome || 'Pending'}</p>
          <p>Resulting execution: {recovery?.external_execution_id || 'None recorded'}</p>
          <p>Action recorded: {recovery?.evidence?.recovered_at || 'Pending'}</p>
          <p>Verified at: {recovery?.evidence?.verified_at || 'Pending'}</p>
          <p>Failure reason: {recovery?.escalation_reason || 'None'}</p>
        </div>

        {/* Section A: AI Advisory Diagnosis */}
        <DiagnosisPanel diagnosis={recovery?.diagnosis || null} />

        {/* Section B & C: Recovery Timeline & Attempts Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Recovery Attempts Table */}
          <div className="rounded-2xl bg-card border border-border p-6 shadow-card space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-border/80">
              <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                <Activity className="w-4 h-4 text-primary-violet" />
                Recovery Execution Attempts
              </h3>
              <span className="text-[11px] px-2 py-0.5 rounded-full font-mono bg-amber-500/10 text-amber-300 border border-amber-500/30">
                {recovery?.mode === 'real_n8n' ? 'n8n PUBLIC API' : 'MOCK ADAPTER'}
              </span>
            </div>
            <AttemptsTable attempts={attempts} />
          </div>

          {/* Audit Log Progression Timeline */}
          <div className="rounded-2xl bg-card border border-border p-6 shadow-card space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-border/80">
              <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                <Clock className="w-4 h-4 text-primary-violet" />
                Immutable Audit Trail
              </h3>
              <span className="text-[11px] font-mono text-text-secondary">
                {timeline.length} events recorded
              </span>
            </div>
            <TimelineView timeline={timeline} />
          </div>
        </div>
      </div>
    </div>
  );
};

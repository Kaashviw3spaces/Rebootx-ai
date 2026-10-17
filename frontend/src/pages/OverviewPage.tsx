import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity, CheckCircle2, AlertTriangle, TrendingUp } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { Header } from '../components/layout/Header';
import { StatCard } from '../components/common/StatCard';
import { TrendsChart } from '../components/dashboard/TrendsChart';
import { RecoveryActivityFeed } from '../components/dashboard/RecoveryActivityFeed';
import { RecentIncidentsTable } from '../components/dashboard/RecentIncidentsTable';
import { SystemHealthPanel } from '../components/dashboard/SystemHealthPanel';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';

export const OverviewPage: React.FC = () => {
  const { token, tenant } = useAuth();

  // Poll summary every 7 seconds
  const { data: summary, isLoading: isSummaryLoading } = useQuery({
    queryKey: ['dashboardSummary', token],
    queryFn: () => api.getDashboardSummary(token!),
    enabled: !!token,
    refetchInterval: 7000,
  });

  // Poll trends every 7 seconds
  const { data: trends = [], isLoading: isTrendsLoading } = useQuery({
    queryKey: ['dashboardTrends', token],
    queryFn: () => api.getDashboardTrends(token!, 7),
    enabled: !!token,
    refetchInterval: 7000,
  });

  // Poll recent incidents every 7 seconds
  const { data: incidentsData, isLoading: isIncidentsLoading } = useQuery({
    queryKey: ['recentIncidents', token],
    queryFn: () => api.getIncidents(token!, { limit: 10 }),
    enabled: !!token,
    refetchInterval: 7000,
  });

  const incidents = incidentsData?.items || [];

  return (
    <div className="space-y-8">
      <Header
        title="Automation Recovery, Under Control."
        subtitle="Monitor failures, understand diagnoses, and track recovery across your workflows."
      />

      <div className="px-8 space-y-8 max-w-7xl mx-auto">
        {/* Row 1: 4 Horizontal Statistics Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {isSummaryLoading ? (
            <LoadingSkeleton rows={4} height="h-32" />
          ) : (
            <>
              <StatCard
                title="Total Incidents"
                value={summary?.total_incidents ?? 0}
                description="Recorded automation failures"
                icon={<Activity className="w-5 h-5" />}
                accentColor="violet"
              />
              <StatCard
                title="Recoveries"
                value={summary?.recovered_incidents ?? 0}
                description={`${summary?.verified_real_recoveries ?? 0} verified real ? ${summary?.simulated_recoveries ?? 0} simulated`}
                icon={<CheckCircle2 className="w-5 h-5" />}
                accentColor="green"
              />
              <StatCard
                title="Needs Attention"
                value={summary?.needs_attention ?? 0}
                description="Escalated for human approval"
                icon={<AlertTriangle className="w-5 h-5" />}
                accentColor="amber"
              />
              <StatCard
                title={summary?.rate_label || "Simulated Recovery Rate"}
                value={`${summary?.recovery_rate ?? 0.0}%`}
                description="Recovery success percentage"
                icon={<TrendingUp className="w-5 h-5" />}
                accentColor="pink"
              />
            </>
          )}
        </div>

        {/* Row 2: Analytics & Recovery Activity */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Trends Chart (2 cols) */}
          <div className="lg:col-span-2 rounded-2xl bg-card border border-border p-6 shadow-card">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold text-text-primary">
                  Incident & Recovery Trends
                </h3>
                <p className="text-xs text-text-secondary">
                  7-day historical timeline of ingested failures and recoveries (all modes)
                </p>
              </div>
              <div className="flex items-center gap-4 text-xs">
                <span className="flex items-center gap-1.5 text-text-secondary">
                  <span className="w-2.5 h-2.5 rounded-full bg-primary-violet"></span>
                  Incidents
                </span>
                <span className="flex items-center gap-1.5 text-text-secondary">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
                  Recovered
                </span>
              </div>
            </div>

            {isTrendsLoading ? (
              <LoadingSkeleton rows={1} height="h-72" />
            ) : (
              <TrendsChart data={trends} />
            )}
          </div>

          {/* Recovery Activity Feed (1 col) */}
          <div className="rounded-2xl bg-card border border-border p-6 shadow-card flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold text-text-primary">
                  Recovery Activity
                </h3>
                <p className="text-xs text-text-secondary">
                  Real-time orchestration stream
                </p>
              </div>
              <Activity className="w-4 h-4 text-primary-violet" />
            </div>

            <div className="flex-1 overflow-y-auto max-h-[320px]">
              {isIncidentsLoading ? (
                <LoadingSkeleton rows={3} height="h-16" />
              ) : (
                <RecoveryActivityFeed incidents={incidents} />
              )}
            </div>
          </div>
        </div>

        {/* Row 3: Recent Incidents & System Overview */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Recent Incidents Table (2 cols) */}
          <div className="lg:col-span-2 rounded-2xl bg-card border border-border p-6 shadow-card">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold text-text-primary">
                  Recent Ingested Incidents
                </h3>
                <p className="text-xs text-text-secondary">
                  Authenticated failure events from connected workflows
                </p>
              </div>
            </div>

            {isIncidentsLoading ? (
              <LoadingSkeleton rows={4} height="h-12" />
            ) : (
              <RecentIncidentsTable incidents={incidents} />
            )}
          </div>

          {/* System Overview Panel (1 col) */}
          <div className="rounded-2xl bg-card border border-border p-6 shadow-card">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold text-text-primary">
                  System Overview
                </h3>
                <p className="text-xs text-text-secondary">
                  Engine & isolation architecture
                </p>
              </div>
            </div>

            <SystemHealthPanel status={tenant} />
          </div>
        </div>
      </div>
    </div>
  );
};

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { BrainCircuit, PieChart as PieIcon, Cpu, Sparkles } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { Header } from '../components/layout/Header';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';

export const AiInsightsPage: React.FC = () => {
  const { token, tenant } = useAuth();

  const { data: incidentsData, isLoading } = useQuery({
    queryKey: ['aiInsightsIncidents', token],
    queryFn: () => api.getIncidents(token!, { limit: 100 }),
    enabled: !!token,
  });

  const incidents = incidentsData?.items || [];

  // Compute category breakdown from actual data
  const categoryCounts: Record<string, number> = {};
  const provenanceCounts: Record<string, number> = {
    'Deterministic Fast-Path': 0,
    'Google Gemma 4 AI': 0,
    'Mock Provider': 0,
  };

  incidents.forEach((inc) => {
    categoryCounts[inc.failure_type] = (categoryCounts[inc.failure_type] || 0) + 1;
    if (inc.diagnosis_source === 'deterministic') {
      provenanceCounts['Deterministic Fast-Path'] += 1;
    } else if (inc.diagnosis_source === 'gemma') {
      provenanceCounts['Google Gemma 4 AI'] += 1;
    } else {
      provenanceCounts['Mock Provider'] += 1;
    }
  });

  return (
    <div className="space-y-8">
      <Header
        title="AI Diagnostic Insights"
        subtitle="Distribution of failure categories, diagnosis provenance, and deterministic safety policy decisions."
      />

      <div className="px-8 space-y-6 max-w-7xl mx-auto">
        {isLoading ? (
          <LoadingSkeleton rows={4} height="h-32" />
        ) : incidents.length === 0 ? (
          <EmptyState
            title="Insufficient Diagnostic Data"
            description="No incidents have been diagnosed yet. Trigger automation failures to observe AI insights."
            icon={<BrainCircuit className="w-8 h-8 text-primary-violet" />}
          />
        ) : (
          <>
            {/* Cards Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Provenance Distribution Card */}
              <div className="rounded-2xl bg-card border border-border p-6 shadow-card space-y-4">
                <div className="flex items-center gap-2 pb-3 border-b border-border/80">
                  <Cpu className="w-4 h-4 text-primary-violet" />
                  <h3 className="text-sm font-semibold text-text-primary">Diagnosis Provenance</h3>
                </div>
                <div className="space-y-3">
                  {Object.entries(provenanceCounts).map(([name, count]) => {
                    const pct = Math.round((count / (incidents.length || 1)) * 100);
                    return (
                      <div key={name} className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-text-secondary">{name}</span>
                          <span className="font-mono text-text-primary font-bold">
                            {count} ({pct}%)
                          </span>
                        </div>
                        <div className="w-full bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="h-full bg-primary-violet rounded-full transition-all"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Top Failure Categories */}
              <div className="rounded-2xl bg-card border border-border p-6 shadow-card space-y-4">
                <div className="flex items-center gap-2 pb-3 border-b border-border/80">
                  <PieIcon className="w-4 h-4 text-primary-pink" />
                  <h3 className="text-sm font-semibold text-text-primary">Failure Categories</h3>
                </div>
                <div className="space-y-3">
                  {Object.entries(categoryCounts).map(([cat, count]) => {
                    const pct = Math.round((count / (incidents.length || 1)) * 100);
                    return (
                      <div key={cat} className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-text-secondary font-mono truncate">{cat}</span>
                          <span className="font-mono text-text-primary font-bold">
                            {count} ({pct}%)
                          </span>
                        </div>
                        <div className="w-full bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                          <div
                            className="h-full bg-emerald-400 rounded-full transition-all"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Engine Profile */}
              <div className="rounded-2xl bg-card border border-border p-6 shadow-card space-y-4">
                <div className="flex items-center gap-2 pb-3 border-b border-border/80">
                  <Sparkles className="w-4 h-4 text-amber-400" />
                  <h3 className="text-sm font-semibold text-text-primary">Diagnostic Engine</h3>
                </div>
                <div className="space-y-3 text-xs">
                  <div className="p-3 rounded-xl bg-elevated/50 border border-border flex justify-between">
                    <span className="text-text-secondary">Configured Model</span>
                    <span className="font-mono text-text-primary font-bold">{tenant?.ai_model}</span>
                  </div>
                  <div className="p-3 rounded-xl bg-elevated/50 border border-border flex justify-between">
                    <span className="text-text-secondary">Provider</span>
                    <span className="font-mono text-primary-violet font-bold">{tenant?.ai_provider}</span>
                  </div>
                  <div className="p-3 rounded-xl bg-elevated/50 border border-border flex justify-between">
                    <span className="text-text-secondary">Safety Gate</span>
                    <span className="font-mono text-emerald-400 font-bold">Enforced (Deterministic)</span>
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

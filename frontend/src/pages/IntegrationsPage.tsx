import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { ShieldCheck, CheckCircle2, AlertCircle, Copy, Check } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { Header } from '../components/layout/Header';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';

export const IntegrationsPage: React.FC = () => {
  const { token } = useAuth();
  const [copiedId, setCopiedId] = React.useState<string | null>(null);

  const { data: integrations = [], isLoading } = useQuery({
    queryKey: ['integrationsList', token],
    queryFn: () => api.getIntegrations(token!),
    enabled: !!token,
  });

  const handleCopy = (val: string) => {
    navigator.clipboard.writeText(val);
    setCopiedId(val);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="space-y-8">
      <Header
        title="Connected Automation Platforms"
        subtitle="Manage automation engine webhooks, error triggers, and authenticated endpoints."
      />

      <div className="px-8 space-y-6 max-w-7xl mx-auto">
        {/* Security Banner */}
        <div className="p-4 rounded-2xl bg-card border border-border flex items-start gap-3 text-xs text-text-secondary">
          <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-semibold text-text-primary block">
              Cryptographic Integrity & Secret Isolation
            </span>
            <p className="leading-relaxed">
              Integrations use exact-byte HMAC-SHA256 signatures with timestamp skew limits (300s). Signing secrets are resolved exclusively by server-side environment variables and are never exposed via API endpoints or stored in the frontend.
            </p>
          </div>
        </div>

        {/* Integration Cards Grid */}
        {isLoading ? (
          <LoadingSkeleton rows={2} height="h-44" />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {integrations.map((integ) => {
              const hasDelivered = !!integ.last_event_at;

              return (
                <div
                  key={integ.id}
                  className="rounded-2xl bg-card border border-border p-6 shadow-card space-y-4 hover:border-zinc-700 transition-colors"
                >
                  <div className="flex items-center justify-between pb-4 border-b border-border/80">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#EA4B71] to-[#FF6D5A] flex items-center justify-center font-bold text-white shadow-sm">
                        n8n
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-text-primary capitalize">
                          {integ.kind} Automation Engine
                        </h3>
                        <span className="text-[11px] text-text-secondary font-mono">
                          ID: {integ.id.slice(0, 8)}...
                        </span>
                      </div>
                    </div>

                    {hasDelivered ? (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Verified Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                        <AlertCircle className="w-3.5 h-3.5" />
                        Awaiting Events
                      </span>
                    )}
                  </div>

                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between p-2.5 rounded-xl bg-elevated/40 border border-border">
                      <span className="text-text-secondary">Integration ID</span>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-text-primary font-bold">
                          {integ.id}
                        </span>
                        <button
                          onClick={() => handleCopy(integ.id)}
                          className="p-1 rounded hover:bg-zinc-800 text-text-secondary"
                        >
                          {copiedId === integ.id ? (
                            <Check className="w-3 h-3 text-emerald-400" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                        </button>
                      </div>
                    </div>

                    <div className="flex justify-between p-2.5 rounded-xl bg-elevated/40 border border-border">
                      <span className="text-text-secondary">Connected Workflows</span>
                      <span className="font-mono text-text-primary font-bold">
                        {integ.workflow_count} registered
                      </span>
                    </div>

                    <div className="flex justify-between p-2.5 rounded-xl bg-elevated/40 border border-border">
                      <span className="text-text-secondary">Last Observed Delivery</span>
                      <span className="font-mono text-text-primary">
                        {integ.last_event_at
                          ? new Date(integ.last_event_at).toLocaleString()
                          : 'No events yet'}
                      </span>
                    </div>
                  </div>

                  <div className="pt-2">
                    <span className="text-[11px] text-text-secondary block mb-1 font-semibold uppercase tracking-wider">
                      Setup Instructions
                    </span>
                    <p className="text-[11px] text-text-secondary leading-relaxed bg-elevated/30 p-3 rounded-xl border border-border">
                      Import <code className="text-primary-violet font-mono">integrations/n8n/workflows/rebootx_error_handler.json</code> into your n8n workspace. Set the Error Workflow setting on your primary workflows to route failures securely into REBOOTX.
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

import React from 'react';
import { Building2, Server, Shield, Database, Lock, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { Header } from '../components/layout/Header';

export const SettingsPage: React.FC = () => {
  const { tenant, logout } = useAuth();

  return (
    <div className="space-y-8">
      <Header
        title="Workspace & Platform Settings"
        subtitle="Tenant identity parameters, cryptographic credentials isolation, and recovery modes."
      />

      <div className="px-8 space-y-6 max-w-4xl mx-auto">
        {/* Tenant Identity Card */}
        <div className="rounded-2xl bg-card border border-border p-6 shadow-card space-y-4">
          <div className="flex items-center gap-2 pb-4 border-b border-border/80">
            <Building2 className="w-5 h-5 text-primary-violet" />
            <h3 className="text-sm font-semibold text-text-primary">Tenant Organization</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div className="p-3.5 rounded-xl bg-elevated/40 border border-border">
              <span className="text-[10px] uppercase font-semibold text-text-secondary tracking-wider block mb-1">
                Tenant Name
              </span>
              <span className="font-semibold text-text-primary text-sm">
                {tenant?.tenant_name || 'Active Workspace'}
              </span>
            </div>

            <div className="p-3.5 rounded-xl bg-elevated/40 border border-border">
              <span className="text-[10px] uppercase font-semibold text-text-secondary tracking-wider block mb-1">
                Tenant ID (UUID)
              </span>
              <span className="font-mono text-text-primary text-xs">
                {tenant?.tenant_id || 'N/A'}
              </span>
            </div>
          </div>
        </div>

        {/* Runtime Environment Card */}
        <div className="rounded-2xl bg-card border border-border p-6 shadow-card space-y-4">
          <div className="flex items-center gap-2 pb-4 border-b border-border/80">
            <Server className="w-5 h-5 text-primary-pink" />
            <h3 className="text-sm font-semibold text-text-primary">Runtime Engine & Telemetry</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div className="p-3.5 rounded-xl bg-elevated/40 border border-border">
              <span className="text-[10px] uppercase font-semibold text-text-secondary tracking-wider block mb-1">
                Environment
              </span>
              <span className="font-mono font-semibold text-text-primary">
                {tenant?.app_env || 'development'}
              </span>
            </div>

            <div className="p-3.5 rounded-xl bg-elevated/40 border border-border">
              <span className="text-[10px] uppercase font-semibold text-text-secondary tracking-wider block mb-1">
                Temporal Task Queue
              </span>
              <span className="font-mono font-semibold text-text-primary">
                {tenant?.temporal_task_queue || 'rebootx-recovery-v1'}
              </span>
            </div>

            <div className="p-3.5 rounded-xl bg-elevated/40 border border-border">
              <span className="text-[10px] uppercase font-semibold text-text-secondary tracking-wider block mb-1">
                AI Diagnosis Provider
              </span>
              <span className="font-mono font-semibold text-primary-violet">
                {tenant?.ai_provider || 'mock'} ({tenant?.ai_model || 'gemma-4-26b-a4b-it'})
              </span>
            </div>

            <div className="p-3.5 rounded-xl bg-elevated/40 border border-border">
              <span className="text-[10px] uppercase font-semibold text-text-secondary tracking-wider block mb-1">
                Recovery Execution Mode
              </span>
              <span className="font-mono font-semibold text-amber-300">
                {tenant?.recovery_mode === 'real_n8n' ? 'Real n8n (verification required)' : 'Mock (Safe Simulation)'}
              </span>
            </div>
          </div>
        </div>

        {/* Security & Credentials Isolation Card */}
        <div className="rounded-2xl bg-card border border-border p-6 shadow-card space-y-4">
          <div className="flex items-center gap-2 pb-4 border-b border-border/80">
            <Shield className="w-5 h-5 text-emerald-400" />
            <h3 className="text-sm font-semibold text-text-primary">Security Architecture</h3>
          </div>

          <div className="space-y-3 text-xs text-text-secondary">
            <div className="p-3.5 rounded-xl bg-elevated/30 border border-border flex items-start gap-3">
              <Lock className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <div>
                <strong className="text-text-primary block mb-0.5">Zero Secret Leakage Invariant</strong>
                <span>
                  HMAC webhook secrets and database passwords exist exclusively on the server. No secrets are passed to the frontend or exposed in bundle code.
                </span>
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-elevated/30 border border-border flex items-start gap-3">
              <Database className="w-4 h-4 text-primary-violet shrink-0 mt-0.5" />
              <div>
                <strong className="text-text-primary block mb-0.5">Strict Tenant Database Isolation</strong>
                <span>
                  Every incident, recovery outbox record, and audit entry includes a foreign key constraint to <code className="font-mono text-zinc-300">tenant_id</code>. Cross-tenant access is rejected with HTTP 404/401 at the database layer.
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Workspace Disconnect Card */}
        <div className="rounded-2xl bg-card border border-rose-900/40 p-6 shadow-card flex items-center justify-between">
          <div>
            <h4 className="text-sm font-semibold text-rose-300">Disconnect Active Workspace</h4>
            <p className="text-xs text-text-secondary mt-0.5">
              Clears the in-memory bearer token from the current session.
            </p>
          </div>
          <button
            onClick={logout}
            className="px-4 py-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-300 text-xs font-semibold flex items-center gap-2 transition-colors"
          >
            <LogOut className="w-4 h-4" />
            <span>Disconnect Session</span>
          </button>
        </div>
      </div>
    </div>
  );
};

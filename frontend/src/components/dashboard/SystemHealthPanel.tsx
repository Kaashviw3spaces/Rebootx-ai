import React from 'react';
import { Server, ShieldCheck, Cpu, Database, CheckCircle2 } from 'lucide-react';
import { SystemStatusResponse } from '../../api/types';

interface SystemHealthPanelProps {
  status: SystemStatusResponse | null;
}

export const SystemHealthPanel: React.FC<SystemHealthPanelProps> = ({ status }) => {
  return (
    <div className="space-y-4">
      {/* FastAPI Ingestion Service */}
      <div className="flex items-center justify-between p-3.5 rounded-xl bg-elevated/40 border border-border/70">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <Server className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs font-semibold text-text-primary">FastAPI Ingestion Engine</div>
            <div className="text-[11px] text-text-secondary font-mono">HMAC SHA-256 Validated • :8000</div>
          </div>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
          <CheckCircle2 className="w-3.5 h-3.5" />
          <span>Active</span>
        </div>
      </div>

      {/* Recovery Execution Mode */}
      <div className="flex items-center justify-between p-3.5 rounded-xl bg-elevated/40 border border-border/70">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <ShieldCheck className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs font-semibold text-text-primary">Recovery Execution Mode</div>
            <div className="text-[11px] text-text-secondary font-mono">Temporal Durable Workflow • {status?.recovery_mode || 'mock-only'}</div>
          </div>
        </div>
        <span className="text-[11px] px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30 font-semibold font-mono">
          {status?.recovery_mode === 'real_n8n' ? 'REAL n8n' : 'MOCK-ONLY'}
        </span>
      </div>

      {/* AI Diagnosis Provider */}
      <div className="flex items-center justify-between p-3.5 rounded-xl bg-elevated/40 border border-border/70">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-primary-violet/10 text-primary-violet border border-primary-violet/20">
            <Cpu className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs font-semibold text-text-primary">Configured Diagnosis Engine</div>
            <div className="text-[11px] text-text-secondary font-mono">
              Provider: {status?.ai_provider || 'mock'} • {status?.ai_model || 'gemma-4-26b-a4b-it'}
            </div>
          </div>
        </div>
        <span className="text-[11px] px-2 py-0.5 rounded bg-primary-violet/10 text-primary-violet border border-primary-violet/30 font-mono">
          {status?.ai_provider || 'mock'}
        </span>
      </div>

      {/* Persistence Architecture */}
      <div className="flex items-center justify-between p-3.5 rounded-xl bg-elevated/40 border border-border/70">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-zinc-800 text-zinc-300 border border-zinc-700">
            <Database className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs font-semibold text-text-primary">Storage Isolation</div>
            <div className="text-[11px] text-text-secondary font-mono">
              Tenant: {status?.tenant_name || 'Active Workspace'} (Scoped)
            </div>
          </div>
        </div>
        <span className="text-[11px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 font-mono">
          Schema managed by Alembic
        </span>
      </div>
    </div>
  );
};


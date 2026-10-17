import React, { useState } from 'react';
import { RefreshCw, KeyRound, ShieldAlert, ArrowRight, Info } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const LoginPage: React.FC = () => {
  const [tokenInput, setTokenInput] = useState('');
  const { login, isLoading, error } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tokenInput.trim()) return;
    await login(tokenInput);
  };

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-6 relative overflow-hidden">
      {/* Background glow */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[350px] bg-primary-violet/10 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-md relative z-10">
        {/* Brand Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-gradient-to-tr from-primary-violet to-primary-pink shadow-glow-purple mb-4">
            <RefreshCw className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">
            REBOOT<span className="text-primary-violet">X</span> Dashboard
          </h1>
          <p className="text-xs text-text-secondary mt-1">
            Autonomous failure detection, AI diagnosis & recovery orchestration
          </p>
        </div>

        {/* Card */}
        <div className="rounded-2xl bg-card border border-border p-8 shadow-card backdrop-blur-sm">
          <div className="flex items-center gap-2 mb-6 pb-4 border-b border-border/80 text-text-primary text-sm font-semibold">
            <KeyRound className="w-4 h-4 text-primary-violet" />
            <span>Connect to Tenant Workspace</span>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="token" className="block text-xs font-medium text-text-secondary mb-1.5">
                Tenant Read Token
              </label>
              <input
                id="token"
                type="password"
                placeholder="Paste your 32+ character tenant read token"
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl bg-elevated/70 border border-border text-text-primary text-xs focus:outline-none focus:border-primary-violet transition-colors font-mono"
                required
                autoFocus
              />
              <span className="text-[11px] text-text-secondary/70 mt-1 block">
                Generated via <code className="font-mono text-primary-violet">backend/scripts/provision.py</code>
              </span>
            </div>

            {error && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-start gap-2">
                <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading || !tokenInput.trim()}
              className="w-full py-2.5 px-4 rounded-xl bg-primary-violet hover:bg-primary-purple text-white text-xs font-semibold tracking-wide flex items-center justify-center gap-2 transition-all shadow-glow-purple disabled:opacity-50 disabled:pointer-events-none"
            >
              {isLoading ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <span>Authenticate & Enter</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Security Notice */}
          <div className="mt-6 pt-5 border-t border-border/70 space-y-2">
            <div className="flex items-start gap-2 text-[11px] text-text-secondary leading-relaxed">
              <Info className="w-4 h-4 text-primary-violet shrink-0 mt-0.5" />
              <span>
                <strong>In-Memory Token Security:</strong> This token is held strictly in application memory and is never written to disk, <code className="font-mono text-zinc-300">localStorage</code>, <code className="font-mono text-zinc-300">sessionStorage</code>, or browser cookies.
              </span>
            </div>
            <p className="text-[10px] text-text-secondary/60 text-center">
              Local demo authentication architecture. For production deployments, a secure HTTP-only server-managed session layer is recommended.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};


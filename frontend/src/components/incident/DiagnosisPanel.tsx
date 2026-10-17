import React from 'react';
import { Brain, Sparkles, ShieldCheck, AlertCircle, ArrowRight } from 'lucide-react';
import { DiagnosisResponse } from '../../api/types';

interface DiagnosisPanelProps {
  diagnosis: DiagnosisResponse | null;
}

export const DiagnosisPanel: React.FC<DiagnosisPanelProps> = ({ diagnosis }) => {
  if (!diagnosis) {
    return (
      <div className="rounded-2xl bg-card border border-border p-6 shadow-card">
        <div className="flex items-center gap-2 mb-4">
          <Brain className="w-5 h-5 text-primary-violet" />
          <h3 className="text-sm font-semibold text-text-primary">AI Advisory Diagnosis</h3>
        </div>
        <p className="text-xs text-text-secondary">
          Diagnosis has not yet been executed for this incident, or validation failed before inference.
        </p>
      </div>
    );
  }

  // Determine provenance styling
  const provenance = diagnosis.source || diagnosis.provider;
  let provLabel = 'Mock Provider';
  let provColor = 'bg-zinc-800 text-zinc-300 border-zinc-700';

  if (provenance === 'gemma') {
    provLabel = 'Gemma 4 AI (gemma-4-26b-a4b-it)';
    provColor = 'bg-primary-violet/15 text-primary-violet border-primary-violet/30';
  } else if (provenance === 'deterministic') {
    provLabel = 'Deterministic Fast-Path';
    provColor = 'bg-blue-500/15 text-blue-400 border-blue-500/30';
  } else if (provenance === 'mock') {
    provLabel = 'Mock Diagnostic Provider (mock-only)';
    provColor = 'bg-amber-500/15 text-amber-300 border-amber-500/30';
  }

  const confidencePct = Math.round(diagnosis.confidence * 100);

  return (
    <div className="rounded-2xl bg-card border border-border p-6 shadow-card space-y-6">
      {/* Panel Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-border/80">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-primary-violet/10 text-primary-violet border border-primary-violet/20">
            <Brain className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
              Autonomous Failure Diagnosis
              <Sparkles className="w-4 h-4 text-primary-pink" />
            </h3>
            <div className="text-xs text-text-secondary">
              Strict 7-Field Pydantic Schema • Safety Policy Gate Enforced
            </div>
          </div>
        </div>

        {/* Provenance Pill */}
        <div className={`px-3 py-1 rounded-full text-xs font-medium border self-start sm:self-auto ${provColor}`}>
          Provenance: <strong className="font-semibold">{provLabel}</strong>
        </div>
      </div>

      {/* Primary Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Category */}
        <div className="p-4 rounded-xl bg-elevated/50 border border-border">
          <span className="text-[11px] font-semibold text-text-secondary uppercase tracking-wider block mb-1">
            Identified Category
          </span>
          <span className="text-sm font-bold text-text-primary font-mono text-primary-violet">
            {diagnosis.failure_category}
          </span>
        </div>

        {/* Recommended Action */}
        <div className="p-4 rounded-xl bg-elevated/50 border border-border">
          <span className="text-[11px] font-semibold text-text-secondary uppercase tracking-wider block mb-1">
            Recommended Action
          </span>
          <div className="flex items-center gap-1.5 text-sm font-bold text-emerald-400 font-mono">
            <ArrowRight className="w-4 h-4" />
            <span>{diagnosis.recommended_action}</span>
          </div>
        </div>

        {/* Confidence Score Meter */}
        <div className="p-4 rounded-xl bg-elevated/50 border border-border">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-semibold text-text-secondary uppercase tracking-wider">
              Diagnostic Confidence
            </span>
            <span className="text-xs font-mono font-bold text-text-primary">
              {confidencePct}%
            </span>
          </div>
          <div className="w-full bg-zinc-800 rounded-full h-2 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                confidencePct >= 75
                  ? 'bg-gradient-to-r from-primary-violet to-emerald-400'
                  : 'bg-amber-400'
              }`}
              style={{ width: `${confidencePct}%` }}
            />
          </div>
        </div>
      </div>

      {/* Safety Policy & Human Approval Status */}
      <div className="p-4 rounded-xl bg-elevated/30 border border-border flex items-start gap-3">
        {diagnosis.requires_human_approval ? (
          <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
        ) : (
          <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
        )}
        <div className="text-xs">
          <div className="font-semibold text-text-primary flex items-center gap-2">
            Safety Policy Decision:
            <span className="font-mono text-primary-violet">{diagnosis.policy_reason}</span>
          </div>
          <p className="text-text-secondary mt-0.5">
            {diagnosis.requires_human_approval
              ? 'Safety threshold triggered: This incident requires human review before executing high-impact external actions.'
              : 'Deterministic safety policy passed: Recovery action authorized within tenant security parameters.'}
          </p>
        </div>
      </div>

      {/* Root Cause & Explanation */}
      <div className="space-y-3">
        <div>
          <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-1">
            Root Cause Analysis
          </h4>
          <p className="text-xs text-text-primary bg-elevated/40 p-3.5 rounded-xl border border-border font-mono leading-relaxed">
            {diagnosis.root_cause}
          </p>
        </div>

        <div>
          <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-1">
            Technical Explanation
          </h4>
          <p className="text-xs text-text-secondary bg-elevated/40 p-3.5 rounded-xl border border-border leading-relaxed">
            {diagnosis.explanation}
          </p>
        </div>
      </div>
    </div>
  );
};

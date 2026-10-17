export interface SystemStatusResponse {
  status: string;
  tenant_id: string;
  tenant_name: string;
  app_env: string;
  recovery_mode: 'mock-only' | 'real_n8n';
  ai_provider: string;
  ai_model: string;
  temporal_task_queue: string;
}

export interface DashboardSummaryResponse {
  total_incidents: int_or_number;
  recovered_incidents: number;
  verified_real_recoveries: number;
  simulated_recoveries: number;
  needs_attention: number;
  active_recovering: number;
  recovery_rate: number;
  rate_label: string;
  mode: 'mock-only' | 'real_n8n';
  ai_provider: string;
}

type int_or_number = number;

export interface TrendPoint {
  date: string;
  incidents_created: number;
  incidents_recovered: number;
  incidents_escalated: number;
}

export interface IncidentItem {
  recovery_mode: 'mock-only' | 'real_n8n';
  id: string;
  workflow_id: string;
  workflow_external_id: string;
  event_id: string;
  source: string;
  source_execution_id: string;
  failed_step: string;
  operation_id: string;
  failure_type: string;
  status: 'RECEIVED' | 'VALIDATING' | 'DIAGNOSING' | 'PLANNED' | 'EXECUTING' | 'VERIFYING' | 'RECOVERED' | 'NEEDS_ATTENTION';
  event_timestamp: string;
  created_at: string;
  resolved_at: string | null;
  recovery_reason: string | null;
  verification_outcome: string | null;
  diagnosis_summary: string | null;
  diagnosis_source: string | null;
}

export interface IncidentListResponse {
  items: IncidentItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface WorkflowSummaryResponse {
  id: string;
  external_id: string;
  kind: string;
  enabled: boolean;
  integration_id: string;
  integration_kind: string;
  incident_count: number;
  last_incident_at: string | null;
  latest_incident_status: string | null;
}

export interface IntegrationSummaryResponse {
  id: string;
  kind: string;
  enabled: boolean;
  workflow_count: number;
  last_event_at: string | null;
}

export interface ApprovalItemResponse {
  incident_id: string;
  workflow_external_id: string;
  failed_step: string;
  failure_type: string;
  status: string;
  escalation_reason: string | null;
  requires_human_approval: boolean;
  recommended_action: string | null;
  diagnosis_source: string | null;
  created_at: string;
}

export interface DiagnosisResponse {
  status: string;
  failure_category: string;
  root_cause: string;
  explanation: string;
  recommended_action: string;
  confidence: number;
  requires_human_approval: boolean;
  alternative_actions: string[];
  provider: string;
  source: string;
  model_id: string;
  requested_model_id: string;
  diagnosed_at: string;
  fallback_reason: string | null;
  policy_reason: string;
}

export interface RecoveryResponse {
  provider: string;
  external_execution_id: string | null;
  evidence: Record<string, string> | null;
  incident_id: string;
  status: string;
  mode: string;
  verification_outcome: string | null;
  escalation_reason: string | null;
  temporal_workflow_id: string | null;
  dispatch_status: string;
  dispatch_attempts: number;
  dispatch_error: string | null;
  diagnosis: DiagnosisResponse | null;
}

export interface AttemptResponse {
  id: string;
  action: string;
  adapter: string | null;
  outcome: string | null;
  failure_reason: string | null;
  external_reference: string | null;
  started_at: string;
  ended_at: string | null;
}

export interface TimelineResponse {
  id: string;
  actor: string;
  event_type: string;
  redacted_details: Record<string, unknown>;
  occurred_at: string;
}

export interface IncidentDetail {
  recovery_mode: 'mock-only' | 'real_n8n';
  id: string;
  workflow_id: string;
  event_id: string;
  source: string;
  source_execution_id: string;
  failed_step: string;
  operation_id: string;
  failure_type: string;
  error_details: {
    category: string;
    message: string;
    http_status?: number;
  };
  status: string;
  verification_outcome?: string | null;
  recovery_reason?: string | null;
  event_timestamp: string;
  created_at: string;
}

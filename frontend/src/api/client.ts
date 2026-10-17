import {
  ApprovalItemResponse,
  AttemptResponse,
  DashboardSummaryResponse,
  IncidentDetail,
  IncidentListResponse,
  IntegrationSummaryResponse,
  RecoveryResponse,
  SystemStatusResponse,
  TimelineResponse,
  TrendPoint,
  WorkflowSummaryResponse,
} from './types';

async function fetchWithAuth<T>(url: string, token: string): Promise<T> {
  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!res.ok) {
    if (res.status === 401) {
      throw new Error('Unauthorized: Tenant session expired or token invalid');
    }
    const text = await res.text();
    throw new Error(`API Error ${res.status}: ${text || res.statusText}`);
  }

  return res.json();
}

export const api = {
  getSystemStatus: (token: string): Promise<SystemStatusResponse> =>
    fetchWithAuth('/api/v1/system/status', token),

  getDashboardSummary: (token: string): Promise<DashboardSummaryResponse> =>
    fetchWithAuth('/api/v1/dashboard/summary', token),

  getDashboardTrends: (token: string, days = 7): Promise<TrendPoint[]> =>
    fetchWithAuth(`/api/v1/dashboard/trends?days=${days}`, token),

  getIncidents: (
    token: string,
    params?: { limit?: number; offset?: number; status?: string; failure_type?: string; search?: string }
  ): Promise<IncidentListResponse> => {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.set('limit', String(params.limit));
    if (params?.offset) searchParams.set('offset', String(params.offset));
    if (params?.status) searchParams.set('status', params.status);
    if (params?.failure_type) searchParams.set('failure_type', params.failure_type);
    if (params?.search) searchParams.set('search', params.search);

    const query = searchParams.toString();
    return fetchWithAuth(`/api/v1/incidents${query ? `?${query}` : ''}`, token);
  },

  getIncident: (token: string, incidentId: string): Promise<IncidentDetail> =>
    fetchWithAuth(`/api/v1/incidents/${incidentId}`, token),

  getRecovery: (token: string, incidentId: string): Promise<RecoveryResponse> =>
    fetchWithAuth(`/api/v1/incidents/${incidentId}/recovery`, token),

  getAttempts: (token: string, incidentId: string): Promise<AttemptResponse[]> =>
    fetchWithAuth(`/api/v1/incidents/${incidentId}/attempts`, token),

  getTimeline: (token: string, incidentId: string): Promise<TimelineResponse[]> =>
    fetchWithAuth(`/api/v1/incidents/${incidentId}/timeline`, token),

  getWorkflows: (token: string): Promise<WorkflowSummaryResponse[]> =>
    fetchWithAuth('/api/v1/workflows', token),

  getIntegrations: (token: string): Promise<IntegrationSummaryResponse[]> =>
    fetchWithAuth('/api/v1/integrations', token),

  getApprovals: (token: string): Promise<ApprovalItemResponse[]> =>
    fetchWithAuth('/api/v1/approvals', token),
};


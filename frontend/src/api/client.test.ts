import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api } from './client';

describe('Frontend API Client', () => {
  const dummyToken = 'synthetic-test-token-at-least-32-characters-long';

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('attaches Bearer token in request headers', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'ok', tenant_name: 'Test Tenant' }),
    });
    vi.stubGlobal('fetch', mockFetch);

    const result = await api.getSystemStatus(dummyToken);
    expect(result.status).toBe('ok');
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/v1/system/status',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: `Bearer ${dummyToken}`,
        }),
      })
    );
  });

  it('constructs query parameters correctly for incident listing', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], total: 0, limit: 10, offset: 20 }),
    });
    vi.stubGlobal('fetch', mockFetch);

    await api.getIncidents(dummyToken, {
      limit: 10,
      offset: 20,
      status: 'RECOVERED',
      search: 'payment',
    });

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/v1/incidents?limit=10&offset=20&status=RECOVERED&search=payment',
      expect.any(Object)
    );
  });

  it('throws descriptive error on 401 unauthorized', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      text: async () => 'Invalid tenant credentials',
    });
    vi.stubGlobal('fetch', mockFetch);

    await expect(api.getSystemStatus('bad-token')).rejects.toThrow(
      'Unauthorized: Tenant session expired or token invalid'
    );
  });

  it('throws descriptive error on generic API failure', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      text: async () => 'Internal error detail',
    });
    vi.stubGlobal('fetch', mockFetch);

    await expect(api.getDashboardSummary(dummyToken)).rejects.toThrow(
      'API Error 500: Internal error detail'
    );
  });
});


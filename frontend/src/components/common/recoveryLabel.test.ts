import { describe, expect, it } from 'vitest';
import { recoveryLabel } from './recoveryLabel';

describe('Recovery provenance labels', () => {
  it('keeps mock successes visibly simulated', () => {
    expect(recoveryLabel('mock-only', 'MOCK_VERIFIED')).toBe('Simulated recovery');
  });
  it('requires independent verification for a real success label', () => {
    expect(recoveryLabel('real_n8n', null)).toBe('Real recovery pending verification');
    expect(recoveryLabel('real_n8n', 'MOCK_VERIFIED')).toBe('Real recovery pending verification');
    expect(recoveryLabel('real_n8n', 'REAL_RECOVERY_VERIFIED')).toBe('Verified real recovery');
  });
  it('separates failed and uncertain results', () => {
    expect(recoveryLabel('real_n8n', 'REAL_RECOVERY_FAILED')).toBe('Failed real recovery');
    expect(recoveryLabel('real_n8n', 'REAL_RECOVERY_UNVERIFIED')).toBe('Unverified real recovery');
  });
});

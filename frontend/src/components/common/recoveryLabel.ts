export function recoveryLabel(mode: string, outcome: string | null): string {
  if (mode !== 'real_n8n') return 'Simulated recovery';
  if (outcome === 'REAL_RECOVERY_VERIFIED') return 'Verified real recovery';
  if (outcome === 'REAL_RECOVERY_FAILED') return 'Failed real recovery';
  if (outcome === 'REAL_RECOVERY_UNVERIFIED') return 'Unverified real recovery';
  return 'Real recovery pending verification';
}

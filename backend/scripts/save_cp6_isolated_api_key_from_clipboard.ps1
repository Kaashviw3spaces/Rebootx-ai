# backend/scripts/save_cp6_isolated_api_key_from_clipboard.ps1
# Securely captures a newly created isolated n8n API key from Windows clipboard.
# Validates key format, tests authentication against isolated n8n on port 5680,
# asserts workflow presence and zero executions, then saves via Windows DPAPI.
param(
    [Parameter(Mandatory=$false)]
    [string]$PreparationDirectory
)

$ErrorActionPreference = 'Stop'
$backendDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $PreparationDirectory) {
    $PreparationDirectory = Join-Path $backendDir '.temporal\cp6-prep-7163e9b9ff1143aeaa6e72939962467f'
}
$cp6Prep = (Resolve-Path -LiteralPath $PreparationDirectory).Path
$cp6InstancePath = Join-Path $cp6Prep 'isolated-n8n.json'
if (-not (Test-Path -LiteralPath $cp6InstancePath)) { throw "Isolated instance manifest missing: $cp6InstancePath" }

$cp6Instance = Get-Content -LiteralPath $cp6InstancePath -Raw | ConvertFrom-Json
$cp6IsolatedDir = $cp6Instance.directory
$cp6KeyPath = Join-Path $cp6IsolatedDir 'api-key.dpapi'

# 1. Fetch text from Windows Clipboard
$rawKey = Get-Clipboard
if (-not $rawKey -or [string]::IsNullOrWhiteSpace($rawKey)) {
    throw "Clipboard is empty or does not contain text. Copy the newly created n8n API key to clipboard first."
}

$trimmedKey = $rawKey.Trim()

# 2. Strict format validation (never print the key)
if ($trimmedKey.Length -lt 20 -or $trimmedKey.Length -gt 2000) {
    throw "Invalid key length ($($trimmedKey.Length) characters). Expected 20-2000 characters."
}

# Assert printable ASCII characters without control characters
if ($trimmedKey -notmatch '^[A-Za-z0-9_.:/-]+$') {
    throw "Invalid character format in clipboard key. Contains forbidden characters or whitespace."
}

$nonPrintable = [int[]][char[]]$trimmedKey | Where-Object { $_ -lt 32 -or $_ -gt 126 }
if ($nonPrintable.Count -gt 0) {
    throw "Key contains unprintable or control characters (codes: $($nonPrintable -join ', '))."
}

Write-Host "[OK] Clipboard key format validated ($($trimmedKey.Length) chars, clean ASCII)." -ForegroundColor Green

# 3. Test API key directly against isolated n8n on port 5680 BEFORE modifying any file
$headers = @{ 'X-N8N-API-KEY' = $trimmedKey }
$testOrigin = $cp6Instance.origin # http://127.0.0.1:5680

Write-Host "Testing authenticated request against $testOrigin/api/v1/workflows..." -ForegroundColor Cyan
try {
    $wfResp = Invoke-RestMethod -Uri "$testOrigin/api/v1/workflows" -Headers $headers -Method Get -TimeoutSec 5
} catch {
    throw "API authentication test failed against $testOrigin! Server response: $($_.Exception.Message)"
}

# 4. Verify workflow response payload
$wfData = $wfResp.data
if (-not $wfData -or $wfData.Count -ne 2) {
    throw "Workflow count mismatch! Expected 2 workflows, got $($wfData.Count)."
}

$wfIds = @($wfData | ForEach-Object { $_.id })
$expectedIds = @('ievg2u7YcfdnU3L8', 'wmtArUNSGBtEuCUM')
foreach ($eid in $expectedIds) {
    if ($wfIds -notcontains $eid) {
        throw "Expected workflow ID '$eid' not found in response!"
    }
}

# Verify both are inactive
$activeWfs = @($wfData | Where-Object { $_.active -eq $true })
if ($activeWfs.Count -gt 0) {
    throw "Refusing key: one or more workflows are unexpectedly active!"
}

Write-Host "[OK] API call returned HTTP 200. Exactly 2 expected workflows confirmed (both inactive)." -ForegroundColor Green

# 5. Verify execution count remains zero
$execResp = Invoke-RestMethod -Uri "$testOrigin/api/v1/executions" -Headers $headers -Method Get -TimeoutSec 5
if ($execResp.data.Count -ne 0) {
    throw "Execution count is not zero (found $($execResp.data.Count) executions)!"
}
Write-Host "[OK] Confirmed zero historical executions." -ForegroundColor Green

# 6. Back up existing api-key.dpapi
$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
if (Test-Path -LiteralPath $cp6KeyPath) {
    $bakPath = "$cp6KeyPath.bak_$timestamp"
    Copy-Item -LiteralPath $cp6KeyPath -Destination $bakPath -Force
    Write-Host "[BACKUP] Existing api-key.dpapi backed up to: $bakPath" -ForegroundColor Cyan
}

# 7. Encrypt and save verified key via Windows DPAPI
$secureKey = ConvertTo-SecureString $trimmedKey -AsPlainText -Force
$encryptedKey = ConvertFrom-SecureString $secureKey
[System.IO.File]::WriteAllText($cp6KeyPath, $encryptedKey)

# 8. Verify round-trip DPAPI read-back
$readBack = [System.Net.NetworkCredential]::new('', (ConvertTo-SecureString ([System.IO.File]::ReadAllText($cp6KeyPath)))).Password
if ($readBack -cne $trimmedKey) {
    throw "FATAL: DPAPI write verification failed on read-back!"
}

# 9. Update isolated-n8n.json metadata
$cp6Instance.api_key_configured = $true
[System.IO.File]::WriteAllText($cp6InstancePath, ($cp6Instance | ConvertTo-Json -Depth 5))

# 10. Clear plaintext variables and clipboard
Remove-Variable rawKey, trimmedKey, secureKey, encryptedKey, readBack, headers -ErrorAction SilentlyContinue
try { Set-Clipboard -Value '' } catch { }

Write-Host "[SUCCESS] Isolated n8n API key verified and protected with Windows DPAPI." -ForegroundColor Green
Write-Host "Clipboard cleared. Zero plaintext keys displayed or written to logs." -ForegroundColor Green


# backend/scripts/repair_cp6_dpapi.ps1
# Interactive DPAPI repair utility for Checkpoint 6 isolated demonstration.
# Generates new DPAPI credentials under current interactive desktop session.
# Uses scripts.rotate_token for ORM-level tenant token rotation.
# Strictly bounded to isolated demo.db with pre-rotation schema validation and full rollback safety.
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

# 1. Bounded target path assertion: Must strictly match cp6-prep-7163e9b9ff1143aeaa6e72939962467f
$expectedPrepPattern = '(?i)backend[\\/]\.temporal[\\/]cp6-prep-7163e9b9ff1143aeaa6e72939962467f$'
if ($cp6Prep -notmatch $expectedPrepPattern) {
    throw "FAIL CLOSED: Target directory '$cp6Prep' violates strict isolated path constraint!"
}

$cp6ManifestPath = Join-Path $cp6Prep 'manifest.json'
$cp6InstancePath = Join-Path $cp6Prep 'isolated-n8n.json'
$cp6SecretsPath = Join-Path $cp6Prep 'secrets.dpapi'
$cp6DemoDbPath = Join-Path $cp6Prep 'demo.db'

if (-not (Test-Path -LiteralPath $cp6ManifestPath)) { throw "Manifest missing: $cp6ManifestPath" }
if (-not (Test-Path -LiteralPath $cp6InstancePath)) { throw "Isolated instance manifest missing: $cp6InstancePath" }
if (-not (Test-Path -LiteralPath $cp6DemoDbPath)) { throw "Isolated demo database missing: $cp6DemoDbPath" }

$cp6Manifest = Get-Content -LiteralPath $cp6ManifestPath -Raw | ConvertFrom-Json
$cp6Instance = Get-Content -LiteralPath $cp6InstancePath -Raw | ConvertFrom-Json

# Assert manifest matches expected UUIDs
$expectedTenantId = '0610d06e-460f-465e-8b19-f80b336fd8e7'
$expectedIntegrationId = '38979968-2d1f-4fd0-9307-c829e54ba58f'
$expectedWorkflowExtId = 'ievg2u7YcfdnU3L8'

if ($cp6Manifest.tenant_id -ne $expectedTenantId) { throw "Manifest tenant ID mismatch: $($cp6Manifest.tenant_id)" }
if ($cp6Manifest.integration_id -ne $expectedIntegrationId) { throw "Manifest integration ID mismatch: $($cp6Manifest.integration_id)" }
if ($cp6Manifest.workflow_external_id -ne $expectedWorkflowExtId) { throw "Manifest workflow ID mismatch: $($cp6Manifest.workflow_external_id)" }

$cp6IsolatedDir = $cp6Instance.directory
$cp6ProcessEnvPath = Join-Path $cp6IsolatedDir 'process-environment.dpapi'
$cp6ApiKeyPath = Join-Path $cp6IsolatedDir 'api-key.dpapi'
$cp6Python = Join-Path $cp6Manifest.backend_directory '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $cp6Python)) { throw "Backend Python venv missing: $cp6Python" }

# 2. Hard guard: Preserve existing api-key.dpapi and verify it decrypts under current logon
if (-not (Test-Path -LiteralPath $cp6ApiKeyPath)) { throw "api-key.dpapi is missing from $cp6IsolatedDir" }
try {
    $null = ConvertTo-SecureString (Get-Content -LiteralPath $cp6ApiKeyPath -Raw)
    Write-Host "[OK] Existing api-key.dpapi validated and decryptable under current logon." -ForegroundColor Green
} catch {
    throw "Existing api-key.dpapi failed decryption. Refusing to proceed until key is verified."
}

# 3. Environment & database preservation guards (record pre-repair hashes)
$backendEnv = Join-Path $cp6Manifest.backend_directory '.env'
$preEnvHash = if (Test-Path -LiteralPath $backendEnv) { (Get-FileHash -LiteralPath $backendEnv -Algorithm SHA256).Hash } else { $null }

# 4. Generate cryptographically secure demo secrets (32 bytes signing, 48 bytes token)
$cp6Rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$cp6SigningBytes = New-Object byte[] 32
$cp6TokenBytes = New-Object byte[] 48
$cp6Rng.GetBytes($cp6SigningBytes)
$cp6Rng.GetBytes($cp6TokenBytes)
$cp6Rng.Dispose()

$cp6SigningSecret = [Convert]::ToBase64String($cp6SigningBytes)
$cp6ReadToken = [Convert]::ToBase64String($cp6TokenBytes)

# 5. Prepare secrets.dpapi payload
$cp6SecretPayload = @{
    signing_secret = $cp6SigningSecret
    read_token = $cp6ReadToken
} | ConvertTo-Json -Compress

$cp6SecureSecrets = ConvertTo-SecureString $cp6SecretPayload -AsPlainText -Force
$cp6EncryptedSecrets = ConvertFrom-SecureString $cp6SecureSecrets

# 6. Prepare process-environment.dpapi payload matching isolated startup configuration
$cp6Env = @{}
foreach ($name in @('SystemRoot','SystemDrive','PATH','PATHEXT','TEMP','TMP','USERPROFILE','APPDATA','LOCALAPPDATA','COMSPEC','HOMEDRIVE','HOMEPATH','PROCESSOR_ARCHITECTURE','OS')) {
    $val = [Environment]::GetEnvironmentVariable($name)
    if ($null -ne $val) { $cp6Env[$name] = $val }
}
$cp6Env['N8N_USER_FOLDER'] = $cp6IsolatedDir
$cp6Env['DB_TYPE'] = 'sqlite'
$cp6Env['DB_SQLITE_DATABASE'] = $cp6Instance.database_path
$cp6Env['N8N_LISTEN_ADDRESS'] = '127.0.0.1'
$cp6Env['N8N_HOST'] = '127.0.0.1'
$cp6Env['N8N_PROTOCOL'] = 'http'
$cp6Env['N8N_PORT'] = '5680'
$cp6Env['N8N_EDITOR_BASE_URL'] = 'http://127.0.0.1:5680'
$cp6Env['N8N_WEBHOOK_URL'] = 'http://127.0.0.1:5680/'
$cp6Env['N8N_RUNNERS_MODE'] = 'internal'
$cp6Env['N8N_RUNNERS_BROKER_PORT'] = '5681'
$cp6Env['N8N_RUNNERS_BROKER_LISTEN_ADDRESS'] = '127.0.0.1'
$cp6Env['N8N_BLOCK_ENV_ACCESS_IN_NODE'] = 'false'
$cp6Env['N8N_DIAGNOSTICS_ENABLED'] = 'false'
$cp6Env['N8N_VERSION_NOTIFICATIONS_ENABLED'] = 'false'
$cp6Env['N8N_TEMPLATES_ENABLED'] = 'false'
$cp6Env['REBOOTX_BASE_URL'] = 'http://127.0.0.1:8000'
$cp6Env['REBOOTX_INTEGRATION_ID'] = $cp6Manifest.integration_id
$cp6Env['REBOOTX_WORKFLOW_EXTERNAL_ID'] = $cp6Manifest.workflow_external_id
$cp6Env['REBOOTX_WEBHOOK_SECRET'] = $cp6SigningSecret

$cp6SecureEnv = ConvertTo-SecureString ($cp6Env | ConvertTo-Json -Compress) -AsPlainText -Force
$cp6EncryptedProcessEnv = ConvertFrom-SecureString $cp6SecureEnv

# 7. Validate in-memory round-trip DPAPI decryption and signing-secret consistency BEFORE writing
$testSecDec = [System.Net.NetworkCredential]::new('', (ConvertTo-SecureString $cp6EncryptedSecrets)).Password | ConvertFrom-Json
if ($testSecDec.signing_secret -cne $cp6SigningSecret) { throw "Secrets round-trip validation failed!" }
if ($testSecDec.read_token -cne $cp6ReadToken) { throw "Read token round-trip validation failed!" }

$testEnvDec = [System.Net.NetworkCredential]::new('', (ConvertTo-SecureString $cp6EncryptedProcessEnv)).Password | ConvertFrom-Json
if ($testEnvDec.REBOOTX_WEBHOOK_SECRET -cne $cp6SigningSecret) { throw "Signing secret consistency check failed!" }

Write-Host "[OK] In-memory DPAPI round-trip validation and secret consistency verified." -ForegroundColor Green

# 8. Create and verify timestamped backups BEFORE modifying any file
$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$dbBak = "$cp6DemoDbPath.bak_$timestamp"
Copy-Item -LiteralPath $cp6DemoDbPath -Destination $dbBak -Force
if (-not (Test-Path -LiteralPath $dbBak) -or (Get-Item -LiteralPath $dbBak).Length -ne (Get-Item -LiteralPath $cp6DemoDbPath).Length) {
    throw "FAIL CLOSED: demo.db backup creation failed or size mismatch!"
}
Write-Host "[BACKUP] demo.db successfully backed up and verified: $dbBak" -ForegroundColor Cyan

$secBak = $null
if (Test-Path -LiteralPath $cp6SecretsPath) {
    $secBak = "$cp6SecretsPath.bak_$timestamp"
    Copy-Item -LiteralPath $cp6SecretsPath -Destination $secBak -Force
    if (-not (Test-Path -LiteralPath $secBak) -or (Get-Item -LiteralPath $secBak).Length -ne (Get-Item -LiteralPath $cp6SecretsPath).Length) {
        throw "FAIL CLOSED: secrets.dpapi backup creation failed or size mismatch!"
    }
    Write-Host "[BACKUP] secrets.dpapi successfully backed up and verified: $secBak" -ForegroundColor Cyan
}

$envBak = $null
if (Test-Path -LiteralPath $cp6ProcessEnvPath) {
    $envBak = "$cp6ProcessEnvPath.bak_$timestamp"
    Copy-Item -LiteralPath $cp6ProcessEnvPath -Destination $envBak -Force
    if (-not (Test-Path -LiteralPath $envBak) -or (Get-Item -LiteralPath $envBak).Length -ne (Get-Item -LiteralPath $cp6ProcessEnvPath).Length) {
        throw "FAIL CLOSED: process-environment.dpapi backup creation failed or size mismatch!"
    }
    Write-Host "[BACKUP] process-environment.dpapi successfully backed up and verified: $envBak" -ForegroundColor Cyan
}

# 9. Pre-rotation schema guard: Database must contain ONLY the expected tenant and integration
$env:CP6_TARGET_DB_URL = "sqlite:///" + $cp6DemoDbPath.Replace('\', '/')
$env:CP6_TENANT_ID = $expectedTenantId
$env:CP6_INTEGRATION_ID = $expectedIntegrationId
$env:CP6_NEW_TOKEN = $cp6ReadToken

@'
import os, sys
from uuid import UUID
from app.core.database import make_engine, session_factory
from app.models.entities import Tenant, Integration, Workflow
from scripts.rotate_token import rotate_tenant_token

db_url = os.environ['CP6_TARGET_DB_URL']
tenant_id = UUID(os.environ['CP6_TENANT_ID'])
integration_id = UUID(os.environ['CP6_INTEGRATION_ID'])
new_token = os.environ['CP6_NEW_TOKEN']

engine = make_engine(db_url)
try:
    with session_factory(engine)() as db:
        # Strict isolation assert: exactly 1 tenant exists
        tenants = db.query(Tenant).all()
        assert len(tenants) == 1, f"Expected 1 tenant, found {len(tenants)}"
        assert tenants[0].id == tenant_id, f"Unexpected tenant ID: {tenants[0].id}"
        assert tenants[0].name == "CP6 Safe Demo", f"Unexpected tenant name: {tenants[0].name}"

        # Strict isolation assert: exactly 1 integration exists
        integrations = db.query(Integration).all()
        assert len(integrations) == 1, f"Expected 1 integration, found {len(integrations)}"
        assert integrations[0].id == integration_id, f"Unexpected integration ID: {integrations[0].id}"
        assert integrations[0].secret_ref == "CP6_DEMO_WEBHOOK_SECRET", f"Unexpected secret_ref: {integrations[0].secret_ref}"

        # Strict isolation assert: exactly 1 workflow exists
        workflows = db.query(Workflow).all()
        assert len(workflows) == 1, f"Expected 1 workflow, found {len(workflows)}"
        assert workflows[0].external_id == "ievg2u7YcfdnU3L8", f"Unexpected workflow: {workflows[0].external_id}"
        assert workflows[0].kind == "side_effect_safe_demo_v1", f"Unexpected workflow kind: {workflows[0].kind}"

    # Perform token rotation using existing scripts.rotate_token ORM logic
    name, returned_token = rotate_tenant_token(db_url, tenant_id, new_token)
    assert returned_token == new_token, "Token rotation returned unexpected token value"
    print(f"ORM_TOKEN_ROTATION_SUCCESS:{name}")
except Exception as exc:
    print(f"ORM_TOKEN_ROTATION_FAILED:{exc}", file=sys.stderr)
    sys.exit(1)
finally:
    engine.dispose()
'@ | & $cp6Python -B -

if ($LASTEXITCODE -ne 0) {
    # Atomic rollback if rotation or schema verification fails
    Copy-Item -LiteralPath $dbBak -Destination $cp6DemoDbPath -Force
    throw "FAIL CLOSED: Pre-rotation database verification or rotation failed. Restored demo.db from backup."
}
Write-Host "[OK] Database schema verified and tenant token rotated via scripts.rotate_token." -ForegroundColor Green

# 10. Write validated encrypted DPAPI files to disk
try {
    [System.IO.File]::WriteAllText($cp6SecretsPath, $cp6EncryptedSecrets)
    [System.IO.File]::WriteAllText($cp6ProcessEnvPath, $cp6EncryptedProcessEnv)

    # Post-write verification from disk files
    $verifySecrets = [System.Net.NetworkCredential]::new('', (ConvertTo-SecureString ([System.IO.File]::ReadAllText($cp6SecretsPath)))).Password | ConvertFrom-Json
    $verifyEnv = [System.Net.NetworkCredential]::new('', (ConvertTo-SecureString ([System.IO.File]::ReadAllText($cp6ProcessEnvPath)))).Password | ConvertFrom-Json

    if ($verifySecrets.signing_secret -cne $verifyEnv.REBOOTX_WEBHOOK_SECRET) {
        throw "Post-write consistency mismatch between secrets.dpapi and process-environment.dpapi!"
    }
} catch {
    # Atomic full rollback if DPAPI file writing or post-verification fails
    Write-Host "[ROLLBACK] Reverting all changes due to write/verification failure..." -ForegroundColor Red
    Copy-Item -LiteralPath $dbBak -Destination $cp6DemoDbPath -Force
    if ($secBak) { Copy-Item -LiteralPath $secBak -Destination $cp6SecretsPath -Force }
    if ($envBak) { Copy-Item -LiteralPath $envBak -Destination $cp6ProcessEnvPath -Force }
    throw "FAIL CLOSED: Failed during DPAPI write/verification. All files rolled back to backup state."
}

# 11. Verify backend/.env remains completely unchanged
if ($preEnvHash) {
    $postEnvHash = (Get-FileHash -LiteralPath $backendEnv -Algorithm SHA256).Hash
    if ($postEnvHash -cne $preEnvHash) { throw "FATAL: backend/.env was modified!" }
}

# 12. Clean up sensitive plaintext variables from PowerShell memory
Remove-Item Env:CP6_TARGET_DB_URL, Env:CP6_TENANT_ID, Env:CP6_INTEGRATION_ID, Env:CP6_NEW_TOKEN -ErrorAction SilentlyContinue
Remove-Variable cp6SigningBytes, cp6TokenBytes, cp6SigningSecret, cp6ReadToken, cp6SecretPayload, cp6SecureSecrets, cp6EncryptedSecrets, cp6Env, cp6SecureEnv, cp6EncryptedProcessEnv, testSecDec, testEnvDec, verifySecrets, verifyEnv -ErrorAction SilentlyContinue

Write-Host "[SUCCESS] DPAPI repair completed successfully." -ForegroundColor Green
Write-Host "Backup reference timestamp: $timestamp" -ForegroundColor Cyan
Write-Host "secrets.dpapi and process-environment.dpapi are now decryptable in your interactive logon." -ForegroundColor Green
Write-Host "Tenant token synced via rotate_token.py; API key and isolated n8n owner account preserved." -ForegroundColor Green

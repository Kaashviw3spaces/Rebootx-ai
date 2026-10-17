# Preparation only. No service start, n8n restart, webhook POST or recovery dispatch.
param([Parameter(Mandatory=$true)][string]$BackendDirectory)
$ErrorActionPreference = 'Stop'
$cp6Backend = (Resolve-Path -LiteralPath $BackendDirectory).Path
$cp6Root = Split-Path -Parent $cp6Backend
$cp6Python = Join-Path $cp6Backend '.venv\Scripts\python.exe'
$cp6OriginalLocation = Get-Location
$cp6EnvFile = Join-Path $cp6Backend '.env'
$cp6HistoricalDb = Join-Path $cp6Backend '.temporal\live_demo.db'
$cp6EnvHash = (Get-FileHash -LiteralPath $cp6EnvFile -Algorithm SHA256).Hash
$cp6HistoricalHash = if (Test-Path -LiteralPath $cp6HistoricalDb) { (Get-FileHash -LiteralPath $cp6HistoricalDb -Algorithm SHA256).Hash } else { $null }
$cp6Session = [guid]::NewGuid().ToString('N')
$cp6Directory = Join-Path $cp6Backend ".temporal\cp6-prep-$cp6Session"
if (Test-Path -LiteralPath $cp6Directory) { throw 'Refusing to reuse an existing preparation directory' }
New-Item -ItemType Directory -Path $cp6Directory | Out-Null
$cp6Db = Join-Path $cp6Directory 'demo.db'
$cp6ProtectedFile = Join-Path $cp6Directory 'secrets.dpapi'
$cp6ManifestFile = Join-Path $cp6Directory 'manifest.json'
$cp6LoaderFile = Join-Path $cp6Directory 'load-session.ps1'

# Generate new demo credentials without putting them in arguments or output.
$cp6Rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$cp6SigningBytes = New-Object byte[] 32
$cp6TokenBytes = New-Object byte[] 48
$cp6Rng.GetBytes($cp6SigningBytes)
$cp6Rng.GetBytes($cp6TokenBytes)
$cp6Rng.Dispose()
$cp6SecretPayload = @{
    signing_secret = [Convert]::ToBase64String($cp6SigningBytes)
    read_token = [Convert]::ToBase64String($cp6TokenBytes)
} | ConvertTo-Json -Compress
$cp6SecurePayload = ConvertTo-SecureString $cp6SecretPayload -AsPlainText -Force
$cp6Encrypted = ConvertFrom-SecureString $cp6SecurePayload
if (-not $cp6Encrypted) { throw 'Windows credential protection failed; stop before database setup' }
[System.IO.File]::WriteAllText($cp6ProtectedFile, $cp6Encrypted)
$cp6DecodedSecure = ConvertTo-SecureString ([System.IO.File]::ReadAllText($cp6ProtectedFile))
$cp6Decoded = [System.Net.NetworkCredential]::new('', $cp6DecodedSecure).Password | ConvertFrom-Json
if ($cp6Decoded.signing_secret -cne (($cp6SecretPayload | ConvertFrom-Json).signing_secret)) { throw 'Protected-secret round trip failed' }

$env:DATABASE_URL = 'sqlite:///' + $cp6Db.Replace('\', '/')
$env:RECOVERY_MODE = 'mock-only'
$env:N8N_AUTHORIZATIONS = '[]'
$env:N8N_BASE_URL = 'http://127.0.0.1:5678'
$env:N8N_SUPPORTED_VERSION = '2.43.6'
$env:AI_PROVIDER = 'mock'
$env:TEMPORAL_ADDRESS = '127.0.0.1:7233'
$env:TEMPORAL_NAMESPACE = 'default'
$env:TEMPORAL_TASK_QUEUE = "rebootx-cp6-$cp6Session"
$env:TEMPORAL_API_KEY = ''
$env:TEMPORAL_TLS_ENABLED = 'false'
$env:CP6_DEMO_WEBHOOK_SECRET = $cp6Decoded.signing_secret
$env:CP6_DEMO_READ_TOKEN = $cp6Decoded.read_token
$env:REBOOTX_BASE_URL = 'http://127.0.0.1:8000'
$env:REBOOTX_WORKFLOW_EXTERNAL_ID = 'ievg2u7YcfdnU3L8'
$env:REBOOTX_WEBHOOK_SECRET = $env:CP6_DEMO_WEBHOOK_SECRET

try {
    Set-Location -LiteralPath $cp6Backend
    # Hard guard: Settings must resolve to this new SQLite file, never .env's Neon URL.
    $env:CP6_EXPECTED_DATABASE = $cp6Db
    @'
import os
from pathlib import Path
from sqlalchemy.engine import make_url
from app.core.config import Settings
u = make_url(Settings().database_url.get_secret_value())
assert u.get_backend_name() == 'sqlite'
assert Path(u.database).resolve() == Path(os.environ['CP6_EXPECTED_DATABASE']).resolve()
assert not Path(u.database).exists()
print('NEW_ISOLATED_SQLITE_TARGET_CONFIRMED')
'@ | & $cp6Python -B -
    if ($LASTEXITCODE -ne 0) { throw 'New database target guard failed' }
    & $cp6Python -B -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Isolated migration failed' }
    & $cp6Python -B -m alembic check
    if ($LASTEXITCODE -ne 0) { throw 'Isolated model drift check failed' }

    # Use the existing provision CLI/main. Supply its private prompt from a new
    # process-local random token, never an argv value or printed token.
    $cp6Provision = @'
import getpass, os, sys
from scripts.provision import main
getpass.getpass = lambda prompt: os.environ['CP6_DEMO_READ_TOKEN']
sys.argv = ['scripts.provision', '--tenant-name', 'CP6 Safe Demo',
            '--workflow-external-id', 'ievg2u7YcfdnU3L8',
            '--workflow-kind', 'side_effect_safe_demo_v1',
            '--secret-env', 'CP6_DEMO_WEBHOOK_SECRET']
try:
    main()
except Exception as exc:
    print('ISOLATED_PROVISION_FAILED:' + type(exc).__name__)
    raise SystemExit(1) from None
'@ | & $cp6Python -B -
    if ($LASTEXITCODE -ne 0) { throw 'Isolated provisioning failed' }
    $cp6ProvisionText = $cp6Provision -join "`n"
    $cp6Tenant = [regex]::Match($cp6ProvisionText, 'Tenant ID: ([0-9a-f-]{36})').Groups[1].Value
    $cp6Integration = [regex]::Match($cp6ProvisionText, 'Integration ID: ([0-9a-f-]{36})').Groups[1].Value
    $cp6Workflow = [regex]::Match($cp6ProvisionText, 'Workflow ID: ([0-9a-f-]{36})').Groups[1].Value
    if (-not $cp6Tenant -or -not $cp6Integration -or -not $cp6Workflow) { throw 'Provisioning IDs missing' }
    $env:REBOOTX_INTEGRATION_ID = $cp6Integration
    $cp6Manifest = [ordered]@{
        session = $cp6Session
        backend_directory = $cp6Backend
        database_path = $cp6Db
        database_url = $env:DATABASE_URL
        tenant_id = $cp6Tenant
        integration_id = $cp6Integration
        workflow_id = $cp6Workflow
        workflow_external_id = 'ievg2u7YcfdnU3L8'
        workflow_kind = 'side_effect_safe_demo_v1'
        signing_secret_ref = 'CP6_DEMO_WEBHOOK_SECRET'
        temporal_task_queue = $env:TEMPORAL_TASK_QUEUE
        recovery_mode = 'mock-only'
        authorizations = @()
        workflow_sha256 = $null
        calibration_execution_id = $null
        secrets_file = 'secrets.dpapi'
        services_started = $false
    }
    [System.IO.File]::WriteAllText($cp6ManifestFile, ($cp6Manifest | ConvertTo-Json -Depth 5))

    # This loader only sets a private shell environment. It never starts services.
    $cp6Loader = @'
param([string]$PreparationDirectory = $PSScriptRoot)
$ErrorActionPreference = 'Stop'
if (-not $PreparationDirectory) { throw 'Explicit preparation directory required' }
$cp6Manifest = Get-Content -LiteralPath (Join-Path $PreparationDirectory 'manifest.json') -Raw | ConvertFrom-Json
$cp6Secure = ConvertTo-SecureString ([System.IO.File]::ReadAllText((Join-Path $PreparationDirectory $cp6Manifest.secrets_file)))
$cp6Secrets = [System.Net.NetworkCredential]::new('', $cp6Secure).Password | ConvertFrom-Json
$env:DATABASE_URL = $cp6Manifest.database_url
$env:RECOVERY_MODE = 'mock-only'
$env:N8N_AUTHORIZATIONS = '[]'
$env:N8N_BASE_URL = 'http://127.0.0.1:5678'
$env:N8N_SUPPORTED_VERSION = '2.43.6'
$env:AI_PROVIDER = 'mock'
$env:TEMPORAL_ADDRESS = '127.0.0.1:7233'
$env:TEMPORAL_NAMESPACE = 'default'
$env:TEMPORAL_TASK_QUEUE = $cp6Manifest.temporal_task_queue
$env:TEMPORAL_API_KEY = ''
$env:TEMPORAL_TLS_ENABLED = 'false'
$env:CP6_DEMO_WEBHOOK_SECRET = $cp6Secrets.signing_secret
$env:CP6_DEMO_READ_TOKEN = $cp6Secrets.read_token
$env:REBOOTX_BASE_URL = 'http://127.0.0.1:8000'
$env:REBOOTX_INTEGRATION_ID = $cp6Manifest.integration_id
$env:REBOOTX_WEBHOOK_SECRET = $cp6Secrets.signing_secret
$env:REBOOTX_WORKFLOW_EXTERNAL_ID = $cp6Manifest.workflow_external_id
Remove-Variable cp6Secrets, cp6Secure
Set-Location -LiteralPath $cp6Manifest.backend_directory
Write-Output 'CP6 private environment loaded; mock mode, empty authorization; no services started.'
'@
    [System.IO.File]::WriteAllText($cp6LoaderFile, $cp6Loader)
    if ((Get-FileHash -LiteralPath $cp6EnvFile -Algorithm SHA256).Hash -cne $cp6EnvHash) { throw 'backend/.env unexpectedly changed' }
    if ($cp6HistoricalHash -and (Get-FileHash -LiteralPath $cp6HistoricalDb -Algorithm SHA256).Hash -cne $cp6HistoricalHash) { throw 'Historical database unexpectedly changed' }
    $cp6Manifest | ConvertTo-Json -Depth 5
    Write-Output 'EXISTING_ENV_AND_HISTORICAL_DATABASE_UNCHANGED; NO_N8N_RESTART; NO_CALIBRATION; NO_SERVICES_STARTED'
}
finally {
    Set-Location -LiteralPath $cp6OriginalLocation
    Remove-Item Env:CP6_DEMO_WEBHOOK_SECRET, Env:CP6_DEMO_READ_TOKEN, Env:REBOOTX_WEBHOOK_SECRET -ErrorAction SilentlyContinue
    Remove-Variable cp6SecretPayload, cp6Decoded, cp6SecurePayload, cp6DecodedSecure, cp6SigningBytes, cp6TokenBytes -ErrorAction SilentlyContinue
}

# Load the isolated backend session only. Never start API, Temporal or dispatch.
param([Parameter(Mandatory=$true)][string]$PreparationDirectory)
$ErrorActionPreference = 'Stop'
$cp6Prep = (Resolve-Path -LiteralPath $PreparationDirectory).Path
$cp6Instance = Get-Content -LiteralPath (Join-Path $cp6Prep 'isolated-n8n.json') -Raw | ConvertFrom-Json
if ($cp6Instance.origin -ne 'http://127.0.0.1:5680') { throw 'Unexpected isolated origin' }
$cp6KeyPath = Join-Path $cp6Instance.directory 'api-key.dpapi'
if (-not (Test-Path -LiteralPath $cp6KeyPath)) { throw 'New isolated API key has not been saved privately' }
$cp6LoaderPath = Join-Path $cp6Prep 'load-session.ps1'
& ([scriptblock]::Create((Get-Content -LiteralPath $cp6LoaderPath -Raw))) -PreparationDirectory $cp6Prep
$cp6Key = ConvertTo-SecureString ([IO.File]::ReadAllText($cp6KeyPath))
$env:N8N_API_KEY = [Net.NetworkCredential]::new('', $cp6Key).Password
$env:N8N_BASE_URL = 'http://127.0.0.1:5680'
$env:N8N_SUPPORTED_VERSION = '2.43.6'
$env:RECOVERY_MODE = 'mock-only'
$env:N8N_AUTHORIZATIONS = '[]'
Remove-Variable cp6Key
Write-Output 'Isolated backend session loaded privately: origin 5680, mock mode, no authorization, no services started.'

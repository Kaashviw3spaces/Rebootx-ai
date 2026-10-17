# User-run hidden credential entry. Stores only a DPAPI-protected new-instance key.
param([Parameter(Mandatory=$true)][string]$PreparationDirectory)
$ErrorActionPreference = 'Stop'
$cp6Prep = (Resolve-Path -LiteralPath $PreparationDirectory).Path
$cp6Instance = Get-Content -LiteralPath (Join-Path $cp6Prep 'isolated-n8n.json') -Raw | ConvertFrom-Json
if ($cp6Instance.origin -ne 'http://127.0.0.1:5680') { throw 'Unexpected instance origin' }
$cp6Key = Read-Host 'New isolated n8n API key (hidden; never paste into chat)' -AsSecureString
if ($cp6Key.Length -eq 0) { throw 'No key supplied' }
$cp6KeyPath = Join-Path $cp6Instance.directory 'api-key.dpapi'
if (Test-Path -LiteralPath $cp6KeyPath) { throw 'A protected isolated key already exists; refusing replacement' }
[IO.File]::WriteAllText($cp6KeyPath, (ConvertFrom-SecureString $cp6Key))
Remove-Variable cp6Key
Write-Output 'New isolated API key saved with Windows protection; no key displayed and backend/.env unchanged.'

# Start only a NEW isolated n8n instance. No workflow execution or recovery services.
param([Parameter(Mandatory=$true)][string]$PreparationDirectory)
$ErrorActionPreference = 'Stop'
$cp6Prep = (Resolve-Path -LiteralPath $PreparationDirectory).Path
$cp6Manifest = Get-Content -LiteralPath (Join-Path $cp6Prep 'manifest.json') -Raw | ConvertFrom-Json
if ($cp6Manifest.workflow_external_id -ne 'ievg2u7YcfdnU3L8') { throw 'Unexpected prepared workflow' }
foreach ($cp6Port in @(5680,5681)) {
    $cp6Probe = [System.Net.Sockets.TcpClient]::new()
    try { $cp6Probe.Connect('127.0.0.1', $cp6Port); throw "Port $cp6Port is already occupied; refusing startup" }
    catch [System.Net.Sockets.SocketException] { }
    finally { $cp6Probe.Dispose() }
}
$cp6Folder = Join-Path $cp6Prep ('n8n-isolated-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $cp6Folder | Out-Null
$cp6Node = (Get-Command node.exe).Source
$cp6N8n = Join-Path $env:LOCALAPPDATA 'npm-cache\_npx\a8a7eec953f1f314\node_modules\n8n\bin\n8n'
if (-not (Test-Path -LiteralPath $cp6N8n)) { throw 'Inspected n8n binary missing' }
$cp6Protected = ConvertTo-SecureString ([System.IO.File]::ReadAllText((Join-Path $cp6Prep 'secrets.dpapi')))
$cp6Secrets = [System.Net.NetworkCredential]::new('', $cp6Protected).Password | ConvertFrom-Json

# Use an allowlisted child environment. Do not inherit backend .env, shared n8n
# config, API keys, read tokens, encryption keys, database URLs or proxy settings.
$cp6Environment = @{}
foreach ($cp6Name in @('SystemRoot','SystemDrive','PATH','PATHEXT','TEMP','TMP','USERPROFILE','APPDATA','LOCALAPPDATA','COMSPEC','HOMEDRIVE','HOMEPATH','PROCESSOR_ARCHITECTURE','OS')) {
    $cp6Value = [Environment]::GetEnvironmentVariable($cp6Name)
    if ($null -ne $cp6Value) { $cp6Environment[$cp6Name] = $cp6Value }
}
$cp6Environment['N8N_USER_FOLDER'] = $cp6Folder
$cp6Environment['DB_TYPE'] = 'sqlite'
$cp6Environment['DB_SQLITE_DATABASE'] = (Join-Path $cp6Folder '.n8n\database.sqlite')
$cp6Environment['N8N_LISTEN_ADDRESS'] = '127.0.0.1'
$cp6Environment['N8N_HOST'] = '127.0.0.1'
$cp6Environment['N8N_PROTOCOL'] = 'http'
$cp6Environment['N8N_PORT'] = '5680'
$cp6Environment['N8N_EDITOR_BASE_URL'] = 'http://127.0.0.1:5680'
$cp6Environment['N8N_WEBHOOK_URL'] = 'http://127.0.0.1:5680/'
$cp6Environment['N8N_RUNNERS_MODE'] = 'internal'
$cp6Environment['N8N_RUNNERS_BROKER_PORT'] = '5681'
$cp6Environment['N8N_RUNNERS_BROKER_LISTEN_ADDRESS'] = '127.0.0.1'
$cp6Environment['N8N_BLOCK_ENV_ACCESS_IN_NODE'] = 'false'
$cp6Environment['N8N_DIAGNOSTICS_ENABLED'] = 'false'
$cp6Environment['N8N_VERSION_NOTIFICATIONS_ENABLED'] = 'false'
$cp6Environment['N8N_TEMPLATES_ENABLED'] = 'false'
$cp6Environment['REBOOTX_BASE_URL'] = 'http://127.0.0.1:8000'
$cp6Environment['REBOOTX_INTEGRATION_ID'] = $cp6Manifest.integration_id
$cp6Environment['REBOOTX_WORKFLOW_EXTERNAL_ID'] = $cp6Manifest.workflow_external_id
$cp6Environment['REBOOTX_WEBHOOK_SECRET'] = $cp6Secrets.signing_secret
$cp6SecureEnvironment = ConvertTo-SecureString ($cp6Environment | ConvertTo-Json -Compress) -AsPlainText -Force
[IO.File]::WriteAllText((Join-Path $cp6Folder 'process-environment.dpapi'), (ConvertFrom-SecureString $cp6SecureEnvironment))

# Start-Process keeps the native process hidden. Environment changes affect this
# short-lived launcher only, never the already running shared n8n process.
$cp6OldEnvironment = @{}
foreach ($cp6Item in [Environment]::GetEnvironmentVariables('Process').GetEnumerator()) { $cp6OldEnvironment[$cp6Item.Key] = $cp6Item.Value }
try {
    foreach ($cp6Name in @([Environment]::GetEnvironmentVariables('Process').Keys)) { [Environment]::SetEnvironmentVariable($cp6Name, $null, 'Process') }
    foreach ($cp6Name in $cp6Environment.Keys) { [Environment]::SetEnvironmentVariable($cp6Name, $cp6Environment[$cp6Name], 'Process') }
    $cp6Process = Start-Process -FilePath $cp6Node -ArgumentList @(('"' + $cp6N8n + '"'), 'start') -WorkingDirectory $cp6Folder -WindowStyle Hidden -RedirectStandardOutput (Join-Path $cp6Folder 'stdout.log') -RedirectStandardError (Join-Path $cp6Folder 'stderr.log') -PassThru
}
finally {
    foreach ($cp6Name in @([Environment]::GetEnvironmentVariables('Process').Keys)) { [Environment]::SetEnvironmentVariable($cp6Name, $null, 'Process') }
    foreach ($cp6Name in $cp6OldEnvironment.Keys) { [Environment]::SetEnvironmentVariable($cp6Name, $cp6OldEnvironment[$cp6Name], 'Process') }
    Remove-Variable cp6Secrets, cp6Protected, cp6Environment, cp6SecureEnvironment
}
$cp6Isolated = [ordered]@{
    directory = $cp6Folder
    n8n_user_folder = $cp6Folder
    database_path = (Join-Path $cp6Folder '.n8n\database.sqlite')
    configuration_path = (Join-Path $cp6Folder '.n8n\config')
    node_executable = $cp6Node
    n8n_binary = $cp6N8n
    process_id = $cp6Process.Id
    origin = 'http://127.0.0.1:5680'
    broker_port = 5681
    expected_demo_id = 'ievg2u7YcfdnU3L8'
    expected_error_handler_id = 'wmtArUNSGBtEuCUM'
    owner_initialized = $false
    api_key_configured = $false
    workflows_imported = $false
}
[IO.File]::WriteAllText((Join-Path $cp6Prep 'isolated-n8n.json'), ($cp6Isolated | ConvertTo-Json))
$cp6Isolated | ConvertTo-Json

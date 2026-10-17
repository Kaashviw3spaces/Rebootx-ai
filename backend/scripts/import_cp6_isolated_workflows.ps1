# Supported CLI import into the NEW isolated database only. Imports stay inactive.
param([Parameter(Mandatory=$true)][string]$PreparationDirectory)
$ErrorActionPreference = 'Stop'
$cp6Prep = (Resolve-Path -LiteralPath $PreparationDirectory).Path
$cp6InstancePath = Join-Path $cp6Prep 'isolated-n8n.json'
$cp6Instance = Get-Content -LiteralPath $cp6InstancePath -Raw | ConvertFrom-Json
$cp6Input = Join-Path $cp6Instance.directory 'cp6-workflows.json'
$cp6Workflows = Get-Content -LiteralPath $cp6Input -Raw | ConvertFrom-Json
$cp6Ids = @($cp6Workflows | ForEach-Object { $_.id })
if ($cp6Workflows.Count -ne 2 -or $cp6Ids -notcontains 'ievg2u7YcfdnU3L8' -or $cp6Ids -notcontains 'wmtArUNSGBtEuCUM') { throw 'Unexpected import content; stop' }
if (@($cp6Workflows | Where-Object { $_.active }).Count) { throw 'Refusing active imports' }
$env:CP6_ISOLATED_DB_CHECK = $cp6Instance.database_path
$cp6Python = Join-Path ((Get-Content -LiteralPath (Join-Path $cp6Prep 'manifest.json') -Raw | ConvertFrom-Json).backend_directory) '.venv\Scripts\python.exe'
@'
import os,sqlite3
from pathlib import Path
p=Path(os.environ['CP6_ISOLATED_DB_CHECK']).resolve()
assert p.is_file() and 'n8n-isolated-' in str(p)
c=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)
try:
    assert c.execute('SELECT count(*) FROM workflow_entity').fetchone()[0] == 0, 'Refusing to overwrite any workflows'
    assert c.execute('SELECT count(*) FROM execution_entity').fetchone()[0] == 0, 'Unexpected executions'
    assert c.execute('SELECT count(*) FROM "user" WHERE email IS NOT NULL AND password IS NOT NULL').fetchone()[0] >= 1, 'Owner initialization required'
finally:
    c.close()
print('ISOLATED_IMPORT_GUARDS_PASSED')
'@ | & $cp6Python -B -
if ($LASTEXITCODE -ne 0) { throw 'Isolated import guard failed; stop' }
$cp6Secure = ConvertTo-SecureString ([IO.File]::ReadAllText((Join-Path $cp6Instance.directory 'process-environment.dpapi')))
$cp6Environment = [Net.NetworkCredential]::new('', $cp6Secure).Password | ConvertFrom-Json
if ($cp6Environment.N8N_USER_FOLDER -ne $cp6Instance.directory -or $cp6Environment.DB_SQLITE_DATABASE -ne $cp6Instance.database_path) { throw 'Isolation configuration mismatch' }
$cp6OldEnvironment = @{}
foreach ($cp6Item in [Environment]::GetEnvironmentVariables('Process').GetEnumerator()) { $cp6OldEnvironment[$cp6Item.Key] = $cp6Item.Value }
try {
    foreach ($cp6Name in @([Environment]::GetEnvironmentVariables('Process').Keys)) { [Environment]::SetEnvironmentVariable($cp6Name, $null, 'Process') }
    foreach ($cp6Property in $cp6Environment.PSObject.Properties) { [Environment]::SetEnvironmentVariable($cp6Property.Name, [string]$cp6Property.Value, 'Process') }
    $cp6Import = Start-Process -FilePath $cp6Instance.node_executable -ArgumentList @(('"' + $cp6Instance.n8n_binary + '"'), 'import:workflow', ('--input="' + $cp6Input + '"')) -WorkingDirectory $cp6Instance.directory -WindowStyle Hidden -RedirectStandardOutput (Join-Path $cp6Instance.directory 'import.stdout.log') -RedirectStandardError (Join-Path $cp6Instance.directory 'import.stderr.log') -Wait -PassThru
    if ($cp6Import.ExitCode -ne 0) { throw 'n8n CLI import failed; stop before further actions' }
}
finally {
    foreach ($cp6Name in @([Environment]::GetEnvironmentVariables('Process').Keys)) { [Environment]::SetEnvironmentVariable($cp6Name, $null, 'Process') }
    foreach ($cp6Name in $cp6OldEnvironment.Keys) { [Environment]::SetEnvironmentVariable($cp6Name, $cp6OldEnvironment[$cp6Name], 'Process') }
    Remove-Variable cp6Environment,cp6Secure
}
@'
import os,sqlite3,json
from pathlib import Path
p=Path(os.environ['CP6_ISOLATED_DB_CHECK']).resolve()
c=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)
try:
    rows=c.execute('SELECT id,name,active,settings FROM workflow_entity ORDER BY id').fetchall()
    assert {r[0] for r in rows}=={'ievg2u7YcfdnU3L8','wmtArUNSGBtEuCUM'}, 'Workflow IDs differ; stop'
    assert all(not r[2] for r in rows), 'Unexpected activation'
    demo=next(r for r in rows if r[0]=='ievg2u7YcfdnU3L8')
    assert json.loads(demo[3])['errorWorkflow']=='wmtArUNSGBtEuCUM'
    assert c.execute('SELECT count(*) FROM execution_entity').fetchone()[0]==0
    print(json.dumps({'actual_imported_ids':[r[0] for r in rows],'error_handler_assignment_verified':True,'both_inactive':True,'execution_count':0}))
finally:
    c.close()
'@ | & $cp6Python -B -
if ($LASTEXITCODE -ne 0) { throw 'Post-import identity check failed; stop' }
$cp6Instance.workflows_imported = $true
$cp6Instance.owner_initialized = $true
[IO.File]::WriteAllText($cp6InstancePath, ($cp6Instance | ConvertTo-Json))
Write-Output 'Only the two authorized workflows imported; IDs preserved; no workflows published or triggered.'

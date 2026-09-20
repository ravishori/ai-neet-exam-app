#Requires -Version 5.1
<#
.SYNOPSIS
  Restore drill: verify dump TOC; if CREATEDB available, restore to clean DB and compare counts.

.PARAMETER DumpPath
  Path to a .dump from pg_backup.ps1

.PARAMETER KeepDrillDb
  If set, do not drop trinetra_db_h1_restore_drill at the end.
#>

param(
  [Parameter(Mandatory = $true)][string]$DumpPath,
  [switch]$KeepDrillDb
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$DrillDb = "trinetra_db_h1_restore_drill"

$EnvFile = Join-Path $RepoRoot "apps\backend\.env"
if ((-not $env:PGPASSWORD) -and (Test-Path $EnvFile)) {
  Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*DATABASE_URL\s*=\s*(.+)$') {
      $raw = $Matches[1].Trim().Trim('"').Trim("'")
      if ($raw -match '://([^:]+):([^@]+)@([^:/]+):?(\d*)/([^?\s]+)') {
        if (-not $env:PGUSER) { $env:PGUSER = $Matches[1] }
        if (-not $env:PGPASSWORD) { $env:PGPASSWORD = $Matches[2] }
        if (-not $env:PGHOST) { $env:PGHOST = $Matches[3] }
        if (-not $env:PGPORT) { $env:PGPORT = $(if ($Matches[4]) { $Matches[4] } else { "5432" }) }
        if (-not $env:PGDATABASE) { $env:PGDATABASE = $Matches[5] }
      }
    }
  }
}

if (-not $env:PGHOST) { $env:PGHOST = "localhost" }
if (-not $env:PGPORT) { $env:PGPORT = "5432" }
if (-not (Test-Path $DumpPath)) { throw "Dump not found: $DumpPath" }

function Find-PgTool([string]$Name) {
  $cmd = Get-Command $Name -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  foreach ($c in @(
      "D:\Program Files\PostgreSQL\18\bin\$Name.exe",
      "C:\Program Files\PostgreSQL\18\bin\$Name.exe",
      "C:\Program Files\PostgreSQL\17\bin\$Name.exe"
    )) {
    if (Test-Path $c) { return $c }
  }
  throw "Cannot find $Name"
}

$psql = Find-PgTool "psql"
$pgrestore = Find-PgTool "pg_restore"
$SourceDb = $env:PGDATABASE
if ([string]::IsNullOrWhiteSpace($SourceDb)) { throw "PGDATABASE (source) required" }

function Invoke-Psql([string]$Database, [string]$Sql) {
  # Pass SQL via stdin to avoid PowerShell parsing of SQL operators
  $Sql | & $psql -v ON_ERROR_STOP=1 -d $Database -t -A
  if ($LASTEXITCODE -ne 0) { throw "psql failed on $Database" }
}

Write-Host "SOURCE_DB=$SourceDb DRILL_DB=$DrillDb DUMP=$DumpPath"

$tocLines = & $pgrestore --list $DumpPath 2>$null
if ($LASTEXITCODE -ne 0) { throw "pg_restore --list failed; dump may be corrupt" }
Write-Host "DUMP_TOC_OK lines=$($tocLines.Count)"

$privSql = @'
SELECT rolcreatedb::text || '|' || rolsuper::text FROM pg_roles WHERE rolname = current_user;
'@
$priv = Invoke-Psql $SourceDb $privSql
$parts = ($priv | Where-Object { $_ -and $_.Trim() } | Select-Object -First 1).Trim() -split '\|'
$canCreate = ($parts[0] -eq "true") -or ($parts[1] -eq "true")
Write-Host "ROLE_CREATEDB=$($parts[0]) ROLE_SUPER=$($parts[1])"

if (-not $canCreate) {
  Write-Host "RESTORE_DRILL_BLOCKED reason=NO_CREATEDB_PRIVILEGE"
  Write-Host "Dump integrity verified via pg_restore --list. Full clean-DB restore requires CREATEDB or superuser (not granted by H1)."
  exit 2
}

$countSql = @'
SELECT 'identity.users|' || count(*)::text FROM identity.users
UNION ALL SELECT 'cms.content_items|' || count(*)::text FROM cms.content_items
UNION ALL SELECT 'cms.content_versions|' || count(*)::text FROM cms.content_versions
UNION ALL SELECT 'academic.subjects|' || count(*)::text FROM academic.subjects
UNION ALL SELECT 'academic.chapters|' || count(*)::text FROM academic.chapters
UNION ALL SELECT 'academic.topics|' || count(*)::text FROM academic.topics
UNION ALL SELECT 'academic.concepts|' || count(*)::text FROM academic.concepts;
'@

$sourceCounts = @{}
Invoke-Psql $SourceDb $countSql | Where-Object { $_ -and $_.Trim() } | ForEach-Object {
  $p = $_.Trim() -split '\|', 2
  if ($p.Length -eq 2) { $sourceCounts[$p[0]] = [int]$p[1] }
}
$srcLine = ($sourceCounts.GetEnumerator() | ForEach-Object { '{0}={1}' -f $_.Key, $_.Value }) -join ' '
Write-Host "SOURCE_COUNTS $srcLine"

$termSql = 'SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = ''' + $DrillDb + ''' AND pid <> pg_backend_pid();'
Invoke-Psql "postgres" $termSql | Out-Null
Invoke-Psql "postgres" ('DROP DATABASE IF EXISTS {0};' -f $DrillDb)
Invoke-Psql "postgres" ('CREATE DATABASE {0} OWNER {1};' -f $DrillDb, $env:PGUSER)

& $pgrestore --no-owner --no-acl --dbname=$DrillDb --exit-on-error $DumpPath
if ($LASTEXITCODE -ne 0) { throw "pg_restore failed with exit $LASTEXITCODE" }

$restoreCounts = @{}
Invoke-Psql $DrillDb $countSql | Where-Object { $_ -and $_.Trim() } | ForEach-Object {
  $p = $_.Trim() -split '\|', 2
  if ($p.Length -eq 2) { $restoreCounts[$p[0]] = [int]$p[1] }
}

$mismatches = @()
foreach ($k in $sourceCounts.Keys) {
  $s = $sourceCounts[$k]
  $r = $restoreCounts[$k]
  if ($s -ne $r) { $mismatches += "$k source=$s restore=$r" }
  Write-Host ("CHECK {0} source={1} restore={2} match={3}" -f $k, $s, $r, ($s -eq $r))
}

$schemaSql = @'
SELECT count(*) FROM information_schema.schemata
WHERE schema_name IN ('identity','academic','cms','assessment','ai','commerce','system');
'@
$schemas = Invoke-Psql $DrillDb $schemaSql
Write-Host ("SCHEMA_COUNT_EXPECTED_7 actual={0}" -f $schemas.Trim())

if ($mismatches.Count -gt 0) {
  throw ("Restore integrity mismatch: {0}" -f ($mismatches -join '; '))
}

if (-not $KeepDrillDb) {
  Invoke-Psql "postgres" $termSql | Out-Null
  Invoke-Psql "postgres" "DROP DATABASE IF EXISTS $DrillDb;"
  Write-Host "DRILL_DB_DROPPED=$DrillDb"
} else {
  Write-Host "DRILL_DB_KEPT=$DrillDb"
}

Write-Host "RESTORE_DRILL_OK"

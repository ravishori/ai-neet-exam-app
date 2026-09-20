#Requires -Version 5.1
<#
.SYNOPSIS
  Logical PostgreSQL backup (pg_dump custom format) for TALOS.

.DESCRIPTION
  Reads connection settings from environment variables only.
  Never prints PGPASSWORD. Writes under database/backups/ (gitignored).

.ENVIRONMENT
  PGHOST, PGPORT, PGUSER, PGDATABASE, PGPASSWORD
  Optional: BACKUP_ENV_LABEL (default: local), PG_DUMP path via PG_BIN
#>

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$OutDir = Join-Path $RepoRoot "database\backups"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function Require-Env([string]$Name) {
  $v = [Environment]::GetEnvironmentVariable($Name)
  if ([string]::IsNullOrWhiteSpace($v)) {
    throw "Missing required environment variable: $Name"
  }
  return $v
}

# Allow loading from apps/backend/.env without printing values (local ops only)
$EnvFile = Join-Path $RepoRoot "apps\backend\.env"
if ((-not $env:PGPASSWORD) -and (Test-Path $EnvFile)) {
  Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*DATABASE_URL\s*=\s*(.+)$') {
      $raw = $Matches[1].Trim().Trim('"').Trim("'")
      # postgresql+asyncpg://user:pass@host:port/db
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

$null = Require-Env "PGUSER"
$null = Require-Env "PGPASSWORD"
$null = Require-Env "PGDATABASE"
if (-not $env:PGHOST) { $env:PGHOST = "localhost" }
if (-not $env:PGPORT) { $env:PGPORT = "5432" }

$PgBin = if ($env:PG_BIN) { $env:PG_BIN } else { "" }
$PgDump = if ($PgBin) { Join-Path $PgBin "pg_dump.exe" } else { "pg_dump" }
if (-not (Get-Command $PgDump -ErrorAction SilentlyContinue)) {
  $candidates = @(
    "D:\Program Files\PostgreSQL\18\bin\pg_dump.exe",
    "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe",
    "C:\Program Files\PostgreSQL\17\bin\pg_dump.exe"
  )
  foreach ($c in $candidates) {
    if (Test-Path $c) { $PgDump = $c; break }
  }
}

$label = if ($env:BACKUP_ENV_LABEL) { $env:BACKUP_ENV_LABEL } else { "local" }
$ts = (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss")
$outName = "{0}_{1}_{2}Z.dump" -f $label, $env:PGDATABASE, $ts
$outPath = Join-Path $OutDir $outName

& $PgDump --format=custom --no-owner --no-acl --file=$outPath
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed with exit $LASTEXITCODE" }

$hash = (Get-FileHash -Algorithm SHA256 -Path $outPath).Hash.ToLower()
$meta = [ordered]@{
  artifact       = $outName
  path           = $outPath
  sha256         = $hash
  bytes          = (Get-Item $outPath).Length
  env_label      = $label
  pg_host        = $env:PGHOST
  pg_port        = $env:PGPORT
  pg_database    = $env:PGDATABASE
  pg_user        = $env:PGUSER
  created_utc    = (Get-Date).ToUniversalTime().ToString("o")
}
$metaPath = "$outPath.json"
($meta | ConvertTo-Json) | Set-Content -Path $metaPath -Encoding utf8

Write-Host "BACKUP_OK artifact=$outName sha256=$hash bytes=$($meta.bytes)"
# Machine-readable path on its own final line for scripting
Write-Output $outPath
# Also write sidecar pointer
Set-Content -Path (Join-Path $OutDir "LATEST_BACKUP.txt") -Value $outPath -Encoding utf8

<#
SkillAlign: one-step setup and start (Windows PowerShell 5.1+).

    .\start.ps1              set up whatever is missing, then start the API and the website
    .\start.ps1 -CheckOnly   run every check but start nothing
    .\start.ps1 -NoBrowser   do not open the browser

Safe to run again and again: it only installs/creates what is missing or changed, never deletes
data, and asks before migrating the database. Credentials come from the git-ignored `.env`.
#>
param([switch]$CheckOnly, [switch]$NoBrowser)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$EnvFile = Join-Path $Root '.env'
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok($msg) { Write-Host "    $msg" -ForegroundColor Green }
function Note($msg) { Write-Host "    $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Host "`n[STOPPED] $msg`n" -ForegroundColor Red; exit 1 }
function FileHash($path) { if (Test-Path $path) { (Get-FileHash -Algorithm SHA256 $path).Hash } else { '' } }
function Ask($question) { $a = Read-Host "$question [y/N]"; return ($a -match '^(y|yes)$') }

# ------------------------------------------------------------------ 1. tools
Step 'Checking tools'
$Python = $null
foreach ($cand in @(@('py', '-3'), @('python'))) {
    try {
        $v = & $cand[0] $cand[1..9] -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $v) { $Python = $cand; break }
    } catch { }
}
if (-not $Python) { Fail 'Python 3.10+ was not found. Install it from https://www.python.org/downloads/ (tick "Add to PATH").' }
$pyVer = [version](& $Python[0] $Python[1..9] -c "import sys; print('%d.%d' % sys.version_info[:2])")
if ($pyVer -lt [version]'3.10') { Fail "Python $pyVer found; 3.10 or newer is required." }
Ok "Python $pyVer"
try { $nodeVer = (node --version).TrimStart('v') } catch { Fail 'Node.js 18+ was not found. Install it from https://nodejs.org/' }
if ([version]$nodeVer -lt [version]'18.0') { Fail "Node.js $nodeVer found; 18 or newer is required." }
Ok "Node.js $nodeVer"

# ------------------------------------------------------------------ 2. credentials (.env)
Step 'Checking .env (credentials)'
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $Root '.env.example') $EnvFile
    Note 'Created .env from .env.example'
}
$envText = [IO.File]::ReadAllText($EnvFile)
if ($envText -match '(?m)^SECRET_KEY=\s*$') {
    $secret = & $Python[0] $Python[1..9] -c "import secrets; print(secrets.token_urlsafe(48))"
    $envText = [regex]::Replace($envText, '(?m)^SECRET_KEY=\s*$', "SECRET_KEY=$secret")
    [IO.File]::WriteAllText($EnvFile, $envText, $Utf8NoBom)
    Ok 'Generated a random SECRET_KEY in .env'
}
if ($envText -match '(?m)^DATABASE_URL=.*YOUR_PASSWORD') {
    Fail "Open .env (in $Root) and replace YOUR_PASSWORD in DATABASE_URL with your PostgreSQL password, then run this again."
}
Ok '.env is filled in'
$frontEnv = Join-Path $Frontend '.env'
if (-not (Test-Path $frontEnv)) { Copy-Item (Join-Path $Frontend '.env.example') $frontEnv; Note 'Created frontend/.env' }

# ------------------------------------------------------------------ 3. backend environment
Step 'Preparing the backend (Python virtual environment)'
$Venv = Join-Path $Backend '.venv'
$VenvPy = Join-Path $Venv 'Scripts\python.exe'
$venvOk = $false
if (Test-Path $VenvPy) {
    try { & $VenvPy -c "import sys" 2>$null; $venvOk = ($LASTEXITCODE -eq 0) } catch { $venvOk = $false }
}
if (-not $venvOk) {
    if (Test-Path $Venv) {
        $aside = "$Venv.broken-$(Get-Date -Format yyyyMMddHHmmss)"
        Rename-Item $Venv $aside
        Note "Existing .venv did not work on this PC (moved aside to $(Split-Path $aside -Leaf); you may delete it)"
    }
    & $Python[0] $Python[1..9] -m venv $Venv
    if ($LASTEXITCODE -ne 0) { Fail 'Could not create the Python virtual environment.' }
    Ok 'Created backend/.venv'
}
$reqHash = (FileHash (Join-Path $Backend 'requirements.txt')) + (FileHash (Join-Path $Backend 'requirements-dev.txt'))
$reqStamp = Join-Path $Venv '.requirements.sha256'
if (-not (Test-Path $reqStamp) -or (Get-Content $reqStamp -Raw).Trim() -ne $reqHash) {
    Note 'Installing backend packages (first run or requirements changed)...'
    & $VenvPy -m pip install --disable-pip-version-check -q -r (Join-Path $Backend 'requirements.txt') -r (Join-Path $Backend 'requirements-dev.txt')
    if ($LASTEXITCODE -ne 0) { Fail 'pip install failed (see the messages above).' }
    Set-Content -Path $reqStamp -Value $reqHash -Encoding ASCII
    Ok 'Backend packages installed'
} else { Ok 'Backend packages up to date' }

# ------------------------------------------------------------------ 4. frontend packages
Step 'Preparing the frontend (npm packages)'
$lockHash = FileHash (Join-Path $Frontend 'package-lock.json')
$lockStamp = Join-Path $Frontend 'node_modules\.package-lock.sha256'
if (-not (Test-Path $lockStamp) -or (Get-Content $lockStamp -Raw).Trim() -ne $lockHash) {
    Note 'Installing frontend packages (first run or package-lock changed)...'
    Push-Location $Frontend
    try { npm ci --no-audit --no-fund; if ($LASTEXITCODE -ne 0) { Fail 'npm ci failed (see the messages above).' } } finally { Pop-Location }
    Set-Content -Path $lockStamp -Value $lockHash -Encoding ASCII
    Ok 'Frontend packages installed'
} else { Ok 'Frontend packages up to date' }

# ------------------------------------------------------------------ 5. database
Step 'Checking the database'
function DbStatus { Push-Location $Backend; try { $out = & $VenvPy (Join-Path $Root 'scripts\db_status.py') 2>&1; $code = $LASTEXITCODE } finally { Pop-Location }; return @($code, ($out -join "`n")) }
$code, $out = DbStatus
if ($code -eq 2) {
    $reason = ($out -split "`n" | Where-Object { $_ -like 'CONNECT fail*' }) -replace '^CONNECT fail ', ''
    Fail "Cannot connect to PostgreSQL: $reason`n          Is PostgreSQL running, does the database exist, and is the password in .env correct?"
}
if ($code -eq 3) {
    $rev = ($out -split "`n" | Where-Object { $_ -like 'REV *' }) -split ' '
    Note "Database schema is at '$($rev[1])' but the app needs '$($rev[2])'."
    Note 'BACK UP FIRST, e.g.:  pg_dump -U postgres -F c -f skillalign_backup.dump skill_alignment_db'
    if ($CheckOnly) { Fail 'Migration needed (run without -CheckOnly to apply it).' }
    if (-not (Ask '    Have you backed up, and should the migration run now?')) { Fail 'Migration skipped; the API will not start on an outdated schema.' }
    Push-Location $Backend
    try { & (Join-Path $Venv 'Scripts\alembic.exe') upgrade head; if ($LASTEXITCODE -ne 0) { Fail 'alembic upgrade failed (database unchanged: the upgrade runs in a transaction).' } } finally { Pop-Location }
    Ok 'Database migrated'
    $code, $out = DbStatus
}
Ok 'Database schema is up to date'
$admins = [int](($out -split "`n" | Where-Object { $_ -like 'ADMINS *' }) -replace '^ADMINS ', '')
if ($admins -eq 0) {
    Note 'No administrator account exists yet.'
    if (-not $CheckOnly -and (Ask '    Create one now?')) {
        $email = Read-Host '    Admin email'
        $name = Read-Host '    Admin full name'
        Push-Location $Backend
        try { & $VenvPy -m app.cli create-admin --email $email --name $name } finally { Pop-Location }
    }
} else { Ok "$admins administrator account(s) found" }

if ($CheckOnly) { Write-Host "`nAll checks passed. Run .\start.ps1 (or start.bat) to start SkillAlign.`n" -ForegroundColor Green; exit 0 }

# ------------------------------------------------------------------ 6. start
Step 'Starting SkillAlign'
Start-Process powershell -WorkingDirectory $Backend -ArgumentList '-NoExit', '-Command',
    "`$host.UI.RawUI.WindowTitle='SkillAlign API'; & '$VenvPy' -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
Start-Process powershell -WorkingDirectory $Frontend -ArgumentList '-NoExit', '-Command',
    "`$host.UI.RawUI.WindowTitle='SkillAlign Web'; npm run dev"
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try { if ((Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:8000/health').StatusCode -eq 200) { $ready = $true; break } } catch { }
    Start-Sleep -Seconds 1
}
if ($ready) { Ok 'API is running at http://127.0.0.1:8000 (docs: /docs)' } else { Note 'API did not answer within 60 s: check the "SkillAlign API" window.' }
Ok 'Website: http://127.0.0.1:5173  (close the two new windows to stop)'
if (-not $NoBrowser) { Start-Sleep -Seconds 3; Start-Process 'http://127.0.0.1:5173' }

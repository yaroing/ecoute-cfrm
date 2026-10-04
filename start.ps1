$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (!(Test-Path '.venv/Scripts/python.exe')) { python -m venv .venv }
& .venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Installation Python échouée' }
& .venv/Scripts/python.exe backend/manage.py migrate
& .venv/Scripts/python.exe backend/manage.py migrate --database sensible
& .venv/Scripts/python.exe backend/manage.py seed_demo
Push-Location frontend
& npm.cmd ci
& npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw 'Construction front-end échouée' }
Pop-Location
$apiProcess = Start-Process -WindowStyle Hidden -PassThru -FilePath "$PSScriptRoot/.venv/Scripts/python.exe" -ArgumentList 'backend/manage.py runserver 127.0.0.1:8000 --noreload' -WorkingDirectory $PSScriptRoot -RedirectStandardOutput "$PSScriptRoot/api.log" -RedirectStandardError "$PSScriptRoot/api-error.log"
$workerProcess = Start-Process -WindowStyle Hidden -PassThru -FilePath "$PSScriptRoot/.venv/Scripts/python.exe" -ArgumentList 'backend/manage.py worker' -WorkingDirectory $PSScriptRoot -RedirectStandardOutput "$PSScriptRoot/worker.log" -RedirectStandardError "$PSScriptRoot/worker-error.log"
Write-Host "Application : http://127.0.0.1:5173 | API PID $($apiProcess.Id) | Worker PID $($workerProcess.Id)"
Write-Host 'Identifiants dans .demo-credentials.json. Ctrl+C arrête la prévisualisation.'
Push-Location frontend
try { & npm.cmd run preview -- --port 5173 } finally { Stop-Process -Id $apiProcess.Id,$workerProcess.Id -ErrorAction SilentlyContinue; Pop-Location }

@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "COMMIT_MESSAGE=Initial commit - Infant Pulse AI system"
set "SCRIPT_DIR=%~dp0"

goto :main

:log
echo [%~1] %~2
exit /b 0

:run_command
call :log INFO "%*"
%*
set "CMD_EXIT_CODE=%ERRORLEVEL%"
if not "!CMD_EXIT_CODE!"=="0" (
  call :log ERROR "Command failed with exit code !CMD_EXIT_CODE!: %*"
  exit /b !CMD_EXIT_CODE!
)
exit /b 0

:validate_repo_url
set "REPO_URL_TO_VALIDATE=%~1"
powershell -NoProfile -Command ^
  "$url = ($env:REPO_URL_TO_VALIDATE).Trim();" ^
  "$httpsPattern = '^(https://github\.com/[^/\s]+/[^/\s]+(?:\.git)?/?$)';" ^
  "$sshPattern = '^(git@github\.com:[^/\s]+/[^/\s]+(?:\.git)?$)';" ^
  "if ($url -match $httpsPattern -or $url -match $sshPattern) { exit 0 } else { exit 1 }"
if errorlevel 1 (
  call :log ERROR "Invalid GitHub repository URL. Use https://github.com/owner/repo(.git) or git@github.com:owner/repo.git"
  exit /b 1
)
exit /b 0

:check_internet
powershell -NoProfile -Command ^
  "try {" ^
  "  $response = Invoke-WebRequest -Uri 'https://github.com' -Method Head -TimeoutSec 10 -UseBasicParsing;" ^
  "  if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) { exit 0 }" ^
  "  exit 1" ^
  "} catch { exit 1 }"
if errorlevel 1 (
  call :log ERROR "Unable to reach GitHub. Check your internet connection and try again."
  exit /b 1
)
exit /b 0

:validate_email
set "EMAIL_TO_VALIDATE=%~1"
powershell -NoProfile -Command ^
  "$email = ($env:EMAIL_TO_VALIDATE).Trim();" ^
  "if ($email -match '^[^@\s]+@[^@\s]+\.[^@\s]+$') { exit 0 } else { exit 1 }"
if errorlevel 1 (
  call :log ERROR "Invalid email format."
  exit /b 1
)
exit /b 0

:ensure_git_identity
set "GIT_USER_NAME="
set "GIT_USER_EMAIL="

for /f "delims=" %%A in ('git config --get user.name 2^>nul') do set "GIT_USER_NAME=%%A"
for /f "delims=" %%A in ('git config --get user.email 2^>nul') do set "GIT_USER_EMAIL=%%A"

if not defined GIT_USER_NAME (
  set /p "GIT_USER_NAME=Enter git user.name: "
  if not defined GIT_USER_NAME (
    call :log ERROR "git user.name cannot be empty."
    exit /b 1
  )
  call :run_command git config user.name "%GIT_USER_NAME%"
)

if not defined GIT_USER_EMAIL (
  set /p "GIT_USER_EMAIL=Enter git user.email: "
  if not defined GIT_USER_EMAIL (
    call :log ERROR "git user.email cannot be empty."
    exit /b 1
  )
  call :validate_email "%GIT_USER_EMAIL%"
  if errorlevel 1 exit /b 1
  call :run_command git config user.email "%GIT_USER_EMAIL%"
)

exit /b 0

:ensure_gitignore
powershell -NoProfile -Command ^
  "$path = Join-Path (Get-Location) '.gitignore';" ^
  "$required = @(" ^
  "  'node_modules/'," ^
  "  '.venv/'," ^
  "  'venv/'," ^
  "  '__pycache__/'," ^
  "  '**/__pycache__/'," ^
  "  '*.pyc'," ^
  "  '.env'," ^
  "  '.next/'," ^
  "  'dist/'," ^
  "  'build/'," ^
  "  '.pytest_cache/'," ^
  "  '*.log'," ^
  "  '*.db'" ^
  ");" ^
  "if (-not (Test-Path $path)) { New-Item -ItemType File -Path $path -Force | Out-Null };" ^
  "$existing = Get-Content $path -ErrorAction SilentlyContinue;" ^
  "$missing = $required | Where-Object { $_ -notin $existing };" ^
  "if ($missing.Count -gt 0) { Add-Content -Path $path -Value ($missing -join [Environment]::NewLine) }"
if errorlevel 1 (
  call :log ERROR "Failed to create or update .gitignore."
  exit /b 1
)
call :log INFO ".gitignore is ready."
exit /b 0

:configure_remote
set "CURRENT_REMOTE="
for /f "delims=" %%A in ('git remote get-url origin 2^>nul') do set "CURRENT_REMOTE=%%A"

if defined CURRENT_REMOTE (
  if /I "!CURRENT_REMOTE!"=="%REPO_URL%" (
    call :log INFO "Remote origin already points to %REPO_URL%"
  ) else (
    call :log WARN "Remote origin exists and will be updated."
    call :run_command git remote set-url origin "%REPO_URL%"
  )
  exit /b 0
)

call :run_command git remote add origin "%REPO_URL%"
exit /b 0

:main
cd /d "%SCRIPT_DIR%" || (
  call :log ERROR "Failed to switch to the script directory."
  exit /b 1
)

call :log INFO "Starting GitHub push workflow from %CD%"

where git >nul 2>&1
if errorlevel 1 (
  call :log ERROR "Git is not installed or not available in PATH."
  exit /b 1
)

set "REPO_URL=%~1"
if not defined REPO_URL (
  set /p "REPO_URL=Enter GitHub repository URL: "
)

for /f "tokens=* delims= " %%A in ("%REPO_URL%") do set "REPO_URL=%%~A"
if not defined REPO_URL (
  call :log ERROR "Repository URL is required."
  exit /b 1
)

call :validate_repo_url "%REPO_URL%"
if errorlevel 1 exit /b 1

call :check_internet
if errorlevel 1 exit /b 1

call :ensure_git_identity
if errorlevel 1 exit /b 1

call :ensure_gitignore
if errorlevel 1 exit /b 1

if exist ".git" (
  call :log INFO "Git repository already initialized."
) else (
  call :run_command git init
  if errorlevel 1 exit /b 1
)

call :run_command git add .
if errorlevel 1 exit /b 1

git diff --cached --quiet --ignore-submodules --
set "HAS_STAGED_CHANGES=%ERRORLEVEL%"

git rev-parse --verify HEAD >nul 2>&1
set "HAS_EXISTING_COMMIT=%ERRORLEVEL%"

if "!HAS_STAGED_CHANGES!"=="0" (
  if not "!HAS_EXISTING_COMMIT!"=="0" (
    call :log ERROR "No staged changes found and the repository has no commits yet."
    exit /b 1
  )
  call :log WARN "No staged changes detected. Skipping commit."
) else (
  call :run_command git commit -m "%COMMIT_MESSAGE%"
  if errorlevel 1 exit /b 1
)

call :run_command git branch -M main
if errorlevel 1 exit /b 1

call :configure_remote
if errorlevel 1 exit /b 1

call :run_command git push -u origin main
if errorlevel 1 exit /b 1

call :log SUCCESS "Project pushed to GitHub successfully."
exit /b 0
